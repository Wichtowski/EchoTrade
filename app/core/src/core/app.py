"""EchoCore FastAPI application."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from libdb.models import Base
from libdb.session import engine
from libshared.config import settings
from sqlalchemy import text
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from core.routers import (
    auth,
    automation,
    investment_plans,
    market,
    portfolio,
    positions,
    reviews,
    trades,
    trading,
)
from core.services.auth import require_app_access_dependency


async def run_startup_repairs() -> None:
    # Local dev safety net for schema changes while we don't yet have Alembic migrations.
    statements = [
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS opened_at TIMESTAMP",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS broker TEXT NOT NULL DEFAULT 'XTB'",
        "ALTER TABLE positions ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS broker TEXT NOT NULL DEFAULT 'XTB'",
        "ALTER TABLE manual_trades ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE investment_plans ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE investment_plan_targets ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'PLN'",
        "ALTER TABLE investment_plan_targets ADD COLUMN IF NOT EXISTS composition_sectors JSONB",
        "ALTER TABLE portfolio_snapshots ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE weekly_reviews ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE opportunity_scans ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE trading_budgets ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE trading_budgets ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'experimental'",
        "ALTER TABLE trading_budgets ADD COLUMN IF NOT EXISTS paper_account_id UUID REFERENCES paper_accounts(user_id)",
        "ALTER TABLE agent_decisions ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE trade_proposals ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE trade_proposals ADD COLUMN IF NOT EXISTS account_type TEXT NOT NULL DEFAULT 'experimental'",
        "ALTER TABLE trade_proposals ADD COLUMN IF NOT EXISTS sources JSONB",
        "ALTER TABLE trade_proposals ADD COLUMN IF NOT EXISTS time_horizon TEXT NOT NULL DEFAULT 'medium_term'",
        "ALTER TABLE risk_checks ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE executed_trades ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE post_trade_reviews ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE risk_rules ADD COLUMN IF NOT EXISTS user_id UUID",
        "ALTER TABLE executed_trades ADD COLUMN IF NOT EXISTS paper_account_id UUID REFERENCES paper_accounts(user_id)",
        "ALTER TABLE executed_trades ADD COLUMN IF NOT EXISTS paper_sequence INTEGER",
        "CREATE UNIQUE INDEX IF NOT EXISTS paper_fill_proposal_unique ON executed_trades(proposal_id) WHERE paper_account_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS paper_fill_sequence_unique ON executed_trades(paper_account_id, paper_sequence) WHERE paper_account_id IS NOT NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS automation_run_period_unique ON automation_runs(user_id, kind, period)",
    ]
    async with engine.begin() as connection:
        for statement in statements:
            await connection.execute(text(statement))


@asynccontextmanager
async def lifespan(_: FastAPI):
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await run_startup_repairs()
    from core.services.jobs import background_loop

    task = asyncio.create_task(background_loop()) if settings.background_jobs_enabled else None
    try:
        yield
    finally:
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="EchoCore",
    version="0.1.0",
    description="EchoTrade backend API",
    lifespan=lifespan,
)

app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected_dependencies = [Depends(require_app_access_dependency)]

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(positions.router, prefix="/positions", tags=["positions"], dependencies=protected_dependencies)
app.include_router(trades.router, prefix="/trades", tags=["trades"], dependencies=protected_dependencies)
app.include_router(
    investment_plans.router,
    prefix="/investment-plans",
    tags=["investment-plans"],
    dependencies=protected_dependencies,
)
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"], dependencies=protected_dependencies)
app.include_router(market.router, prefix="/market", tags=["market"], dependencies=protected_dependencies)
app.include_router(reviews.router, prefix="/reviews", tags=["reviews"], dependencies=protected_dependencies)
app.include_router(trading.router, tags=["trading"], dependencies=protected_dependencies)
app.include_router(automation.router, tags=["automation"], dependencies=protected_dependencies)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": settings.app_version}
