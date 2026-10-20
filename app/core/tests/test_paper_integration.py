from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from core.services import jobs
from core.services.paper import account_state, load_account
from core.services.trading import (
    approve_trade_proposal,
    create_trade_proposal,
    evaluate_trade_proposal,
    execute_approved_paper_trade,
)
from fastapi import HTTPException
from libdb.models import Base, ExecutedTrade, MarketQuote, PaperAccount, User
from libshared.config import settings
from libshared.schemas import TradeProposalCreate
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def database(monkeypatch):
    url = os.environ.get("ECHO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set ECHO_TEST_DATABASE_URL to an isolated PostgreSQL database")
    schema = "test_" + uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(settings, "cooldown_after_trade_hours", 0)
    monkeypatch.setattr(settings, "cooldown_after_loss_hours", 0)
    # Fixed open session keeps transaction tests independent of the wall clock.
    import core.services.paper as paper
    import core.services.trading as trading

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return (
                datetime(2026, 10, 13, 16, 0, tzinfo=UTC) if tz else datetime(2026, 10, 13, 16, 0)
            )

    monkeypatch.setattr(trading, "datetime", Clock)
    monkeypatch.setattr(paper, "datetime", Clock)
    async with factory() as session:
        owner = User(email=f"{uuid4()}@example.com", password_hash="test", role="owner")
        session.add(owner)
        await session.commit()
        user_id = owner.id
        account = await load_account(session, user_id)
        account.status = "active"
        session.add(
            MarketQuote(
                symbol="AMD",
                price=100,
                currency="USD",
                source="yahoo",
                source_timestamp=datetime(2026, 10, 13, 15, 59),
                received_at=datetime(2026, 10, 13, 16, 0),
            )
        )
        await session.commit()
    yield factory, user_id
    await engine.dispose()
    async with admin.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    await admin.dispose()


def proposal(action="BUY", amount=50, **changes):
    return TradeProposalCreate.model_validate(
        {
            "ticker": "AMD",
            "action": action,
            "amount": amount,
            "currency": "USD",
            "reason": "Sourced research",
            "thesis": "Defined thesis",
            "risks": ["Demand risk"],
            "invalidated_if": "Guidance weakens",
            "review_date": "2026-11-13T12:00:00Z",
            "sources": [{"title": "Filing", "url": "https://example.com/filing"}],
            **changes,
        }
    )


async def approved(factory, user_id, data):
    async with factory() as session:
        created = await create_trade_proposal(session, data, user_id=user_id)
        checked = await evaluate_trade_proposal(session, created.id, user_id=user_id)
        assert checked.passed
        assert created.status == "pending"
        result = await approve_trade_proposal(session, created.id, user_id=user_id)
        return result.id


async def test_concurrent_retry_fills_once_and_preserves_cash(database):
    factory, user_id = database
    proposal_id = await approved(factory, user_id, proposal())

    async def execute():
        async with factory() as session:
            return (await execute_approved_paper_trade(session, proposal_id, user_id=user_id)).id

    first, second = await asyncio.gather(execute(), execute())
    assert first == second
    async with factory() as session:
        assert await session.scalar(select(func.count(ExecutedTrade.id))) == 1
        account = await load_account(session, user_id)
        state = await account_state(session, account)
        assert state.cash == 250
        assert state.equity == 300
        assert state.positions[0].quantity == 0.5


async def test_sell_updates_cash_and_realized_pnl(database):
    factory, user_id = database
    buy = await approved(factory, user_id, proposal())
    async with factory() as session:
        await execute_approved_paper_trade(session, buy, user_id=user_id)
        quote = await session.scalar(select(MarketQuote))
        quote.price = 120
        await session.commit()
    sell = await approved(factory, user_id, proposal("SELL", 60))
    async with factory() as session:
        await execute_approved_paper_trade(session, sell, user_id=user_id)
        state = await account_state(session, await load_account(session, user_id))
        assert state.cash == 310
        assert state.realized_pnl == 10
        assert state.positions == []


@pytest.mark.parametrize(
    "change,rule",
    [
        ({"status": "paused"}, "trading_paused"),
        ({"source_timestamp": datetime(2026, 10, 12)}, "stale_market_data"),
        ({"currency": "PLN"}, "currency_mismatch"),
    ],
)
async def test_execution_rechecks_changed_conditions(database, change, rule):
    factory, user_id = database
    proposal_id = await approved(factory, user_id, proposal())
    async with factory() as session:
        target = (
            await session.get(PaperAccount, user_id)
            if "status" in change
            else await session.scalar(select(MarketQuote))
        )
        for key, value in change.items():
            setattr(target, key, value)
        await session.commit()
    async with factory() as session:
        with pytest.raises(HTTPException, match=rule):
            await execute_approved_paper_trade(session, proposal_id, user_id=user_id)


async def test_sell_without_holdings_and_unapproved_fill_rejected(database):
    factory, user_id = database
    async with factory() as session:
        sell = await create_trade_proposal(session, proposal("SELL"), user_id=user_id)
        result = await evaluate_trade_proposal(session, sell.id, user_id=user_id)
        assert "insufficient_holdings" in result.failed_rules
        buy = await create_trade_proposal(session, proposal(), user_id=user_id)
        with pytest.raises(HTTPException, match="manually approved"):
            await execute_approved_paper_trade(session, buy.id, user_id=user_id)


async def test_model_settings_persist_and_viewer_cannot_write(database, monkeypatch):
    from core.app import app
    from libdb.session import get_session

    factory, user_id = database
    monkeypatch.setattr(settings, "internal_api_token", "integration-token")

    async def session_dependency():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = session_dependency
    try:
        headers = {"X-Echo-Internal-Token": "integration-token", "X-Echo-User-Id": str(user_id)}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", headers=headers
        ) as client:
            response = await client.put(
                "/ai/settings",
                json={
                    "commentary_model": "gpt-6.1-sol",
                    "proposal_model": "gpt-6-luna",
                    "reasoning_effort": "medium",
                },
            )
            assert response.status_code == 200, response.text
            assert (await client.get("/ai/settings")).json()["commentary_model"] == "gpt-6.1-sol"
            assert "api_key" not in response.json()
            assert (
                await client.put("/ai/settings", json={"commentary_model": "invalid"})
            ).status_code == 422
            async with factory() as session:
                viewer = User(
                    email=f"{uuid4()}@example.com", password_hash="test", role="invited_viewer"
                )
                session.add(viewer)
                await session.commit()
            client.headers["X-Echo-User-Id"] = str(viewer.id)
            assert (await client.put("/ai/settings", json={})).status_code == 403
            assert (
                await client.patch("/paper/account", json={"status": "active"})
            ).status_code == 403
    finally:
        app.dependency_overrides.clear()


async def test_scheduled_enqueue_is_idempotent(database):
    factory, user_id = database
    async with factory() as session:
        first = await jobs.enqueue(session, "daily", user_id, "2026-10-13", scheduled=True)
        second = await jobs.enqueue(session, "daily", user_id, "2026-10-13", scheduled=True)
        assert first.id == second.id


async def test_manual_enqueue_rejects_concurrent_duplicates(database):
    factory, user_id = database

    async def add():
        async with factory() as session:
            try:
                return await jobs.enqueue(session, "commentary", user_id)
            except HTTPException as exc:
                return exc

    results = await asyncio.gather(add(), add())
    assert sum(isinstance(result, HTTPException) for result in results) == 1


async def test_delivery_retry_reuses_research_and_proposal(database, monkeypatch):
    factory, user_id = database
    calls = 0
    from core.services.ai import get_ai_settings
    from libdb.models import AgentDecision, AutomationRun, TradeProposal

    async def generate(*args):
        nonlocal calls
        calls += 1
        return {
            "proposal": proposal().model_dump(mode="json"),
            "reason": "Research supports a proposal",
            "model": "gpt-6-luna",
            "usage": {},
            "response_id": "resp_test",
            "sources": [{"title": "Filing", "url": "https://example.com/filing"}],
        }

    async def refresh(*args):
        return {"failed_symbols": []}

    async def deliver(*args):
        raise httpx.ConnectError("Delivery temporarily unavailable")

    monkeypatch.setattr(jobs, "async_session", factory)
    monkeypatch.setattr(jobs, "generate_research", generate)
    monkeypatch.setattr(jobs, "refresh_quotes", refresh)
    monkeypatch.setattr(jobs, "deliver_notification", deliver)
    async with factory() as session:
        config = await get_ai_settings(session, user_id)
        config.automation_enabled = True
        await session.commit()
        job = await jobs.enqueue(session, "proposal", user_id)
    for _ in range(2):
        with pytest.raises(httpx.ConnectError):
            await jobs.process_job(job.id)
    async with factory() as session:
        assert await session.scalar(select(func.count(TradeProposal.id))) == 1
        assert await session.scalar(select(func.count(AgentDecision.id))) == 2
        assert (await session.get(AutomationRun, job.id)).payload["proposal_id"]
    assert calls == 1


@pytest.mark.parametrize("kind", ["daily", "weekly", "scan"])
async def test_report_jobs_store_results_with_naive_database_dates(database, monkeypatch, kind):
    from core.services import browser_capture
    from core.services.ai import get_ai_settings
    from libdb.models import (
        AutomationRun,
        ManualTrade,
        OpportunityScan,
        PortfolioSnapshot,
        Position,
        WeeklyReview,
    )

    factory, user_id = database

    async def generate(*args):
        return {
            "commentary": "Sourced report",
            "risks": [],
            "watchlist": [],
            "model": "gpt-6-luna",
            "usage": {},
            "response_id": "resp_report",
            "sources": [],
        }

    async def refresh(*args):
        return {"failed_symbols": []}

    async def deliver(*args):
        return None

    monkeypatch.setattr(jobs, "async_session", factory)
    monkeypatch.setattr(browser_capture, "async_session", factory)
    monkeypatch.setattr(jobs, "generate_research", generate)
    monkeypatch.setattr(jobs, "refresh_quotes", refresh)
    monkeypatch.setattr(jobs, "deliver_notification", deliver)
    async with factory() as session:
        config = await get_ai_settings(session, user_id)
        config.automation_enabled = True
        session.add(
            Position(
                user_id=user_id,
                account_type="personal",
                ticker="AMD",
                quantity=1,
                average_price=100,
                currency="USD",
                broker="Revolut",
            )
        )
        session.add(
            ManualTrade(
                user_id=user_id,
                account_type="personal",
                ticker="AMD",
                action="BUY",
                quantity=1,
                price=100,
                currency="USD",
                broker="Revolut",
                fees=0,
                executed_at=datetime.now(UTC).replace(tzinfo=None),
                review_date=datetime.now(UTC).replace(tzinfo=None),
            )
        )
        await session.commit()
        job = await jobs.enqueue(session, kind, user_id)
    await jobs.process_job(job.id)
    await jobs.process_job(job.id)
    async with factory() as session:
        assert (await session.get(AutomationRun, job.id)).status == "completed"
        table = {"daily": PortfolioSnapshot, "weekly": WeeklyReview, "scan": OpportunityScan}[kind]
        assert await session.scalar(select(func.count(table.id))) == 1


def test_calendar_holidays_early_close_and_dst():
    assert jobs.scheduled_periods(datetime(2026, 12, 25, 16, tzinfo=UTC)) == []
    assert ("daily", "2026-11-27") in jobs.scheduled_periods(
        datetime(2026, 11, 27, 18, 20, tzinfo=UTC)
    )
    assert any(
        kind == "hourly"
        for kind, _ in jobs.scheduled_periods(datetime(2026, 10, 26, 14, tzinfo=UTC))
    )
    assert not any(
        kind == "hourly"
        for kind, _ in jobs.scheduled_periods(datetime(2026, 11, 2, 14, tzinfo=UTC))
    )


def test_movement_alerts_require_fresh_matching_quotes():
    before = {"AMD": {"price": 100, "currency": "USD", "fresh": True}}
    current = {"AMD": {"price": 110, "currency": "USD", "fresh": True}}
    assert jobs.movement_warnings(before, current) == [
        "AMD moved +10.00% since the previous monitoring check"
    ]
    current["AMD"]["fresh"] = False
    assert jobs.movement_warnings(before, current) == []


async def test_capture_queue_allows_different_symbols_but_blocks_same_symbol(database):
    factory, user_id = database
    async with factory() as session:
        await jobs.enqueue(session, "capture", user_id, request={"symbol": "AMD"})
        await jobs.enqueue(session, "capture", user_id, request={"symbol": "NVDA"})
        with pytest.raises(HTTPException, match="already queued"):
            await jobs.enqueue(session, "capture", user_id, request={"symbol": "AMD"})
