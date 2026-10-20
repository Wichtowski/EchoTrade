"""One background consumer and scheduler in the API process; PostgreSQL owns the queue."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import exchange_calendars as calendars
import httpx
from fastapi import HTTPException
from lens.browser import LensCaptureError, capture_cnbc_chart_data
from libdb.models import (
    AISettings,
    AutomationRun,
    BrowserDocument,
    ManualTrade,
    PortfolioSnapshot,
    Position,
    User,
)
from libdb.session import async_session, engine
from libshared.config import settings
from libshared.constants import WHITELIST
from libshared.schemas import (
    BrowserCaptureProvider,
    OpportunityScanRunRequest,
    TradeProposalCreate,
    WeeklyReviewRunRequest,
)
from openai import APIConnectionError, APIStatusError
from sqlalchemy import select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.ai import generate_research, get_ai_settings, log_research, research_context
from core.services.browser_capture import build_capture_payload
from core.services.market_data import build_market_quote, fetch_yahoo_quotes
from core.services.paper import account_state, load_account, update_loss_baselines
from core.services.portfolio import build_snapshot_payload
from core.services.quote_refresh import build_quote_refresh_payload
from core.services.review import (
    create_opportunity_scan,
    create_weekly_review,
    serialize_opportunity_scan,
    serialize_weekly_review,
)
from core.services.trading import create_trade_proposal

logger = logging.getLogger(__name__)


async def enqueue(
    session: AsyncSession,
    kind: str,
    user_id: UUID,
    period: str | None = None,
    request: dict | None = None,
    *,
    scheduled: bool = False,
) -> AutomationRun:
    if not settings.background_jobs_enabled:
        raise HTTPException(status_code=503, detail="Background jobs are disabled")
    period = period or str(uuid4())
    if not scheduled:
        lock = int.from_bytes(
            hashlib.sha256(f"{kind}:{user_id}".encode()).digest()[:8], "big", signed=True
        )
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
        active_query = select(AutomationRun)
        if kind == "capture":
            active_query = active_query.where(
                AutomationRun.request["symbol"].astext == (request or {}).get("symbol")
            )
        active = await session.scalar(
            active_query.where(
                AutomationRun.user_id == user_id,
                AutomationRun.kind == kind,
                AutomationRun.status.in_(["queued", "running"]),
            ).limit(1)
        )
        if active is not None:
            raise HTTPException(
                status_code=409, detail=f"A {kind} job is already queued or running"
            )
    statement = insert(AutomationRun).values(
        user_id=user_id, kind=kind, period=period, request=request or {}, status="queued"
    )
    statement = statement.on_conflict_do_nothing(
        index_elements=["user_id", "kind", "period"]
    ).returning(AutomationRun.id)
    job_id = await session.scalar(statement)
    job = (
        await session.get(AutomationRun, job_id)
        if job_id
        else await session.scalar(
            select(AutomationRun).where(
                AutomationRun.user_id == user_id,
                AutomationRun.kind == kind,
                AutomationRun.period == period,
            )
        )
    )
    await session.commit()
    return job


@lru_cache(maxsize=1)
def market_calendar():
    return calendars.get_calendar("XNYS")


def scheduled_periods(now: datetime) -> list[tuple[str, str]]:
    # shortcut: monitoring uses US sessions, add per-exchange schedules for other markets.
    calendar = market_calendar()
    ny = now.astimezone(ZoneInfo("America/New_York"))
    warsaw = now.astimezone(ZoneInfo("Europe/Warsaw"))
    day = ny.date().isoformat()
    due = []
    if calendar.is_session(day):
        opened = calendar.session_open(day).to_pydatetime()
        closed = calendar.session_close(day).to_pydatetime()
        if opened <= now < closed:
            due.append(("hourly", ny.strftime("%Y-%m-%dT%H")))
        if closed + timedelta(minutes=15) <= now:
            due.append(("daily", day))
        if ny.weekday() in {0, 2, 4} and opened + timedelta(hours=1) <= now < closed:
            due.append(("scan", day))
    if warsaw.weekday() == 6 and warsaw.hour >= 18:
        due.append(("weekly", warsaw.date().isoformat()))
    return due


async def schedule_due(now: datetime) -> None:
    periods = scheduled_periods(now)
    if not periods:
        return
    async with async_session() as session:
        users = list(
            (
                await session.scalars(
                    select(AISettings.user_id)
                    .join(User)
                    .where(
                        AISettings.automation_enabled.is_(True),
                        User.is_active.is_(True),
                        User.role == "owner",
                    )
                )
            ).all()
        )
        for user_id in users:
            for kind, period in periods:
                await enqueue(session, kind, user_id, period, scheduled=True)


async def refresh_quotes(session: AsyncSession, symbols: list[str]) -> dict:
    quotes, failed = await fetch_yahoo_quotes(sorted(set(symbols)), delay_seconds=2)
    for quote in quotes:
        session.add(build_market_quote(quote))
    await session.commit()
    return {"symbols": symbols, "stored_count": len(quotes), "failed_symbols": failed}


async def process_job(job_id: UUID) -> None:
    async with async_session() as session:
        job = await session.get(AutomationRun, job_id)
        owner = await session.get(User, job.user_id)
        if owner is None or not owner.is_active or owner.role != "owner":
            raise HTTPException(status_code=403, detail="Owner access required")
        config = await get_ai_settings(session, job.user_id)
        await session.commit()
        kind = job.kind
        if kind in {"hourly", "daily", "weekly", "scan"} and not config.automation_enabled:
            job.status = "cancelled"
            await session.commit()
            return
        if kind == "capture":
            result = await capture_cnbc_chart_data(symbol=job.request["symbol"])
            document_id = str(uuid4())
            document = {
                **(result.document or {}),
                "captured_at": datetime.now(UTC).isoformat(),
                "observations": [asdict(item) for item in result.observations],
                "warnings": result.warnings,
            }
            session.add(
                BrowserDocument(
                    id=document_id, provider="cnbc", symbol=result.symbol, document=document
                )
            )
            job.payload = build_capture_payload(
                task_id=str(job.id),
                provider=BrowserCaptureProvider.CNBC,
                symbol=result.symbol,
                status="completed",
                document_id=document_id,
            )
        elif kind == "quotes":
            result = await refresh_quotes(session, job.request["symbols"])
            job.payload = build_quote_refresh_payload(
                task_id=str(job.id),
                provider="yahoo",
                requested_symbols=job.request["symbols"],
                status="completed",
                stored_count=result["stored_count"],
                failed_symbols=result["failed_symbols"],
            )
        elif (
            job.payload is None
            or "model" not in job.payload
            and kind in {"weekly", "daily", "scan", "proposal", "commentary"}
        ):
            account = await load_account(session, job.user_id)
            state = await account_state(session, account)
            personal_symbols = list(
                (
                    await session.scalars(
                        select(Position.ticker).where(Position.user_id == job.user_id)
                    )
                ).all()
            )
            symbols = personal_symbols + [position.ticker for position in state.positions]
            if kind in {"proposal", "scan"}:
                symbols += WHITELIST
            await session.commit()
            refresh = await refresh_quotes(session, symbols)
            context = await research_context(session, job.user_id)
            account = await load_account(session, job.user_id)
            if context["paper"]["equity"] is not None:
                update_loss_baselines(account, context["paper"]["equity"], datetime.now(UTC))
            await session.commit()
            if kind == "hourly":
                from core.routers.portfolio import portfolio_risk

                risk = await portfolio_risk(session=session, user_id=job.user_id)
                prices = {
                    ticker: quote
                    for ticker, quote in context["quotes"].items()
                    if ticker in symbols
                }
                previous = await session.scalar(
                    select(AutomationRun)
                    .where(
                        AutomationRun.user_id == job.user_id,
                        AutomationRun.kind == "hourly",
                        AutomationRun.status == "completed",
                        AutomationRun.id != job.id,
                    )
                    .order_by(AutomationRun.created_at.desc())
                    .limit(1)
                )
                moves = movement_warnings(
                    (previous.payload or {}).get("prices", {}) if previous else {}, prices
                )
                unavailable = [
                    f"Quote refresh failed for {ticker}" for ticker in refresh["failed_symbols"]
                ]
                stale = [
                    f"Stale quote for {ticker}"
                    for ticker, quote in prices.items()
                    if not quote["fresh"]
                ]
                job.payload = {
                    "warnings": sorted(
                        set(
                            risk.warnings
                            + context["paper"]["warnings"]
                            + moves
                            + unavailable
                            + stale
                        )
                    ),
                    "prices": prices,
                    "refresh": refresh,
                }
            elif kind == "weekly":
                if not job.request.get("review"):
                    review = await create_weekly_review(
                        session, WeeklyReviewRunRequest(), user_id=job.user_id, commit=False
                    )
                    job.request = {
                        **job.request,
                        "review": serialize_weekly_review(review).model_dump(mode="json"),
                    }
                    await session.commit()
                result = await generate_research(
                    {**context, "weekly_review": job.request["review"]}, config, "commentary"
                )
                log_research(session, job.user_id, context, result, "commentary")
                job.payload = {
                    **result,
                    "review_id": job.request["review"]["id"],
                    "refresh": refresh,
                }
            else:
                if kind == "daily" and not job.request.get("snapshot_id"):
                    from core.routers.portfolio import _build_quote_map_with_capture_fallback

                    positions = list(
                        (
                            await session.scalars(
                                select(Position).where(
                                    Position.user_id == job.user_id,
                                    Position.account_type == "personal",
                                )
                            )
                        ).all()
                    )
                    trades = list(
                        (
                            await session.scalars(
                                select(ManualTrade)
                                .where(
                                    ManualTrade.user_id == job.user_id,
                                    ManualTrade.account_type == "personal",
                                )
                                .order_by(ManualTrade.executed_at)
                            )
                        ).all()
                    )
                    quotes = await _build_quote_map_with_capture_fallback(positions, session)
                    total, details, allocation, risk = await build_snapshot_payload(
                        positions, quotes, trades=trades
                    )
                    snapshot = PortfolioSnapshot(
                        user_id=job.user_id,
                        account_type="personal",
                        total_value=total,
                        currency=risk.currency,
                        positions=details,
                        allocation=allocation,
                        risk_summary=risk.model_dump(),
                    )
                    session.add(snapshot)
                    await session.flush()
                    job.request = {
                        **job.request,
                        "snapshot_id": str(snapshot.id),
                        "snapshot": {
                            "value": total,
                            "currency": risk.currency,
                            "risk": risk.model_dump(),
                        },
                    }
                    await session.commit()
                if kind == "daily":
                    context["snapshot"] = job.request["snapshot"]
                if kind == "scan":
                    if not job.request.get("scan"):
                        scan = await create_opportunity_scan(
                            session,
                            OpportunityScanRunRequest(tickers=WHITELIST, cadence="mwf"),
                            user_id=job.user_id,
                            commit=False,
                        )
                        job.request = {
                            **job.request,
                            "scan": serialize_opportunity_scan(scan).model_dump(mode="json"),
                        }
                        await session.commit()
                    context["scan"] = job.request["scan"]
                proposal_enabled = (
                    kind == "proposal"
                    or kind == "scan"
                    and config.proposals_enabled
                    and account.status == "active"
                )
                result = await generate_research(
                    context, config, "proposal" if proposal_enabled else "commentary"
                )
                log_research(
                    session,
                    job.user_id,
                    context,
                    result,
                    "proposal" if proposal_enabled else "commentary",
                )
                job.payload = {**result, "refresh": refresh}
                if result.get("proposal"):
                    # Store the provider output before creating a proposal so notification retries do not rerun AI.
                    await session.commit()
        if job.payload and job.payload.get("proposal") and not job.payload.get("proposal_id"):
            data = TradeProposalCreate.model_validate(job.payload["proposal"])
            proposal = await create_trade_proposal(session, data, user_id=job.user_id, commit=False)
            job.payload = {**job.payload, "proposal_id": str(proposal.id)}
        await session.commit()
        await deliver_notification(session, job)
        job.status = "completed"
        job.error = None
        await session.commit()


async def deliver_notification(session: AsyncSession, job: AutomationRun) -> None:
    if job.notification_sent or job.kind in {"commentary", "proposal", "quotes", "capture"}:
        return
    payload = job.payload or {}
    if job.kind == "hourly":
        warnings = payload.get("warnings", [])
        previous = await session.scalar(
            select(AutomationRun)
            .where(
                AutomationRun.user_id == job.user_id,
                AutomationRun.kind == "hourly",
                AutomationRun.id != job.id,
                AutomationRun.status == "completed",
            )
            .order_by(AutomationRun.created_at.desc())
            .limit(1)
        )
        if not warnings or previous and (previous.payload or {}).get("warnings") == warnings:
            return
        message = "EchoTrade risk alerts\n" + "\n".join(warnings)
        webhook = settings.discord_webhook_alerts
    else:
        message = f"EchoTrade {job.kind}\n" + (
            payload.get("commentary") or payload.get("reason") or "Research completed"
        )
        webhook = (
            settings.discord_webhook_proposals
            if payload.get("proposal_id")
            else settings.discord_webhook_daily
        )
    if not webhook:
        return
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            webhook, json={"content": message[:1900], "allowed_mentions": {"parse": []}}
        )
        response.raise_for_status()
    # shortcut: a crash between Discord acceptance and this commit can duplicate a notification.
    job.notification_sent = True
    await session.commit()


def movement_warnings(previous: dict, current: dict) -> list[str]:
    warnings = []
    for ticker, quote in current.items():
        before = previous.get(ticker)
        if (
            not before
            or not quote["fresh"]
            or not before.get("fresh")
            or quote["currency"] != before["currency"]
        ):
            continue
        if before["price"] > 0:
            change = (quote["price"] / before["price"] - 1) * 100
            if abs(change) >= 5:
                warnings.append(
                    f"{ticker} moved {change:+.2f}% since the previous monitoring check"
                )
    return warnings


async def background_loop() -> None:
    while True:
        try:
            async with engine.connect() as connection:
                acquired = await connection.scalar(text("SELECT pg_try_advisory_lock(794619103)"))
                await connection.commit()
                if not acquired:
                    await asyncio.sleep(30)
                    continue
                try:
                    async with async_session() as session:
                        await session.execute(
                            update(AutomationRun)
                            .where(AutomationRun.status == "running")
                            .values(status="queued")
                        )
                        await session.commit()
                    while True:
                        await schedule_due(datetime.now(UTC))
                        async with async_session() as session:
                            job = await session.scalar(
                                select(AutomationRun)
                                .where(
                                    AutomationRun.status == "queued",
                                    AutomationRun.available_at
                                    <= datetime.now(UTC).replace(tzinfo=None),
                                )
                                .order_by(AutomationRun.created_at)
                                .with_for_update(skip_locked=True)
                                .limit(1)
                            )
                            if job is None:
                                await asyncio.sleep(10)
                                continue
                            job.status = "running"
                            job.attempts += 1
                            job_id = job.id
                            await session.commit()
                        try:
                            await asyncio.wait_for(process_job(job_id), timeout=300)
                        except Exception as exc:
                            retryable = (
                                isinstance(
                                    exc,
                                    (
                                        httpx.TransportError,
                                        asyncio.TimeoutError,
                                        APIConnectionError,
                                    ),
                                )
                                or isinstance(exc, (httpx.HTTPStatusError, APIStatusError))
                                and (
                                    exc.response.status_code == 429
                                    or exc.response.status_code >= 500
                                )
                            )
                            async with async_session() as session:
                                failed = await session.get(AutomationRun, job_id)
                                failed.status = (
                                    "queued" if retryable and failed.attempts < 3 else "failed"
                                )
                                failed.error = (
                                    str(exc.detail)
                                    if isinstance(exc, HTTPException)
                                    else f"{type(exc).__name__}: background job failed"
                                )
                                if isinstance(exc, LensCaptureError):
                                    failed.payload = build_capture_payload(
                                        task_id=str(failed.id),
                                        provider=BrowserCaptureProvider.CNBC,
                                        symbol=failed.request["symbol"],
                                        status="failed",
                                        error=str(exc),
                                        error_stage=exc.stage,
                                        error_code=exc.code,
                                        retryable=exc.retryable,
                                        error_details=exc.details,
                                    )
                                    failed.error = str(exc)
                                failed.available_at = (
                                    datetime.now(UTC) + timedelta(seconds=30 * failed.attempts)
                                ).replace(tzinfo=None)
                                await session.commit()
                            logger.warning(
                                "Background job %s failed (%s)", job_id, type(exc).__name__
                            )
                finally:
                    await connection.execute(text("SELECT pg_advisory_unlock(794619103)"))
                    await connection.commit()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background queue unavailable")
            await asyncio.sleep(30)
