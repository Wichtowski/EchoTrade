"""Redis-backed async status tracking for browser capture jobs."""

from __future__ import annotations

import json
from asyncio import to_thread
from datetime import UTC, datetime

from bson import ObjectId
from pymongo import MongoClient
from redis.asyncio import Redis
from redis.exceptions import RedisError

from libshared.config import settings
from libshared.schemas import (
    BrowserCaptureDocumentOut,
    BrowserCaptureProvider,
    BrowserCaptureTaskOut,
    SavedQueryCreate,
    SavedQueryKind,
    SavedQueryOut,
)

CNBC_CAPTURE_TIME_RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "ALL"]
CAPTURE_STATUS_TTL_SECONDS = 60 * 60 * 24


def _capture_key(provider: BrowserCaptureProvider, symbol: str) -> str:
    return f"browser_capture:{provider.value}:{symbol.strip().upper()}"


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


async def _redis() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def _mongo_collection():
    client = MongoClient(settings.mongodb_url)
    database = client[settings.mongodb_database]
    return client, database[settings.mongodb_chart_collection]


def _saved_queries_collection():
    client = MongoClient(settings.mongodb_url)
    database = client[settings.mongodb_database]
    return client, database[settings.mongodb_saved_query_collection]


async def get_capture_status(
    provider: BrowserCaptureProvider,
    symbol: str,
) -> BrowserCaptureTaskOut | None:
    client = await _redis()
    try:
        raw = await client.get(_capture_key(provider, symbol))
    except RedisError:
        return None
    finally:
        await client.aclose()
    if raw is None:
        return None
    return BrowserCaptureTaskOut.model_validate(json.loads(raw))


async def get_capture_statuses(
    provider: BrowserCaptureProvider,
    symbols: list[str],
) -> dict[str, BrowserCaptureTaskOut | None]:
    normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    if not normalized:
        return {}
    client = await _redis()
    try:
        values = await client.mget([_capture_key(provider, symbol) for symbol in normalized])
    except RedisError:
        return {symbol: None for symbol in normalized}
    finally:
        await client.aclose()
    return {
        symbol: BrowserCaptureTaskOut.model_validate(json.loads(raw)) if raw else None
        for symbol, raw in zip(normalized, values, strict=False)
    }


async def set_capture_status(
    provider: BrowserCaptureProvider,
    symbol: str,
    payload: dict[str, object],
) -> BrowserCaptureTaskOut:
    normalized_symbol = symbol.strip().upper()
    client = await _redis()
    serialized = json.dumps(payload)
    try:
        await client.set(_capture_key(provider, normalized_symbol), serialized, ex=CAPTURE_STATUS_TTL_SECONDS)
    except RedisError as exc:
        raise RuntimeError(
            "Redis is not available. Start Redis before queueing browser capture jobs."
        ) from exc
    finally:
        await client.aclose()
    return BrowserCaptureTaskOut.model_validate(payload)


def _read_latest_capture_document_sync(
    provider: BrowserCaptureProvider,
    symbol: str,
) -> BrowserCaptureDocumentOut | None:
    client, collection = _mongo_collection()
    try:
        document = collection.find_one(
            {"symbol": symbol.strip().upper(), "source": provider.value},
            sort=[("captured_at", -1)],
        )
    finally:
        client.close()
    if document is None:
        return None
    document_id = str(document.pop("_id", ""))
    captured_at = document.get("captured_at")
    return BrowserCaptureDocumentOut(
        provider=provider,
        symbol=symbol.strip().upper(),
        document_id=document_id,
        captured_at=str(captured_at) if captured_at is not None else None,
        document=document,
    )


async def get_latest_capture_document(
    provider: BrowserCaptureProvider,
    symbol: str,
) -> BrowserCaptureDocumentOut | None:
    return await to_thread(_read_latest_capture_document_sync, provider, symbol)


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


def _read_capture_availability_sync(
    provider: BrowserCaptureProvider,
    symbols: list[str],
) -> dict[str, bool]:
    normalized = [symbol.strip().upper() for symbol in symbols if symbol.strip()]
    if not normalized:
        return {}
    client, collection = _mongo_collection()
    try:
        available_symbols = {
            str(document.get("symbol", "")).strip().upper()
            for document in collection.find(
                {"symbol": {"$in": normalized}, "source": provider.value},
                {"symbol": 1},
            )
        }
    finally:
        client.close()
    return {symbol: symbol in available_symbols for symbol in normalized}


async def get_capture_availability(
    provider: BrowserCaptureProvider,
    symbols: list[str],
) -> dict[str, bool]:
    return await to_thread(_read_capture_availability_sync, provider, symbols)


def _build_saved_query(document: dict[str, object]) -> SavedQueryOut:
    document_id = str(document.get("_id", ""))
    created_at = document.get("created_at")
    updated_at = document.get("updated_at")
    return SavedQueryOut(
        id=document_id,
        kind=SavedQueryKind(str(document.get("kind", SavedQueryKind.BROWSER_CHART.value))),
        name=str(document.get("name", "")),
        payload=document.get("payload", {}) if isinstance(document.get("payload"), dict) else {},
        created_at=created_at if isinstance(created_at, datetime) else datetime.now(UTC),
        updated_at=updated_at if isinstance(updated_at, datetime) else datetime.now(UTC),
    )


def _list_saved_queries_sync(kind: SavedQueryKind) -> list[SavedQueryOut]:
    client, collection = _saved_queries_collection()
    try:
        documents = list(
            collection.find({"kind": kind.value}).sort([("updated_at", -1), ("created_at", -1)])
        )
    finally:
        client.close()
    return [_build_saved_query(document) for document in documents]


async def list_saved_queries(kind: SavedQueryKind) -> list[SavedQueryOut]:
    return await to_thread(_list_saved_queries_sync, kind)


def _create_saved_query_sync(query: SavedQueryCreate) -> SavedQueryOut:
    now = datetime.now(UTC)
    client, collection = _saved_queries_collection()
    try:
        existing = collection.find_one({"kind": query.kind.value, "name": query.name})
        if existing is not None:
            collection.update_one(
                {"_id": existing["_id"]},
                {"$set": {"payload": query.payload, "updated_at": now}},
            )
            existing["payload"] = query.payload
            existing["updated_at"] = now
            return _build_saved_query(existing)

        document = {
            "kind": query.kind.value,
            "name": query.name,
            "payload": query.payload,
            "created_at": now,
            "updated_at": now,
        }
        insert_result = collection.insert_one(document)
        document["_id"] = insert_result.inserted_id
        return _build_saved_query(document)
    finally:
        client.close()


async def create_saved_query(query: SavedQueryCreate) -> SavedQueryOut:
    return await to_thread(_create_saved_query_sync, query)


def _delete_saved_query_sync(query_id: str) -> bool:
    if not ObjectId.is_valid(query_id):
        return False
    client, collection = _saved_queries_collection()
    try:
        result = collection.delete_one({"_id": ObjectId(query_id)})
    finally:
        client.close()
    return result.deleted_count > 0


async def delete_saved_query(query_id: str) -> bool:
    return await to_thread(_delete_saved_query_sync, query_id)
