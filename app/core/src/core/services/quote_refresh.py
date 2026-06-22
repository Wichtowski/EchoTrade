"""Redis-backed async status tracking for held quote refresh jobs."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from redis.asyncio import Redis
from redis.exceptions import RedisError

from libshared.config import settings
from libshared.schemas import MarketQuoteRefreshTaskOut

QUOTE_REFRESH_STATUS_KEY = "market_quote_refresh:held"
QUOTE_REFRESH_STATUS_TTL_SECONDS = 60 * 60 * 24


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


async def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def build_quote_refresh_payload(
    *,
    task_id: str,
    provider: str,
    requested_symbols: list[str],
    status: str,
    stored_count: int = 0,
    failed_symbols: list[str] | None = None,
    error: str | None = None,
) -> dict[str, object]:
    return {
        "task_id": task_id,
        "provider": provider,
        "requested_symbols": requested_symbols,
        "status": status,
        "stored_count": stored_count,
        "failed_symbols": failed_symbols or [],
        "error": error,
        "updated_at": _now_iso(),
    }


async def get_quote_refresh_status() -> MarketQuoteRefreshTaskOut | None:
    client = await _redis()
    try:
        raw = await client.get(QUOTE_REFRESH_STATUS_KEY)
    except RedisError:
        return None
    finally:
        await client.aclose()
    if raw is None:
        return None
    return MarketQuoteRefreshTaskOut.model_validate(json.loads(raw))


async def set_quote_refresh_status(payload: dict[str, object]) -> MarketQuoteRefreshTaskOut:
    client = await _redis()
    serialized = json.dumps(payload)
    try:
        await client.set(QUOTE_REFRESH_STATUS_KEY, serialized, ex=QUOTE_REFRESH_STATUS_TTL_SECONDS)
    except RedisError as exc:
        raise RuntimeError(
            "Redis is not available. Start Redis before queueing held quote refresh jobs."
        ) from exc
    finally:
        await client.aclose()
    return MarketQuoteRefreshTaskOut.model_validate(payload)
