from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from guard.evaluator import evaluate_hard_rules
from libdb.models import (
    AgentDecision,
    ExecutedTrade,
    MarketQuote,
    PostTradeReview,
    RiskCheck,
    RiskRule,
    TradeProposal,
    TradingBudget,
)
from libshared.config import settings
from libshared.constants import RISK_RULES
from libshared.schemas import (
    AccountType,
    Currency,
    ExecutedTradeOut,
    OrderType,
    PaperTradingStatusOut,
    ProposalStatus,
    RiskCheckOut,
    RiskCheckResult,
    TradeAction,
    TradeProposalCreate,
    TradeProposalOut,
    TradeProposalSource,
    TradingStatus,
)
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession


def _as_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _serialize_sources(
    data: list[TradeProposalSource] | list[dict[str, str | None]] | None,
) -> list[dict[str, str | None]] | None:
    if data is None:
        return None
    serialized: list[dict[str, str | None]] = []
    for item in data:
        if isinstance(item, TradeProposalSource):
            serialized.append(item.model_dump())
        else:
            serialized.append(dict(item))
    return serialized


def _source_models(data: list[dict[str, str | None]] | None) -> list[TradeProposalSource] | None:
    if data is None:
        return None
    return [TradeProposalSource.model_validate(item) for item in data]


def serialize_trade_proposal(proposal: TradeProposal) -> TradeProposalOut:
    return TradeProposalOut(
        id=proposal.id,
        created_at=proposal.created_at,
        account_type=AccountType(proposal.account_type),
        ticker=proposal.ticker,
        action=TradeAction(proposal.action),
        amount=_as_float(proposal.amount),
        currency=Currency(proposal.currency),
        order_type=OrderType(proposal.order_type),
        limit_price=None if proposal.limit_price is None else _as_float(proposal.limit_price),
        reason=proposal.reason,
        thesis=proposal.thesis,
        risks=proposal.risks,
        invalidated_if=proposal.invalidated_if,
        expected_holding_period=proposal.expected_holding_period,
        review_date=proposal.review_date,
        confidence=None if proposal.confidence is None else _as_float(proposal.confidence),
        used_browser_context=proposal.used_browser_context,
        sources=proposal.sources,
        status=ProposalStatus(proposal.status),
    )


def serialize_risk_check(risk_check: RiskCheck) -> RiskCheckOut:
    return RiskCheckOut(
        id=risk_check.id,
        proposal_id=risk_check.proposal_id,
        created_at=risk_check.created_at,
        passed=risk_check.passed,
        failed_rules=list(risk_check.failed_rules or []),
        warnings=list(risk_check.warnings or []),
        position_size_after_trade=(
            None
            if risk_check.position_size_after_trade is None
            else _as_float(risk_check.position_size_after_trade)
        ),
        sector_exposure_after_trade=(
            None
            if risk_check.sector_exposure_after_trade is None
            else _as_float(risk_check.sector_exposure_after_trade)
        ),
        monthly_budget_remaining=(
            None
            if risk_check.monthly_budget_remaining is None
            else _as_float(risk_check.monthly_budget_remaining)
        ),
        daily_loss=None if risk_check.daily_loss is None else _as_float(risk_check.daily_loss),
        monthly_loss=None if risk_check.monthly_loss is None else _as_float(risk_check.monthly_loss),
        evaluator_summary=risk_check.evaluator_summary,
    )


def serialize_executed_trade(executed_trade: ExecutedTrade) -> ExecutedTradeOut:
    return ExecutedTradeOut(
        id=executed_trade.id,
        proposal_id=executed_trade.proposal_id,
        broker_order_id=executed_trade.broker_order_id,
        ticker=executed_trade.ticker,
        action=TradeAction(executed_trade.action),
        quantity=_as_float(executed_trade.quantity),
        price=_as_float(executed_trade.price),
        fees=_as_float(executed_trade.fees),
        currency=Currency(executed_trade.currency),
        status=executed_trade.status,
        executed_at=executed_trade.executed_at,
    )


async def get_or_create_budget(
    session: AsyncSession,
    *,
    user_id: UUID,
    account_type: AccountType = AccountType.EXPERIMENTAL,
) -> TradingBudget:
    month = _current_month()
    result = await session.execute(
        select(TradingBudget).where(
            TradingBudget.user_id == user_id,
            TradingBudget.account_type == account_type.value,
            TradingBudget.month == month,
        )
    )
    budget = result.scalar_one_or_none()
    if budget is not None:
        return budget

    budget = TradingBudget(
        user_id=user_id,
        account_type=account_type.value,
        month=month,
        starting_budget=settings.max_monthly_budget,
        used_budget=0,
        realized_pnl=0,
        unrealized_pnl=0,
        max_drawdown=0,
        status="active",
    )
    session.add(budget)
    await session.flush()
    return budget


async def create_trade_proposal(
    session: AsyncSession,
    data: TradeProposalCreate,
    *,
    user_id: UUID,
) -> TradeProposal:
    proposal = TradeProposal(
        user_id=user_id,
        account_type=data.account_type.value,
        ticker=data.ticker.strip().upper(),
        action=data.action.value,
        amount=data.amount,
        currency=data.currency.value,
        order_type=data.order_type.value,
        limit_price=data.limit_price,
        reason=data.reason,
        thesis=data.thesis,
        risks=data.risks,
        invalidated_if=data.invalidated_if,
        expected_holding_period=data.expected_holding_period,
        review_date=data.review_date,
        confidence=data.confidence,
        used_browser_context=data.used_browser_context,
        sources=_serialize_sources(data.sources),
        status=ProposalStatus.PENDING.value,
    )
    decision = AgentDecision(
        user_id=user_id,
        agent_name="EchoSignal",
        account_type=data.account_type.value,
        candidate_action=data.action.value,
        ticker=proposal.ticker,
        reasoning_summary=data.reason,
        confidence=data.confidence,
        risk_level=None,
        expected_horizon=data.expected_holding_period,
        final_decision="proposal_created",
    )
    session.add_all([proposal, decision])
    await session.commit()
    await session.refresh(proposal)
    return proposal


async def get_owned_proposal(session: AsyncSession, proposal_id: UUID, *, user_id: UUID) -> TradeProposal:
    proposal = await session.get(TradeProposal, proposal_id)
    if proposal is None or proposal.user_id != user_id:
        raise HTTPException(status_code=404, detail="Trade proposal not found")
    return proposal


def _proposal_to_create(proposal: TradeProposal) -> TradeProposalCreate:
    return TradeProposalCreate(
        account_type=AccountType(proposal.account_type),
        ticker=proposal.ticker,
        action=TradeAction(proposal.action),
        amount=_as_float(proposal.amount),
        currency=Currency(proposal.currency),
        order_type=OrderType(proposal.order_type),
        limit_price=None if proposal.limit_price is None else _as_float(proposal.limit_price),
        reason=proposal.reason,
        thesis=proposal.thesis,
        risks=list(proposal.risks or []),
        invalidated_if=proposal.invalidated_if,
        expected_holding_period=proposal.expected_holding_period,
        review_date=proposal.review_date,
        confidence=None if proposal.confidence is None else _as_float(proposal.confidence),
        used_browser_context=proposal.used_browser_context,
        sources=_source_models(proposal.sources),
    )


async def evaluate_trade_proposal(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    user_id: UUID,
) -> RiskCheck:
    proposal = await get_owned_proposal(session, proposal_id, user_id=user_id)
    if proposal.status == ProposalStatus.EXECUTED.value:
        raise HTTPException(status_code=409, detail="Executed proposals cannot be re-evaluated")

    budget = await get_or_create_budget(
        session,
        user_id=user_id,
        account_type=AccountType(proposal.account_type),
    )
    remaining_budget = _as_float(budget.starting_budget) - _as_float(budget.used_budget)
    result = evaluate_hard_rules(
        _proposal_to_create(proposal),
        monthly_budget_remaining=remaining_budget,
    )
    risk_check = _store_risk_check(result, proposal, user_id=user_id)
    proposal.status = (
        ProposalStatus.APPROVED.value if result.approved else ProposalStatus.REJECTED.value
    )
    session.add(risk_check)
    await session.commit()
    await session.refresh(risk_check)
    await session.refresh(proposal)
    return risk_check


def _store_risk_check(
    result: RiskCheckResult,
    proposal: TradeProposal,
    *,
    user_id: UUID,
) -> RiskCheck:
    return RiskCheck(
        user_id=user_id,
        proposal_id=proposal.id,
        passed=result.approved,
        failed_rules=result.failed_rules,
        warnings=result.warnings,
        position_size_after_trade=result.position_size_after_trade,
        sector_exposure_after_trade=result.sector_exposure_after_trade,
        monthly_budget_remaining=result.monthly_budget_remaining,
        daily_loss=result.daily_loss,
        monthly_loss=result.monthly_loss,
        evaluator_summary=result.summary,
    )


async def approve_trade_proposal(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    user_id: UUID,
) -> TradeProposal:
    proposal = await get_owned_proposal(session, proposal_id, user_id=user_id)
    if proposal.status == ProposalStatus.EXECUTED.value:
        raise HTTPException(status_code=409, detail="Executed proposals cannot be approved")
    risk_check = await _latest_risk_check(session, proposal.id, user_id=user_id)
    if risk_check is None or not risk_check.passed:
        raise HTTPException(status_code=409, detail="A passing risk check is required before approval")
    proposal.status = ProposalStatus.APPROVED.value
    await session.commit()
    await session.refresh(proposal)
    return proposal


async def reject_trade_proposal(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    user_id: UUID,
    reason: str | None = None,
) -> TradeProposal:
    proposal = await get_owned_proposal(session, proposal_id, user_id=user_id)
    if proposal.status == ProposalStatus.EXECUTED.value:
        raise HTTPException(status_code=409, detail="Executed proposals cannot be rejected")
    proposal.status = ProposalStatus.REJECTED.value
    session.add(
        AgentDecision(
            user_id=user_id,
            agent_name="EchoGuard",
            account_type=proposal.account_type,
            candidate_action=proposal.action,
            ticker=proposal.ticker,
            reasoning_summary=reason,
            confidence=None if proposal.confidence is None else _as_float(proposal.confidence),
            risk_level=None,
            expected_horizon=proposal.expected_holding_period,
            final_decision="proposal_rejected",
        )
    )
    await session.commit()
    await session.refresh(proposal)
    return proposal


async def execute_approved_paper_trade(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    user_id: UUID,
) -> ExecutedTrade:
    proposal = await get_owned_proposal(session, proposal_id, user_id=user_id)
    if proposal.status != ProposalStatus.APPROVED.value:
        raise HTTPException(status_code=409, detail="Only approved proposals can be paper executed")

    quote = await _latest_quote(session, proposal.ticker)
    if quote is None:
        raise HTTPException(status_code=409, detail="A stored quote is required for paper execution")

    budget = await get_or_create_budget(
        session,
        user_id=user_id,
        account_type=AccountType(proposal.account_type),
    )
    remaining_budget = _as_float(budget.starting_budget) - _as_float(budget.used_budget)
    proposal_amount = _as_float(proposal.amount)
    if proposal_amount > remaining_budget:
        raise HTTPException(status_code=409, detail="Monthly paper budget is exhausted")

    price = _as_float(quote.price)
    if price <= 0:
        raise HTTPException(status_code=409, detail="Latest quote price must be positive")

    executed_trade = ExecutedTrade(
        user_id=user_id,
        proposal_id=proposal.id,
        broker_order_id=None,
        ticker=proposal.ticker,
        action=proposal.action,
        quantity=proposal_amount / price,
        price=price,
        fees=0,
        currency=quote.currency,
        status="paper_filled",
    )
    proposal.status = ProposalStatus.EXECUTED.value
    budget.used_budget = _as_float(budget.used_budget) + proposal_amount
    if _as_float(budget.used_budget) >= _as_float(budget.starting_budget):
        budget.status = TradingStatus.BUDGET_EXHAUSTED.value

    session.add(executed_trade)
    await session.flush()
    if proposal.review_date is not None:
        session.add(
            PostTradeReview(
                user_id=user_id,
                trade_id=executed_trade.id,
                review_date=proposal.review_date,
            )
        )
    session.add(
        AgentDecision(
            user_id=user_id,
            agent_name="EchoBot",
            account_type=proposal.account_type,
            candidate_action=proposal.action,
            ticker=proposal.ticker,
            reasoning_summary="Approved paper proposal executed with stored quote",
            confidence=None if proposal.confidence is None else _as_float(proposal.confidence),
            risk_level=None,
            expected_horizon=proposal.expected_holding_period,
            final_decision="paper_executed",
        )
    )
    await session.commit()
    await session.refresh(executed_trade)
    return executed_trade


async def _latest_quote(session: AsyncSession, ticker: str) -> MarketQuote | None:
    result = await session.execute(
        select(MarketQuote)
        .where(MarketQuote.symbol == ticker)
        .order_by(MarketQuote.received_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _latest_risk_check(
    session: AsyncSession,
    proposal_id: UUID,
    *,
    user_id: UUID,
) -> RiskCheck | None:
    result = await session.execute(
        select(RiskCheck)
        .where(RiskCheck.proposal_id == proposal_id, RiskCheck.user_id == user_id)
        .order_by(RiskCheck.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def build_trader_status(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> PaperTradingStatusOut:
    budget = await get_or_create_budget(session, user_id=user_id)
    pending_count = await _count_proposals(session, user_id, ProposalStatus.PENDING)
    approved_count = await _count_proposals(session, user_id, ProposalStatus.APPROVED)
    executed_count_result = await session.execute(
        select(func.count(ExecutedTrade.id)).where(ExecutedTrade.user_id == user_id)
    )
    executed_count = int(executed_count_result.scalar_one() or 0)
    last_trade_result = await session.execute(
        select(ExecutedTrade)
        .where(ExecutedTrade.user_id == user_id)
        .order_by(ExecutedTrade.executed_at.desc())
        .limit(1)
    )
    last_trade = last_trade_result.scalar_one_or_none()
    used_budget = _as_float(budget.used_budget)
    max_budget = _as_float(budget.starting_budget)
    return PaperTradingStatusOut(
        status=TradingStatus(budget.status),
        monthly_budget_remaining=max(max_budget - used_budget, 0.0),
        monthly_budget_used=used_budget,
        max_monthly_budget=max_budget,
        daily_trades_remaining=settings.max_daily_trades,
        pending_proposals=pending_count,
        approved_proposals=approved_count,
        executed_trades=executed_count,
        last_trade_at=None if last_trade is None else last_trade.executed_at,
    )


async def _count_proposals(
    session: AsyncSession,
    user_id: UUID,
    status: ProposalStatus,
) -> int:
    result = await session.execute(
        select(func.count(TradeProposal.id)).where(
            TradeProposal.user_id == user_id,
            TradeProposal.status == status.value,
        )
    )
    return int(result.scalar_one() or 0)


async def list_risk_rules(session: AsyncSession, *, user_id: UUID) -> list[dict[str, Any]]:
    result = await session.execute(
        select(RiskRule).where(or_(RiskRule.user_id == user_id, RiskRule.user_id.is_(None)))
    )
    configured = {rule.name: rule for rule in result.scalars().all()}
    rules: list[dict[str, Any]] = []
    for name in RISK_RULES:
        rule = configured.get(name)
        rules.append(
            {
                "name": name,
                "enabled": True if rule is None else rule.enabled,
                "value": {} if rule is None else rule.value,
                "source": "default" if rule is None else "configured",
            }
        )
    return rules
