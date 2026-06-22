"""Market data fetching and storage helpers."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libdb.models import ManualTrade, MarketHistoryBar, MarketQuote, Position
from libshared.schemas import MarketHistoryBarOut, MarketQuoteIngest

YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rate/{base}/{quote}"


def _to_naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def build_market_quote(data: MarketQuoteIngest) -> MarketQuote:
    return MarketQuote(
        symbol=data.symbol.upper(),
        price=data.price,
        currency=data.currency,
        source=data.source,
        source_timestamp=_to_naive_utc(data.source_timestamp),
        delay_seconds=data.delay_seconds,
        confidence=data.confidence,
        warnings=data.warnings,
    )


async def fetch_yahoo_quote(
    symbol: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> MarketQuoteIngest:
    normalized_symbol = symbol.strip().upper()
    if client is None:
        async with httpx.AsyncClient(timeout=10.0) as managed_client:
            response = await managed_client.get(
                YAHOO_CHART_URL.format(symbol=normalized_symbol),
                params={"range": "5d", "interval": "1d", "includePrePost": "false"},
            )
            response.raise_for_status()
            payload = response.json()
    else:
        response = await client.get(
            YAHOO_CHART_URL.format(symbol=normalized_symbol),
            params={"range": "5d", "interval": "1d", "includePrePost": "false"},
        )
        response.raise_for_status()
        payload = response.json()

    result = _extract_yahoo_result(payload, normalized_symbol)
    meta = result.get("meta")
    if not isinstance(meta, dict):
        raise RuntimeError(f"Yahoo response meta missing for {normalized_symbol}")

    current_price = meta.get("regularMarketPrice") or meta.get("previousClose")
    timestamp = meta.get("regularMarketTime")
    currency = meta.get("currency")
    if not current_price:
        raise RuntimeError(f"No current price returned for {normalized_symbol}")

    source_timestamp = (
        datetime.fromtimestamp(timestamp, tz=UTC) if isinstance(timestamp, int | float) and timestamp > 0 else None
    )
    warnings: list[str] = []
    if source_timestamp is None:
        warnings.append("Source timestamp missing from Yahoo response")

    return MarketQuoteIngest(
        symbol=normalized_symbol,
        price=float(current_price),
        currency=str(currency).upper() if isinstance(currency, str) and currency else "USD",
        source="yahoo",
        source_timestamp=source_timestamp,
        confidence="high",
        warnings=warnings or None,
    )


async def fetch_yahoo_quotes(
    symbols: list[str],
    *,
    delay_seconds: float = 0.0,
) -> tuple[list[MarketQuoteIngest], list[str]]:
    normalized_symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    stored_quotes: list[MarketQuoteIngest] = []
    failed_symbols: list[str] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        for index, symbol in enumerate(normalized_symbols):
            if index > 0 and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            try:
                quote = await fetch_yahoo_quote(symbol, client=client)
            except Exception as exc:  # pragma: no cover - external dependency path
                failed_symbols.append(f"{symbol}: {exc}")
                continue
            stored_quotes.append(quote)

    return stored_quotes, failed_symbols


async def fetch_frankfurter_rate(
    base_currency: str,
    quote_currency: str,
    *,
    on_date: datetime | None = None,
) -> float:
    normalized_base = base_currency.strip().upper()
    normalized_quote = quote_currency.strip().upper()
    if normalized_base == normalized_quote:
        return 1.0

    params: dict[str, str] = {}
    if on_date is not None:
        params["date"] = on_date.date().isoformat()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            FRANKFURTER_RATE_URL.format(base=normalized_base, quote=normalized_quote),
            params=params,
        )
        response.raise_for_status()
        payload = response.json()

    rate = payload.get("rate")
    if not isinstance(rate, int | float):
        raise RuntimeError(f"No Frankfurter FX rate returned for {normalized_base}/{normalized_quote}")
    return float(rate)


def build_weekly_checkpoint_bar(quote: MarketQuoteIngest) -> MarketHistoryBarOut:
    if quote.source_timestamp is None:
        bar_anchor = datetime.now(UTC)
    elif quote.source_timestamp.tzinfo is None:
        bar_anchor = quote.source_timestamp.replace(tzinfo=UTC)
    else:
        bar_anchor = quote.source_timestamp.astimezone(UTC)
    week_start = (bar_anchor - timedelta(days=bar_anchor.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    captured_at = datetime.now(UTC).replace(tzinfo=None)
    price = float(quote.price)
    return MarketHistoryBarOut(
        symbol=quote.symbol.upper(),
        resolution="W",
        bar_time=week_start.replace(tzinfo=None),
        open_price=price,
        high_price=price,
        low_price=price,
        close_price=price,
        volume=None,
        source=f"{quote.source}_checkpoint",
        captured_at=captured_at,
    )


async def resolve_history_start(session: AsyncSession, symbol: str) -> datetime:
    normalized_symbol = symbol.strip().upper()
    trade_result = await session.execute(
        select(ManualTrade.executed_at)
        .where(ManualTrade.ticker == normalized_symbol)
        .where(ManualTrade.action == "BUY")
        .order_by(ManualTrade.executed_at.asc())
        .limit(1)
    )
    first_trade = trade_result.scalar_one_or_none()
    if first_trade is not None:
        return first_trade

    position_result = await session.execute(
        select(Position.opened_at)
        .where(Position.ticker == normalized_symbol)
        .where(Position.opened_at.is_not(None))
        .order_by(Position.opened_at.asc())
        .limit(1)
    )
    first_position_open = position_result.scalar_one_or_none()
    if first_position_open is not None:
        return first_position_open

    raise RuntimeError(f"No first buy or opened position found for {normalized_symbol}")


async def fetch_yahoo_weekly_bars(
    symbol: str,
    started_at: datetime,
    ended_at: datetime | None = None,
) -> list[MarketHistoryBarOut]:
    ended_at = ended_at or datetime.now(UTC)
    from_unix = int(_to_naive_utc(started_at).timestamp())
    to_unix = int(_to_naive_utc(ended_at).timestamp())
    normalized_symbol = symbol.strip().upper()

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            YAHOO_CHART_URL.format(symbol=normalized_symbol),
            params={
                "period1": str(from_unix),
                "period2": str(to_unix),
                "interval": "1wk",
                "includePrePost": "false",
                "events": "div,splits",
            },
        )
        response.raise_for_status()
        payload = response.json()

    return _build_yahoo_history_bars_from_payload(symbol=normalized_symbol, resolution="W", payload=payload)


def _build_history_bars_from_payload(
    symbol: str,
    resolution: str,
    payload: dict[str, object],
) -> list[MarketHistoryBarOut]:
    timestamps = payload.get("t")
    opens = payload.get("o")
    highs = payload.get("h")
    lows = payload.get("l")
    closes = payload.get("c")
    volumes = payload.get("v")

    if not all(isinstance(series, list) for series in [timestamps, opens, highs, lows, closes]):
        raise RuntimeError(f"Incomplete candle payload returned for {symbol}")

    volume_series: Iterable[object | None]
    if isinstance(volumes, list):
        volume_series = volumes
    else:
        volume_series = [None] * len(timestamps)

    captured_at = datetime.now(UTC).replace(tzinfo=None)
    bars: list[MarketHistoryBarOut] = []
    for timestamp, open_price, high_price, low_price, close_price, volume in zip(
        timestamps,
        opens,
        highs,
        lows,
        closes,
        volume_series,
        strict=False,
    ):
        if not isinstance(timestamp, int | float):
            continue
        bars.append(
            MarketHistoryBarOut(
                symbol=symbol.upper(),
                resolution=resolution,
                bar_time=datetime.fromtimestamp(timestamp, tz=UTC).replace(tzinfo=None),
                open_price=float(open_price),
                high_price=float(high_price),
                low_price=float(low_price),
                close_price=float(close_price),
                volume=float(volume) if isinstance(volume, int | float) else None,
                source="market_api",
                captured_at=captured_at,
            )
        )
    return bars


def _extract_yahoo_result(payload: dict[str, object], symbol: str) -> dict[str, object]:
    chart = payload.get("chart")
    if not isinstance(chart, dict):
        raise RuntimeError(f"Yahoo chart payload missing for {symbol}")

    error = chart.get("error")
    if error:
        raise RuntimeError(f"Yahoo returned an error for {symbol}: {error}")

    results = chart.get("result")
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        raise RuntimeError(f"No Yahoo chart result returned for {symbol}")
    return results[0]


def _build_yahoo_history_bars_from_payload(
    symbol: str,
    resolution: str,
    payload: dict[str, object],
) -> list[MarketHistoryBarOut]:
    result = _extract_yahoo_result(payload, symbol)
    timestamps = result.get("timestamp")
    indicators = result.get("indicators")
    if not isinstance(timestamps, list) or not isinstance(indicators, dict):
        raise RuntimeError(f"Incomplete Yahoo candle payload returned for {symbol}")

    quote_list = indicators.get("quote")
    if not isinstance(quote_list, list) or not quote_list or not isinstance(quote_list[0], dict):
        raise RuntimeError(f"Yahoo quote indicators missing for {symbol}")

    quote = quote_list[0]
    opens = quote.get("open")
    highs = quote.get("high")
    lows = quote.get("low")
    closes = quote.get("close")
    volumes = quote.get("volume")

    if not all(isinstance(series, list) for series in [opens, highs, lows, closes]):
        raise RuntimeError(f"Incomplete Yahoo OHLC payload returned for {symbol}")

    volume_series: Iterable[object | None]
    if isinstance(volumes, list):
        volume_series = volumes
    else:
        volume_series = [None] * len(timestamps)

    captured_at = datetime.now(UTC).replace(tzinfo=None)
    bars: list[MarketHistoryBarOut] = []
    for timestamp, open_price, high_price, low_price, close_price, volume in zip(
        timestamps,
        opens,
        highs,
        lows,
        closes,
        volume_series,
        strict=False,
    ):
        if not isinstance(timestamp, int | float):
            continue
        if not all(isinstance(value, int | float) for value in [open_price, high_price, low_price, close_price]):
            continue
        bars.append(
            MarketHistoryBarOut(
                symbol=symbol.upper(),
                resolution=resolution,
                bar_time=datetime.fromtimestamp(timestamp, tz=UTC).replace(tzinfo=None),
                open_price=float(open_price),
                high_price=float(high_price),
                low_price=float(low_price),
                close_price=float(close_price),
                volume=float(volume) if isinstance(volume, int | float) else None,
                source="yahoo",
                captured_at=captured_at,
            )
        )
    if not bars:
        raise RuntimeError(f"No usable Yahoo weekly history returned for {symbol}")
    return bars


async def upsert_history_bars(
    session: AsyncSession,
    bars: list[MarketHistoryBarOut],
) -> list[MarketHistoryBar]:
    stored: list[MarketHistoryBar] = []
    for bar in bars:
        result = await session.execute(
            select(MarketHistoryBar)
            .where(MarketHistoryBar.symbol == bar.symbol)
            .where(MarketHistoryBar.resolution == bar.resolution)
            .where(MarketHistoryBar.bar_time == bar.bar_time)
            .limit(1)
        )
        existing = result.scalar_one_or_none()
        record = existing or MarketHistoryBar(
            symbol=bar.symbol,
            resolution=bar.resolution,
            bar_time=bar.bar_time,
            open_price=bar.open_price,
            high_price=bar.high_price,
            low_price=bar.low_price,
            close_price=bar.close_price,
            volume=bar.volume,
            source=bar.source,
            captured_at=bar.captured_at,
        )
        record.open_price = bar.open_price
        record.high_price = bar.high_price
        record.low_price = bar.low_price
        record.close_price = bar.close_price
        record.volume = bar.volume
        record.source = bar.source
        record.captured_at = bar.captured_at
        session.add(record)
        stored.append(record)
    await session.commit()
    for record in stored:
        await session.refresh(record)
    return stored
