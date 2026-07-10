"""SQLAlchemy ORM models for EchoTrade."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    average_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    broker: Mapped[str] = mapped_column(Text, nullable=False, default="XTB")
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class ManualTrade(Base):
    __tablename__ = "manual_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="personal")
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    broker: Mapped[str] = mapped_column(Text, nullable=False, default="XTB")
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    fees: Mapped[float] = mapped_column(Numeric, nullable=False, default=0)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(nullable=True)
    executed_at: Mapped[datetime] = mapped_column(default=func.now())
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class InvestmentPlan(Base):
    __tablename__ = "investment_plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="personal")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    broker: Mapped[str] = mapped_column(Text, nullable=False, default="XTB")
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="PLN")
    monthly_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    contribution_day: Mapped[int] = mapped_column(nullable=False, default=10)
    start_date: Mapped[datetime] = mapped_column(nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class InvestmentPlanTarget(Base):
    __tablename__ = "investment_plan_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, default="PLN")
    weight_pct: Mapped[float] = mapped_column(Numeric, nullable=False)
    sector: Mapped[str | None] = mapped_column(Text, nullable=True)
    composition_sectors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class InvestmentPlanPause(Base):
    __tablename__ = "investment_plan_pauses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=False
    )
    start_date: Mapped[datetime] = mapped_column(nullable=False)
    end_date: Mapped[datetime] = mapped_column(nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class InvestmentPlanAmountChange(Base):
    __tablename__ = "investment_plan_amount_changes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=False
    )
    effective_date: Mapped[datetime] = mapped_column(nullable=False)
    monthly_amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class InvestmentPlanOneOffContribution(Base):
    __tablename__ = "investment_plan_one_off_contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=False
    )
    contribution_date: Mapped[datetime] = mapped_column(nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    positions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    allocation: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    risk_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="personal")
    period_start: Mapped[datetime] = mapped_column(nullable=False)
    period_end: Mapped[datetime] = mapped_column(nullable=False)
    reporting_currency: Mapped[str] = mapped_column(Text, nullable=False)
    total_value: Mapped[float] = mapped_column(Numeric, nullable=False)
    total_value_change: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    trade_count: Mapped[int] = mapped_column(nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    insights: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class OpportunityScan(Base):
    __tablename__ = "opportunity_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="personal")
    cadence: Mapped[str] = mapped_column(Text, nullable=False, default="manual")
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investment_plans.id"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    tickers: Mapped[dict] = mapped_column(JSONB, nullable=False)
    candidates: Mapped[dict] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Invite(Base):
    __tablename__ = "invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="invited_viewer")
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)


class MarketQuote(Base):
    __tablename__ = "market_quotes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_timestamp: Mapped[datetime | None] = mapped_column(nullable=True)
    received_at: Mapped[datetime] = mapped_column(default=func.now())
    delay_seconds: Mapped[int | None] = mapped_column(nullable=True)
    confidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class MarketHistoryBar(Base):
    __tablename__ = "market_history_bars"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[str] = mapped_column(Text, nullable=False, default="W")
    bar_time: Mapped[datetime] = mapped_column(nullable=False)
    open_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    high_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    low_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    close_price: Mapped[float] = mapped_column(Numeric, nullable=False)
    volume: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="yahoo")
    captured_at: Mapped[datetime] = mapped_column(default=func.now())


class LensSnapshot(Base):
    __tablename__ = "lens_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    source: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    symbol: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    observations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    screenshots: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class TradingBudget(Base):
    __tablename__ = "trading_budgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="experimental")
    month: Mapped[str] = mapped_column(Text, nullable=False)
    starting_budget: Mapped[float] = mapped_column(Numeric, nullable=False)
    used_budget: Mapped[float] = mapped_column(Numeric, default=0)
    realized_pnl: Mapped[float] = mapped_column(Numeric, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric, default=0)
    max_drawdown: Mapped[float] = mapped_column(Numeric, default=0)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())


class AgentDecision(Base):
    __tablename__ = "agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    agent_name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type: Mapped[str] = mapped_column(Text, nullable=False)
    market_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    portfolio_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    browser_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    candidate_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_horizon: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_decision: Mapped[str] = mapped_column(Text, nullable=False)


class TradeProposal(Base):
    __tablename__ = "trade_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    account_type: Mapped[str] = mapped_column(Text, nullable=False, default="experimental")
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    order_type: Mapped[str] = mapped_column(Text, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    risks: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    invalidated_if: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_holding_period: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_date: Mapped[datetime | None] = mapped_column(nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    used_browser_context: Mapped[bool] = mapped_column(Boolean, default=False)
    sources: Mapped[list[dict[str, str | None]] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")


class RiskCheck(Base):
    __tablename__ = "risk_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    failed_rules: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    warnings: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    position_size_after_trade: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    sector_exposure_after_trade: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    monthly_budget_remaining: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    daily_loss: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    monthly_loss: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    evaluator_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExecutedTrade(Base):
    __tablename__ = "executed_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trade_proposals.id"), nullable=False
    )
    broker_order_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticker: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric, nullable=False)
    price: Mapped[float] = mapped_column(Numeric, nullable=False)
    fees: Mapped[float] = mapped_column(Numeric, default=0)
    currency: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(default=func.now())


class PostTradeReview(Base):
    __tablename__ = "post_trade_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("executed_trades.id"), nullable=False
    )
    review_date: Mapped[datetime] = mapped_column(nullable=False)
    price_after_1d: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    price_after_7d: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    price_after_30d: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    was_decision_good: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mistake_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())


class RiskRule(Base):
    __tablename__ = "risk_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
