"""Copy legacy chart captures and saved queries to PostgreSQL without deleting Mongo data."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from libdb.models import Base, BrowserDocument, DataMigration, SavedQuery
from libdb.session import async_session, engine
from libshared.config import settings
from pymongo import MongoClient
from sqlalchemy.dialects.postgresql import insert


def capture_values(document: dict) -> dict:
    data = dict(document)
    identifier = str(data.pop("_id"))
    captured = data.get("captured_at")
    timestamp = (
        datetime.fromisoformat(captured.replace("Z", "+00:00"))
        if isinstance(captured, str)
        else captured
    )
    if not isinstance(timestamp, datetime):
        raise ValueError("Legacy capture has no valid timestamp")
    return {
        "id": identifier,
        "provider": str(data.get("source", "cnbc")),
        "symbol": str(data["symbol"]).upper(),
        "captured_at": timestamp.replace(tzinfo=None),
        "document": json.loads(json.dumps(data, default=str)),
    }


async def main() -> None:
    counts = {"captures": 0, "saved_queries": 0}
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    with MongoClient(settings.mongodb_url, serverSelectionTimeoutMS=5000) as client:
        database = client[settings.mongodb_database]
        async with async_session() as session:
            for document in database[settings.mongodb_chart_collection].find():
                statement = (
                    insert(BrowserDocument)
                    .values(**capture_values(document))
                    .on_conflict_do_nothing()
                )
                result = await session.execute(statement)
                counts["captures"] += result.rowcount
            for document in database[settings.mongodb_saved_query_collection].find():
                values = {
                    "id": str(document["_id"]),
                    "kind": document["kind"],
                    "name": document["name"],
                    "payload": document.get("payload", {}),
                    "created_at": document.get("created_at", datetime.now(UTC)).replace(
                        tzinfo=None
                    ),
                    "updated_at": document.get("updated_at", datetime.now(UTC)).replace(
                        tzinfo=None
                    ),
                }
                result = await session.execute(
                    insert(SavedQuery).values(**values).on_conflict_do_nothing()
                )
                counts["saved_queries"] += result.rowcount
            await session.execute(
                insert(DataMigration)
                .values(name="legacy_mongo", counts=counts)
                .on_conflict_do_update(
                    index_elements=["name"],
                    set_={"counts": counts, "completed_at": datetime.now(UTC).replace(tzinfo=None)},
                )
            )
            await session.commit()
    print(json.dumps(counts))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
