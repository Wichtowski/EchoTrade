"""Shared Pydantic schemas used across EchoTrade services."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class AccountType(str, Enum):
    PERSONAL = "personal"
    EXPERIMENTAL = "experimental"


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class ProposalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    EXPIRED = "expired"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimeHorizon(str, Enum):
    INTRADAY = "intraday"       # < 1 day
    SHORT_TERM = "short_term"   # 1–5 days
    MEDIUM_TERM = "medium_term" # 1–8 weeks
    LONG_TERM = "long_term"     # 2–6 months
    STRATEGIC = "strategic"     # > 6 months


class TradingStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    BUDGET_EXHAUSTED = "budget_exhausted"
    DRAWDOWN_LIMIT = "drawdown_limit"


class Currency(str, Enum):
    PLN = "PLN"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"


class Broker(str, Enum):
    XTB = "XTB"
    REVOLUT = "Revolut"


class BrowserCaptureProvider(str, Enum):
    CNBC = "cnbc"


class SavedQueryKind(str, Enum):
    BROWSER_CHART = "browser_chart"


class Sector(str, Enum):
    SEMIS = "semis"
    REAL_ESTATE = "real_estate"
    METALS = "metals"
    AI_INFRA = "ai_infra"
    SOFTWARE = "software"
    DEFENSE = "defense"
    BROAD_MARKET = "broad_market"
    ETFS = "etfs"
    INDUSTRIALS = "industrials"
    HEALTHCARE = "healthcare"
    ENERGY = "energy"
    FINANCIALS = "financials"
    CONSUMER = "consumer"
    OTHER = "other"


class UserRole(str, Enum):
    OWNER = "owner"
    INVITED_VIEWER = "invited_viewer"


class InviteDeliveryState(str, Enum):
    LINK_ONLY = "link_only"
    SENT = "sent"
    FAILED = "failed"


class PositionCreate(BaseModel):
    account_type: AccountType
    ticker: str
    quantity: float
    average_price: float
    broker: Broker
    currency: Currency = Currency.PLN
    sector: Sector | None = None
    thesis: str | None = None
    opened_at: datetime | None = None


class AuthStatusOut(BaseModel):
    has_users: bool
    authenticated: bool


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: UUID
    email: str
    display_name: str | None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    model_config = {"from_attributes": True}


class InviteCreate(BaseModel):
    email: str | None = None
    role: UserRole = UserRole.INVITED_VIEWER
    expires_in_hours: int = Field(default=168, ge=1, le=24 * 30)


class InviteOut(BaseModel):
    id: UUID
    email: str | None
    role: UserRole
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None
    invite_url: str | None = None
    delivery_state: InviteDeliveryState | None = None
    delivery_error: str | None = None

    model_config = {"from_attributes": True}


class InviteAcceptRequest(BaseModel):
    token: str = Field(min_length=16)
    email: str
    password: str = Field(min_length=12)
    display_name: str | None = None


class PositionUpdate(BaseModel):
    quantity: float | None = None
    average_price: float | None = None
    broker: Broker | None = None
    sector: Sector | None = None
    thesis: str | None = None
    opened_at: datetime | None = None


class PositionOut(BaseModel):
    id: UUID
    account_type: AccountType
    ticker: str
    quantity: float
    average_price: float
    broker: Broker
    currency: Currency
    sector: Sector | None
    thesis: str | None
    opened_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SavedQueryCreate(BaseModel):
    kind: SavedQueryKind
    name: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SavedQueryOut(BaseModel):
    id: str
    kind: SavedQueryKind
    name: str
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ManualTradeCreate(BaseModel):
    account_type: AccountType = AccountType.PERSONAL
    ticker: str
    action: TradeAction
    quantity: float = Field(gt=0)
    price: float = Field(gt=0)
    broker: Broker
    currency: Currency = Currency.PLN
    fees: float = 0
    sector: Sector | None = None
    thesis: str | None = None
    notes: str | None = None
    review_date: datetime | None = None
    executed_at: datetime | None = None


class ManualTradeUpdate(BaseModel):
    account_type: AccountType | None = None
    ticker: str | None = None
    action: TradeAction | None = None
    quantity: float | None = Field(default=None, gt=0)
    price: float | None = Field(default=None, gt=0)
    broker: Broker | None = None
    currency: Currency | None = None
    fees: float | None = None
    sector: Sector | None = None
    thesis: str | None = None
    notes: str | None = None
    review_date: datetime | None = None
    executed_at: datetime | None = None


class ManualTradeOut(BaseModel):
    id: UUID
    account_type: AccountType
    ticker: str
    action: TradeAction
    quantity: float
    price: float
    broker: Broker
    currency: Currency
    fees: float
    sector: Sector | None
    thesis: str | None
    notes: str | None
    review_date: datetime | None
    executed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentPlanCreate(BaseModel):
    account_type: AccountType = AccountType.PERSONAL
    name: str
    broker: Broker = Broker.XTB
    currency: Currency = Currency.PLN
    monthly_amount: float = Field(gt=0)
    contribution_day: int = Field(ge=1, le=31)
    start_date: date
    notes: str | None = None


class InvestmentPlanUpdate(BaseModel):
    account_type: AccountType | None = None
    name: str | None = None
    broker: Broker | None = None
    currency: Currency | None = None
    monthly_amount: float | None = Field(default=None, gt=0)
    contribution_day: int | None = Field(default=None, ge=1, le=31)
    start_date: date | None = None
    notes: str | None = None


class InvestmentPlanPauseCreate(BaseModel):
    start_date: date
    end_date: date
    reason: str | None = None


class InvestmentPlanPauseOut(BaseModel):
    id: UUID
    plan_id: UUID
    start_date: date
    end_date: date
    reason: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentPlanAmountChangeCreate(BaseModel):
    effective_date: date
    monthly_amount: float = Field(gt=0)
    note: str | None = None


class InvestmentPlanAmountChangeOut(BaseModel):
    id: UUID
    plan_id: UUID
    effective_date: date
    monthly_amount: float
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentPlanOneOffContributionCreate(BaseModel):
    contribution_date: date
    amount: float = Field(gt=0)
    note: str | None = None


class InvestmentPlanOneOffContributionOut(BaseModel):
    id: UUID
    plan_id: UUID
    contribution_date: date
    amount: float
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class InvestmentPlanTargetCreate(BaseModel):
    ticker: str
    currency: Currency = Currency.PLN
    weight_pct: float = Field(gt=0, le=100)
    sector: Sector | None = None
    composition_sectors: list[str] = Field(default_factory=list)
    notes: str | None = None


class InvestmentPlanTargetUpdate(BaseModel):
    ticker: str | None = None
    currency: Currency | None = None
    weight_pct: float | None = Field(default=None, gt=0, le=100)
    sector: Sector | None = None
    composition_sectors: list[str] | None = None
    notes: str | None = None


class InvestmentPlanTargetOut(BaseModel):
    id: UUID
    plan_id: UUID
    ticker: str
    currency: Currency
    weight_pct: float
    sector: Sector | None
    composition_sectors: list[str]
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InvestmentPlanOut(BaseModel):
    id: UUID
    account_type: AccountType
    name: str
    broker: Broker
    currency: Currency
    monthly_amount: float
    contribution_day: int
    start_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime
    next_run_on: date | None
    scheduled_contributions: int
    expected_contributions_total: float
    target_allocation_total: float
    targets: list[InvestmentPlanTargetOut]
    pauses: list[InvestmentPlanPauseOut] = Field(default_factory=list)
    amount_changes: list[InvestmentPlanAmountChangeOut] = Field(default_factory=list)
    one_off_contributions: list[InvestmentPlanOneOffContributionOut] = Field(default_factory=list)


class MarketQuoteOut(BaseModel):
    symbol: str
    price: float
    currency: Currency
    source: str
    source_timestamp: datetime | None
    received_at: datetime
    delay_seconds: int | None
    confidence: str | None
    warnings: list[str] | None

    model_config = {"from_attributes": True}


class MarketQuoteIngest(BaseModel):
    symbol: str
    price: float = Field(gt=0)
    currency: Currency = Currency.USD
    source: str = "manual"
    source_timestamp: datetime | None = None
    delay_seconds: int | None = None
    confidence: str | None = None
    warnings: list[str] | None = None


class MarketQuoteRefreshResult(BaseModel):
    requested_symbols: list[str]
    stored_quotes: list[MarketQuoteOut]
    provider: str
    failed_symbols: list[str] = []


class MarketQuoteRefreshTaskOut(BaseModel):
    task_id: str
    provider: str
    requested_symbols: list[str]
    status: str
    stored_count: int = 0
    failed_symbols: list[str] = []
    error: str | None = None
    updated_at: datetime | None = None


class MarketHistoryBarOut(BaseModel):
    symbol: str
    resolution: str
    bar_time: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float | None
    source: str
    captured_at: datetime

    model_config = {"from_attributes": True}


class MarketHistoryCaptureResult(BaseModel):
    symbol: str
    resolution: str
    started_at: datetime
    ended_at: datetime
    bars_written: int
    bars: list[MarketHistoryBarOut]
    source: str
    warnings: list[str] = []


class BrowserCaptureTaskOut(BaseModel):
    task_id: str
    symbol: str
    provider: BrowserCaptureProvider
    status: str
    time_ranges: list[str]
    document_id: str | None = None
    error: str | None = None
    error_stage: str | None = None
    error_code: str | None = None
    retryable: bool | None = None
    error_details: dict[str, str] | None = None
    updated_at: datetime | None = None


class BrowserCaptureDocumentOut(BaseModel):
    provider: BrowserCaptureProvider
    symbol: str
    document_id: str
    captured_at: str | None = None
    document: Any


class PortfolioSnapshotOut(BaseModel):
    id: UUID
    created_at: datetime
    account_type: AccountType
    total_value: float
    currency: Currency
    positions: Any
    allocation: Any | None
    risk_summary: Any | None

    model_config = {"from_attributes": True}


class PortfolioRiskOut(BaseModel):
    total_value: float
    currency: Currency
    ticker_allocation: dict[str, float]
    sector_allocation: dict[str, float]
    warnings: list[str]


class PortfolioPositionBreakdownOut(BaseModel):
    ticker: str
    quantity: float
    average_price: float
    current_price: float
    currency: Currency
    reporting_currency: Currency
    market_value: float
    market_value_native: float
    cost_basis_native: float
    cost_basis: float
    pnl_native: float
    pnl: float
    sector: str | None = None
    price_source: str | None = None
    fx_rate_to_reporting: float


class PortfolioOverviewOut(BaseModel):
    total_value: float
    currency: Currency
    positions: list[PortfolioPositionBreakdownOut]
    risk: PortfolioRiskOut


class TradeProposalSource(BaseModel):
    title: str
    url: str
    published_at: str | None = None
    source_type: str | None = None


class TradeProposalCreate(BaseModel):
    account_type: AccountType = AccountType.EXPERIMENTAL
    ticker: str
    action: TradeAction
    amount: float
    currency: Currency = Currency.PLN
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = None
    reason: str
    thesis: str | None = None
    risks: list[str] | None = None
    invalidated_if: str | None = None
    expected_holding_period: str | None = None
    review_date: datetime | None = None
    confidence: float | None = None
    used_browser_context: bool = False
    sources: list[TradeProposalSource] | None = None


class TradeProposalOut(BaseModel):
    id: UUID
    created_at: datetime
    account_type: AccountType
    ticker: str
    action: TradeAction
    amount: float
    currency: str
    order_type: OrderType
    limit_price: float | None
    reason: str
    thesis: str | None
    risks: Any | None
    invalidated_if: str | None
    expected_holding_period: str | None
    review_date: datetime | None
    confidence: float | None
    used_browser_context: bool
    sources: Any | None = None
    status: ProposalStatus

    model_config = {"from_attributes": True}


class TradeProposalDecisionRequest(BaseModel):
    reason: str | None = None


class RiskCheckResult(BaseModel):
    approved: bool
    risk_level: RiskLevel
    failed_rules: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str
    requires_manual_review: bool = False
    position_size_after_trade: float | None = None
    sector_exposure_after_trade: float | None = None
    monthly_budget_remaining: float | None = None
    daily_loss: float | None = None
    monthly_loss: float | None = None


class RiskEvaluateRequest(BaseModel):
    proposal_id: UUID


class RiskCheckOut(BaseModel):
    id: UUID
    proposal_id: UUID
    created_at: datetime
    passed: bool
    failed_rules: list[str]
    warnings: list[str]
    position_size_after_trade: float | None
    sector_exposure_after_trade: float | None
    monthly_budget_remaining: float | None
    daily_loss: float | None
    monthly_loss: float | None
    evaluator_summary: str | None


class ExecutedTradeOut(BaseModel):
    id: UUID
    proposal_id: UUID
    broker_order_id: str | None
    ticker: str
    action: TradeAction
    quantity: float
    price: float
    fees: float
    currency: Currency
    status: str
    executed_at: datetime

    model_config = {"from_attributes": True}


class TraderExecuteRequest(BaseModel):
    proposal_id: UUID


class PaperTradingStatusOut(BaseModel):
    status: TradingStatus
    mode: str = "paper"
    monthly_budget_remaining: float
    monthly_budget_used: float
    max_monthly_budget: float
    daily_trades_remaining: int
    pending_proposals: int
    approved_proposals: int
    executed_trades: int
    cooldown_until: datetime | None = None
    last_trade_at: datetime | None = None


class LensObservation(BaseModel):
    label: str
    value: str
    confidence: Confidence = Confidence.LOW


class LensSnapshotCreate(BaseModel):
    source: str
    url: str
    page_title: str | None = None
    symbol: str | None = None
    data_type: str
    raw_text: str | None = None
    observations: list[LensObservation] | None = None
    screenshots: list[str] | None = None
    confidence: Confidence = Confidence.LOW
    warnings: list[str] | None = None


class LensSnapshotOut(BaseModel):
    id: UUID
    created_at: datetime
    source: str
    url: str
    page_title: str | None
    symbol: str | None
    data_type: str
    observations: Any | None
    screenshots: Any | None
    confidence: str | None
    warnings: Any | None

    model_config = {"from_attributes": True}


class TraderStatusOut(BaseModel):
    status: TradingStatus
    monthly_budget_remaining: float | None = None
    daily_trades_remaining: int | None = None
    cooldown_until: datetime | None = None
    last_trade_at: datetime | None = None


class WeeklyReviewRunRequest(BaseModel):
    account_type: AccountType = AccountType.PERSONAL
    reporting_currency: Currency | None = None
    period_days: int = Field(default=7, ge=1, le=31)


class WeeklyReviewPositionInsight(BaseModel):
    ticker: str
    market_value: float
    pnl: float
    allocation_pct: float
    allocation_change_pct: float | None = None
    sector: str | None = None


class WeeklyReviewOut(BaseModel):
    id: UUID
    created_at: datetime
    account_type: AccountType
    period_start: datetime
    period_end: datetime
    reporting_currency: Currency
    total_value: float
    total_value_change: float | None
    trade_count: int
    buy_count: int
    sell_count: int
    top_winners: list[WeeklyReviewPositionInsight]
    top_losers: list[WeeklyReviewPositionInsight]
    concentration_changes: dict[str, float]
    due_review_tickers: list[str]
    warnings: list[str]
    summary: str
    insights: list[str]


class OpportunityScanRunRequest(BaseModel):
    account_type: AccountType = AccountType.PERSONAL
    plan_id: UUID | None = None
    tickers: list[str] = Field(default_factory=list)
    cadence: str = "manual"
    limit: int = Field(default=20, ge=1, le=50)


class OpportunityCandidateOut(BaseModel):
    ticker: str
    sector: str | None = None
    currency: Currency | None = None
    source: str
    held: bool
    has_fresh_quote: bool
    has_chart: bool
    latest_price: float | None = None
    market_value: float | None = None
    target_weight_pct: float | None = None
    thesis_due: bool = False
    score: float
    notes: list[str] = Field(default_factory=list)


class OpportunityScanOut(BaseModel):
    id: UUID
    created_at: datetime
    account_type: AccountType
    cadence: str
    plan_id: UUID | None
    candidate_count: int
    summary: str
    warnings: list[str]
    tickers: list[str]
    candidates: list[OpportunityCandidateOut]
