from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from libshared.schemas import PaperTradingStatusOut, RiskCheckOut, RiskEvaluateRequest

from core.routers.trading_dependencies import SessionDependency, UserIdDependency
from core.services.trading import (
    build_trader_status,
    evaluate_trade_proposal,
    list_risk_rules,
    serialize_risk_check,
)

router = APIRouter()


@router.get("/risk/status", response_model=PaperTradingStatusOut)
async def risk_status(
    session: SessionDependency,
    user_id: UserIdDependency,
) -> PaperTradingStatusOut:
    return await build_trader_status(session, user_id=user_id)


@router.get("/risk/rules", response_model=list[dict[str, Any]])
async def risk_rules(
    session: SessionDependency,
    user_id: UserIdDependency,
) -> list[dict[str, Any]]:
    return await list_risk_rules(session, user_id=user_id)


@router.post("/risk/evaluate", response_model=RiskCheckOut, status_code=201)
async def risk_evaluate(
    data: RiskEvaluateRequest,
    session: SessionDependency,
    user_id: UserIdDependency,
) -> RiskCheckOut:
    risk_check = await evaluate_trade_proposal(session, data.proposal_id, user_id=user_id)
    return serialize_risk_check(risk_check)
