"""Market data router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.browser_capture import (
    CNBC_CAPTURE_TIME_RANGES,
    build_capture_payload,
    create_saved_query,
    delete_saved_query,
    get_capture_availability,
    get_capture_status,
    get_capture_statuses,
    get_latest_capture_document,
    list_saved_queries,
    set_capture_status,
)
from core.services.market_data import (
    build_weekly_checkpoint_bar,
    build_market_quote,
    fetch_frankfurter_rate,
    fetch_yahoo_quotes,
    fetch_yahoo_weekly_bars,
    resolve_history_start,
    upsert_history_bars,
)
from core.services.quote_refresh import (
    build_quote_refresh_payload,
    get_quote_refresh_status,
    set_quote_refresh_status,
)
from libdb.models import MarketHistoryBar, MarketQuote, Position
from libdb.session import get_session
from libshared.schemas import (
    BrowserCaptureDocumentOut,
    BrowserCaptureProvider,
    BrowserCaptureTaskOut,
    MarketHistoryBarOut,
    MarketHistoryCaptureResult,
    MarketQuoteOut,
    MarketQuoteRefreshResult,
    MarketQuoteRefreshTaskOut,
    SavedQueryCreate,
    SavedQueryKind,
    SavedQueryOut,
)
from libworker.tasks.market import capture_cnbc_chart, refresh_held_yahoo_quotes

router = APIRouter()


PROVIDER_TASKS = {
    BrowserCaptureProvider.CNBC: capture_cnbc_chart,
}


@router.get("/prices")
async def get_prices(
    symbols: str = "", session: AsyncSession = Depends(get_session)
) -> dict[str, object]:
    """Return the latest stored prices for comma-separated symbols."""
    requested_symbols = [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]
    result = await session.execute(select(MarketQuote).order_by(MarketQuote.received_at.desc()))
    latest: dict[str, MarketQuoteOut] = {}
    for quote in result.scalars().all():
        if requested_symbols and quote.symbol not in requested_symbols:
            continue
        if quote.symbol not in latest:
            latest[quote.symbol] = MarketQuoteOut.model_validate(quote)
    return {
        "symbols": requested_symbols,
        "prices": {symbol: price.model_dump() for symbol, price in latest.items()},
    }


@router.post("/quotes/refresh-held", response_model=MarketQuoteRefreshResult, status_code=201)
async def refresh_held_quotes(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> MarketQuoteRefreshResult:
    position_result = await session.execute(select(Position.ticker).where(Position.user_id == user_id))
    symbols = sorted({ticker.strip().upper() for ticker in position_result.scalars().all() if ticker})
    if not symbols:
        return MarketQuoteRefreshResult(
            requested_symbols=[],
            stored_quotes=[],
            provider="yahoo",
            failed_symbols=[],
        )

    quote_payloads, failed_symbols = await fetch_yahoo_quotes(symbols)

    stored_quotes: list[MarketQuote] = []
    for quote_data in quote_payloads:
        quote = build_market_quote(quote_data)
        session.add(quote)
        stored_quotes.append(quote)

    await session.commit()
    for quote in stored_quotes:
        await session.refresh(quote)

    return MarketQuoteRefreshResult(
        requested_symbols=symbols,
        stored_quotes=[MarketQuoteOut.model_validate(quote) for quote in stored_quotes],
        provider="yahoo",
        failed_symbols=failed_symbols,
    )


@router.post("/quotes/refresh-held/queue", response_model=MarketQuoteRefreshTaskOut, status_code=202)
async def queue_refresh_held_quotes(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> MarketQuoteRefreshTaskOut:
    position_result = await session.execute(select(Position.ticker).where(Position.user_id == user_id))
    symbols = sorted({ticker.strip().upper() for ticker in position_result.scalars().all() if ticker})
    if not symbols:
        raise HTTPException(status_code=409, detail="No held positions found to refresh.")

    existing = await get_quote_refresh_status()
    if existing is not None and existing.status in {"queued", "running"}:
        raise HTTPException(status_code=409, detail="Held quote refresh is already queued or running.")

    task = refresh_held_yahoo_quotes.delay(symbols)
    payload = build_quote_refresh_payload(
        task_id=task.id,
        provider="yahoo",
        requested_symbols=symbols,
        status="queued",
    )
    try:
        return await set_quote_refresh_status(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/quotes/refresh-held/status", response_model=MarketQuoteRefreshTaskOut | None)
async def get_refresh_held_quotes_status() -> MarketQuoteRefreshTaskOut | None:
    return await get_quote_refresh_status()


@router.get("/news")
async def get_news(symbol: str = "") -> dict[str, object]:
    """Fetch news for a symbol."""
    # TODO: implement news fetching (Yahoo, RSS)
    return {"symbol": symbol, "articles": []}


@router.get("/sector-summary")
async def sector_summary() -> dict[str, object]:
    # TODO: implement sector summary
    return {"sectors": {}}


@router.get("/fx")
async def fx_rates(pair: str = "USD/PLN", date: str | None = None) -> dict[str, object]:
    try:
        base_currency, quote_currency = [part.strip().upper() for part in pair.split("/", maxsplit=1)]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Pair must look like USD/PLN") from exc

    requested_at = datetime.fromisoformat(date) if date else None
    try:
        rate = await fetch_frankfurter_rate(base_currency, quote_currency, on_date=requested_at)
    except Exception as exc:  # pragma: no cover - external dependency path
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch Frankfurter FX rate for {base_currency}/{quote_currency}: {exc}",
        ) from exc
    return {
        "pair": f"{base_currency}/{quote_currency}",
        "rate": rate,
        "date": requested_at.date().isoformat() if requested_at is not None else None,
        "provider": "frankfurter",
    }


@router.get("/history")
async def price_history(
    symbol: str = "",
    resolution: str = "W",
    session: AsyncSession = Depends(get_session),
) -> dict[str, object]:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        return {"symbol": normalized_symbol, "resolution": resolution, "data": []}
    result = await session.execute(
        select(MarketHistoryBar)
        .where(MarketHistoryBar.symbol == normalized_symbol)
        .where(MarketHistoryBar.resolution == resolution.upper())
        .order_by(MarketHistoryBar.bar_time.asc())
    )
    bars = [MarketHistoryBarOut.model_validate(bar).model_dump() for bar in result.scalars().all()]
    return {"symbol": normalized_symbol, "resolution": resolution.upper(), "data": bars}


@router.post("/browser/capture/{provider}/{ticker}", response_model=BrowserCaptureTaskOut, status_code=202)
async def enqueue_browser_capture(
    provider: BrowserCaptureProvider,
    ticker: str,
) -> BrowserCaptureTaskOut:
    normalized_symbol = ticker.strip().upper()
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    task_runner = PROVIDER_TASKS.get(provider)
    if task_runner is None:
        raise HTTPException(status_code=404, detail=f"Provider {provider.value} is not supported")

    existing = await get_capture_status(provider, normalized_symbol)
    if existing is not None and existing.status in {"queued", "running"}:
        raise HTTPException(
            status_code=409,
            detail=f"{provider.value} capture is already {existing.status} for {normalized_symbol}",
        )

    task = task_runner.delay(normalized_symbol)
    payload = build_capture_payload(
        task_id=task.id,
        provider=provider,
        symbol=normalized_symbol,
        status="queued",
    )
    try:
        return await set_capture_status(provider, normalized_symbol, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/browser/capture/{provider}/status")
async def get_browser_capture_statuses(
    provider: BrowserCaptureProvider,
    symbols: str = "",
) -> dict[str, object]:
    requested_symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    statuses = await get_capture_statuses(provider, requested_symbols)
    return {
        "statuses": {
            symbol: status.model_dump() if status is not None else None for symbol, status in statuses.items()
        },
        "time_ranges": CNBC_CAPTURE_TIME_RANGES,
        "provider": provider.value,
    }


@router.get("/browser/capture/{provider}/availability")
async def get_browser_capture_availability_route(
    provider: BrowserCaptureProvider,
    symbols: str = "",
) -> dict[str, object]:
    requested_symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]
    return {
        "provider": provider.value,
        "available": await get_capture_availability(provider, requested_symbols),
    }


@router.get("/browser/capture/{provider}/{ticker}/latest", response_model=BrowserCaptureDocumentOut)
async def get_latest_browser_capture(
    provider: BrowserCaptureProvider,
    ticker: str,
) -> BrowserCaptureDocumentOut:
    normalized_symbol = ticker.strip().upper()
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="Ticker is required")

    document = await get_latest_capture_document(provider, normalized_symbol)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"No stored browser capture found for {provider.value} {normalized_symbol}",
        )
    return document


@router.get("/saved-queries", response_model=list[SavedQueryOut])
async def get_saved_queries(kind: SavedQueryKind) -> list[SavedQueryOut]:
    return await list_saved_queries(kind)


@router.post("/saved-queries", response_model=SavedQueryOut, status_code=201)
async def save_query(query: SavedQueryCreate) -> SavedQueryOut:
    return await create_saved_query(query)


@router.delete("/saved-queries/{query_id}", status_code=204)
async def remove_saved_query(query_id: str) -> None:
    deleted = await delete_saved_query(query_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Saved query {query_id} was not found")


@router.post("/history/capture/{symbol}", response_model=MarketHistoryCaptureResult, status_code=201)
async def capture_weekly_history(
    symbol: str,
    session: AsyncSession = Depends(get_session),
) -> MarketHistoryCaptureResult:
    normalized_symbol = symbol.strip().upper()
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="Symbol is required")

    warnings: list[str] = []
    try:
        started_at = await resolve_history_start(session, normalized_symbol)
        try:
            fetched_bars = await fetch_yahoo_weekly_bars(normalized_symbol, started_at=started_at)
        except HTTPException:
            raise
        except Exception as exc:
            checkpoint_quote = await fetch_yahoo_quote(normalized_symbol)
            fetched_bars = [build_weekly_checkpoint_bar(checkpoint_quote)]
            warnings.append(
                "Yahoo weekly candles were unavailable, so only the current weekly checkpoint was stored."
            )
        stored_bars = await upsert_history_bars(session, fetched_bars)
    except Exception as exc:  # pragma: no cover - network / integration path
        raise HTTPException(
            status_code=502,
            detail=f"Failed to capture weekly history for {normalized_symbol}: {exc}",
        ) from exc

    ended_at = stored_bars[-1].bar_time if stored_bars else started_at
    return MarketHistoryCaptureResult(
        symbol=normalized_symbol,
        resolution="W",
        started_at=started_at,
        ended_at=ended_at,
        bars_written=len(stored_bars),
        bars=[MarketHistoryBarOut.model_validate(bar) for bar in stored_bars],
        source="yahoo",
        warnings=warnings,
    )
