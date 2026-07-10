from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from libdb.models import TradeProposal
from libshared.schemas import (
    TradeProposalCreate,
    TradeProposalDecisionRequest,
    TradeProposalOut,
)
from sqlalchemy import select

from core.routers.trading_dependencies import SessionDependency, UserIdDependency
from core.services.trading import (
    approve_trade_proposal,
    create_trade_proposal,
    reject_trade_proposal,
    serialize_trade_proposal,
)

router = APIRouter()


@router.get("/trade-proposals", response_model=list[TradeProposalOut])
async def list_trade_proposals(
    session: SessionDependency,
    user_id: UserIdDependency,
) -> list[TradeProposalOut]:
    result = await session.execute(
        select(TradeProposal)
        .where(TradeProposal.user_id == user_id)
        .order_by(TradeProposal.created_at.desc())
        .limit(50)
    )
    return [serialize_trade_proposal(proposal) for proposal in result.scalars().all()]


@router.post("/trade-proposals", response_model=TradeProposalOut, status_code=201)
async def post_trade_proposal(
    data: TradeProposalCreate,
    session: SessionDependency,
    user_id: UserIdDependency,
) -> TradeProposalOut:
    proposal = await create_trade_proposal(session, data, user_id=user_id)
    return serialize_trade_proposal(proposal)


@router.post("/trade-proposals/{proposal_id}/approve", response_model=TradeProposalOut)
async def approve_proposal(
    proposal_id: UUID,
    session: SessionDependency,
    user_id: UserIdDependency,
) -> TradeProposalOut:
    proposal = await approve_trade_proposal(session, proposal_id, user_id=user_id)
    return serialize_trade_proposal(proposal)


@router.post("/trade-proposals/{proposal_id}/reject", response_model=TradeProposalOut)
async def reject_proposal(
    proposal_id: UUID,
    data: TradeProposalDecisionRequest,
    session: SessionDependency,
    user_id: UserIdDependency,
) -> TradeProposalOut:
    proposal = await reject_trade_proposal(session, proposal_id, user_id=user_id, reason=data.reason)
    return serialize_trade_proposal(proposal)
