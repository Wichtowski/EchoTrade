"""EchoLedger journal service — stores and queries all decisions and trades."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libdb.models import AgentDecision, ExecutedTrade, TradeProposal


async def log_decision(session: AsyncSession, decision_data: dict) -> AgentDecision:
    """Log an agent decision (including no-trade decisions)."""
    decision = AgentDecision(**decision_data)
    session.add(decision)
    await session.commit()
    await session.refresh(decision)
    return decision


async def get_decisions(
    session: AsyncSession, limit: int = 50
) -> list[AgentDecision]:
    """Retrieve recent agent decisions."""
    result = await session.execute(
        select(AgentDecision).order_by(AgentDecision.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def get_trade_history(
    session: AsyncSession, ticker: str | None = None, limit: int = 50
) -> list[ExecutedTrade]:
    """Retrieve executed trade history, optionally filtered by ticker."""
    stmt = select(ExecutedTrade).order_by(ExecutedTrade.executed_at.desc()).limit(limit)
    if ticker:
        stmt = stmt.where(ExecutedTrade.ticker == ticker)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_proposal(session: AsyncSession, proposal_id: UUID) -> TradeProposal | None:
    """Retrieve a single trade proposal."""
    return await session.get(TradeProposal, proposal_id)
