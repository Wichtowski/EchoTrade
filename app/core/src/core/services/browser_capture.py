"""PostgreSQL-backed browser capture data and job status."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from libdb.models import AutomationRun, BrowserDocument, SavedQuery
from libdb.session import async_session
from libshared.schemas import (
    BrowserCaptureDocumentOut,
    BrowserCaptureProvider,
    BrowserCaptureTaskOut,
    SavedQueryCreate,
    SavedQueryKind,
    SavedQueryOut,
)
from sqlalchemy import select

CNBC_CAPTURE_TIME_RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "ALL"]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def build_capture_payload(
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
) -> dict[str, object]:
    return {
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


async def get_capture_status(
    provider: BrowserCaptureProvider, symbol: str, user_id: UUID
) -> BrowserCaptureTaskOut | None:
    async with async_session() as session:
        job = await session.scalar(
            select(AutomationRun)
            .where(
                AutomationRun.kind == "capture",
                AutomationRun.user_id == user_id,
                AutomationRun.request["symbol"].astext == symbol.strip().upper(),
            )
            .order_by(AutomationRun.created_at.desc())
            .limit(1)
        )
        if job is None:
            return None
        payload = dict(
            job.payload
            or build_capture_payload(
                task_id=str(job.id), provider=provider, symbol=symbol, status=job.status
            )
        )
        payload["status"] = job.status
        payload["error"] = job.error
        return BrowserCaptureTaskOut.model_validate(payload)


async def get_capture_statuses(
    provider: BrowserCaptureProvider, symbols: list[str], user_id: UUID
) -> dict[str, BrowserCaptureTaskOut | None]:
    return {
        symbol.strip().upper(): await get_capture_status(provider, symbol, user_id)
        for symbol in symbols
        if symbol.strip()
    }


async def get_latest_capture_document(
    provider: BrowserCaptureProvider, symbol: str
) -> BrowserCaptureDocumentOut | None:
    async with async_session() as session:
        document = await session.scalar(
            select(BrowserDocument)
            .where(
                BrowserDocument.provider == provider.value,
                BrowserDocument.symbol == symbol.strip().upper(),
            )
            .order_by(BrowserDocument.captured_at.desc())
            .limit(1)
        )
        if document is None:
            return None
        return BrowserCaptureDocumentOut(
            provider=provider,
            symbol=document.symbol,
            document_id=document.id,
            captured_at=document.captured_at.isoformat(),
            document=document.document,
        )


def extract_latest_capture_close(document: dict[str, object]) -> float | None:
    ranges = document.get("ranges")
    if not isinstance(ranges, dict):
        return None

    preferred_order = ["1D", "5D", "1M", "3M", "6M"]
    for range_key in preferred_order:
        latest = _extract_latest_close_from_range(ranges.get(range_key))
        if latest is not None:
            return latest

    for payload in ranges.values():
        latest = _extract_latest_close_from_range(payload)
        if latest is not None:
            return latest
    return None


def _extract_latest_close_from_range(payload: object) -> float | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    chart_data = data.get("chartData")
    if not isinstance(chart_data, dict):
        return None
    price_bars = chart_data.get("priceBars")
    if not isinstance(price_bars, list):
        return None
    for bar in reversed(price_bars):
        if not isinstance(bar, dict):
            continue
        close_value = bar.get("close")
        try:
            close = float(close_value)
        except (TypeError, ValueError):
            continue
        return close
    return None


async def get_capture_availability(
    provider: BrowserCaptureProvider, symbols: list[str]
) -> dict[str, bool]:
    normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    async with async_session() as session:
        available = set(
            (
                await session.scalars(
                    select(BrowserDocument.symbol).where(
                        BrowserDocument.provider == provider.value,
                        BrowserDocument.symbol.in_(normalized),
                    )
                )
            ).all()
        )
    return {symbol: symbol in available for symbol in normalized}


def _saved(query: SavedQuery) -> SavedQueryOut:
    return SavedQueryOut(
        id=query.id,
        kind=query.kind,
        name=query.name,
        payload=query.payload,
        created_at=query.created_at,
        updated_at=query.updated_at,
    )


async def list_saved_queries(kind: SavedQueryKind) -> list[SavedQueryOut]:
    async with async_session() as session:
        queries = (
            await session.scalars(
                select(SavedQuery)
                .where(SavedQuery.kind == kind.value)
                .order_by(SavedQuery.updated_at.desc())
            )
        ).all()
        return [_saved(query) for query in queries]


async def create_saved_query(query: SavedQueryCreate) -> SavedQueryOut:
    async with async_session() as session:
        existing = await session.scalar(
            select(SavedQuery)
            .where(SavedQuery.kind == query.kind.value, SavedQuery.name == query.name)
            .with_for_update()
        )
        if existing is None:
            existing = SavedQuery(
                id=str(uuid4()), kind=query.kind.value, name=query.name, payload=query.payload
            )
            session.add(existing)
        else:
            existing.payload = query.payload
        await session.commit()
        await session.refresh(existing)
        return _saved(existing)


async def delete_saved_query(query_id: str) -> bool:
    async with async_session() as session:
        query = await session.get(SavedQuery, query_id)
        if query is None:
            return False
        await session.delete(query)
        await session.commit()
        return True
