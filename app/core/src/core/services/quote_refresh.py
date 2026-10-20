"""PostgreSQL-backed status tracking for held quote refresh jobs."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from libdb.models import AutomationRun
from libdb.session import async_session
from libshared.schemas import MarketQuoteRefreshTaskOut
from sqlalchemy import select


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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


async def get_quote_refresh_status(user_id: UUID) -> MarketQuoteRefreshTaskOut | None:
    async with async_session() as session:
        job = await session.scalar(
            select(AutomationRun)
            .where(AutomationRun.kind == "quotes", AutomationRun.user_id == user_id)
            .order_by(AutomationRun.created_at.desc())
            .limit(1)
        )
        if job is None:
            return None
        payload = dict(
            job.payload
            or build_quote_refresh_payload(
                task_id=str(job.id),
                provider="yahoo",
                requested_symbols=(job.request or {}).get("symbols", []),
                status=job.status,
            )
        )
        payload["status"] = job.status
        payload["error"] = job.error
        return MarketQuoteRefreshTaskOut.model_validate(payload)
