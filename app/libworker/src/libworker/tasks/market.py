"""Market data Celery tasks."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
import json

from pymongo import MongoClient
from redis import Redis
from redis.exceptions import RedisError

from core.services.market_data import build_market_quote, fetch_yahoo_quotes
from core.services.quote_refresh import build_quote_refresh_payload
from lens.browser import CNBC_CAPTURE_TIME_RANGES, LensCaptureError, capture_cnbc_chart_data
from libshared.schemas import BrowserCaptureProvider
from libshared.config import settings
from libdb.session import async_session
from libworker.celery_app import app

CAPTURE_STATUS_TTL_SECONDS = 60 * 60 * 24
QUOTE_REFRESH_DELAY_SECONDS = 2.0


def _capture_key(provider: BrowserCaptureProvider, symbol: str) -> str:
    return f"browser_capture:{provider.value}:{symbol.strip().upper()}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _set_capture_status(
    *,
    task_id: str,
    provider: BrowserCaptureProvider,
    symbol: str,
    status: str,
    document_id: str | None = None,
    error: str | None = None,
    error_stage: str | None = None,
    error_code: str | None = None,
    retryable: bool | None = None,
    error_details: dict[str, str] | None = None,
) -> dict[str, object] | None:
    payload = {
        "task_id": task_id,
        "symbol": symbol.strip().upper(),
        "provider": provider.value,
        "status": status,
        "time_ranges": CNBC_CAPTURE_TIME_RANGES,
        "document_id": document_id,
        "error": error,
        "error_stage": error_stage,
        "error_code": error_code,
        "retryable": retryable,
        "error_details": error_details,
        "updated_at": _now_iso(),
    }
    client = _redis()
    try:
        client.set(_capture_key(provider, symbol), json.dumps(payload), ex=CAPTURE_STATUS_TTL_SECONDS)
    except RedisError:
        return None
    finally:
        client.close()
    return payload


def _set_quote_refresh_status(
    *,
    task_id: str,
    requested_symbols: list[str],
    status: str,
    provider: str = "yahoo",
    stored_count: int = 0,
    failed_symbols: list[str] | None = None,
    error: str | None = None,
) -> dict[str, object] | None:
    payload = build_quote_refresh_payload(
        task_id=task_id,
        provider=provider,
        requested_symbols=requested_symbols,
        status=status,
        stored_count=stored_count,
        failed_symbols=failed_symbols,
        error=error,
    )
    client = _redis()
    try:
        client.set("market_quote_refresh:held", json.dumps(payload), ex=CAPTURE_STATUS_TTL_SECONDS)
    except RedisError:
        return None
    finally:
        client.close()
    return payload


def _mongo_collection():
    client = MongoClient(settings.mongodb_url)
    database = client[settings.mongodb_database]
    collection = database[settings.mongodb_chart_collection]
    return client, collection


@app.task(name="market.fetch_prices")
def fetch_prices(symbols: list[str] | None = None) -> dict:
    """Fetch current prices for given symbols or all held tickers.

    TODO: Multi-source fetching (Yahoo, broker, optional fallbacks).
    """
    return {"status": "ok", "task": "fetch_prices", "symbols": symbols or []}


@app.task(bind=True, name="market.refresh_held_yahoo_quotes")
def refresh_held_yahoo_quotes(self, symbols: list[str]) -> dict:
    """Refresh held quotes with throttled Yahoo requests in the worker."""
    normalized_symbols = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    _set_quote_refresh_status(
        task_id=self.request.id,
        requested_symbols=normalized_symbols,
        status="running",
    )
    try:
        return asyncio.run(
            _refresh_held_yahoo_quotes(task_id=self.request.id, symbols=normalized_symbols)
        )
    except Exception as exc:
        _set_quote_refresh_status(
            task_id=self.request.id,
            requested_symbols=normalized_symbols,
            status="failed",
            error=str(exc),
        )
        raise


async def _refresh_held_yahoo_quotes(task_id: str, symbols: list[str]) -> dict:
    quotes, failed_symbols = await fetch_yahoo_quotes(
        symbols,
        delay_seconds=QUOTE_REFRESH_DELAY_SECONDS,
    )

    async with async_session() as session:
        for quote_data in quotes:
            session.add(build_market_quote(quote_data))
        await session.commit()

    _set_quote_refresh_status(
        task_id=task_id,
        requested_symbols=symbols,
        status="completed",
        stored_count=len(quotes),
        failed_symbols=failed_symbols,
    )

    return {
        "status": "ok",
        "task": "refresh_held_yahoo_quotes",
        "provider": "yahoo",
        "requested_symbols": symbols,
        "stored_count": len(quotes),
        "failed_symbols": failed_symbols,
        "delay_seconds": QUOTE_REFRESH_DELAY_SECONDS,
    }


@app.task(name="market.fetch_news")
def fetch_news(symbol: str) -> dict:
    """Fetch news for a symbol.

    TODO: Yahoo company news, RSS feeds.
    """
    return {"status": "ok", "task": "fetch_news", "symbol": symbol}


@app.task(name="market.check_movement")
def check_movement(threshold_pct: float = 5.0) -> dict:
    """Check for large daily movements above threshold.

    Used by urgent-alerts workflow.
    TODO: Compare current vs previous close for all held tickers.
    """
    return {"status": "ok", "task": "check_movement", "threshold_pct": threshold_pct}


@app.task(bind=True, name="market.capture_cnbc_chart")
def capture_cnbc_chart(self, symbol: str) -> dict:
    """Capture CNBC chart GraphQL payload for a single symbol via Playwright."""
    normalized_symbol = symbol.strip().upper()
    _set_capture_status(
        task_id=self.request.id,
        provider=BrowserCaptureProvider.CNBC,
        symbol=normalized_symbol,
        status="running",
    )
    try:
        return asyncio.run(_capture_cnbc_chart(task_id=self.request.id, symbol=normalized_symbol))
    except LensCaptureError as exc:
        _set_capture_status(
            task_id=self.request.id,
            provider=BrowserCaptureProvider.CNBC,
            symbol=normalized_symbol,
            status="failed",
            error=str(exc),
            error_stage=exc.stage,
            error_code=exc.code,
            retryable=exc.retryable,
            error_details=exc.details,
        )
        return {
            "status": "failed",
            "task": "capture_cnbc_chart",
            "symbol": normalized_symbol,
            "provider": BrowserCaptureProvider.CNBC.value,
            "error": str(exc),
            "error_stage": exc.stage,
            "error_code": exc.code,
            "retryable": exc.retryable,
            "error_details": exc.details,
        }
    except Exception as exc:
        _set_capture_status(
            task_id=self.request.id,
            provider=BrowserCaptureProvider.CNBC,
            symbol=normalized_symbol,
            status="failed",
            error=str(exc),
            error_stage="worker",
            error_code=exc.__class__.__name__,
            retryable=False,
        )
        raise


async def _capture_cnbc_chart(task_id: str, symbol: str) -> dict:
    result = await capture_cnbc_chart_data(symbol=symbol)

    client, collection = _mongo_collection()
    try:
        document = {
            **(result.document or {}),
            "captured_at": _now_iso(),
            "observations": [asdict(item) for item in result.observations],
            "warnings": result.warnings,
        }
        insert_result = collection.insert_one(document)
        document_id = str(insert_result.inserted_id)
    finally:
        client.close()

    _set_capture_status(
        task_id=task_id,
        provider=BrowserCaptureProvider.CNBC,
        symbol=result.symbol,
        status="completed",
        document_id=document_id,
    )

    range_count = 0
    if isinstance(result.document, dict) and isinstance(result.document.get("ranges"), dict):
        range_count = len(result.document["ranges"])
    return {
        "status": "ok",
        "task": "capture_cnbc_chart",
        "symbol": result.symbol,
        "time_ranges": CNBC_CAPTURE_TIME_RANGES,
        "document_id": document_id,
        "range_count": range_count,
        "observations": [asdict(item) for item in result.observations],
    }
