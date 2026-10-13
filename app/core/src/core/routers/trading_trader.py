from __future__ import annotations

from fastapi import APIRouter
from libshared.schemas import (
    ExecutedTradeOut,
    PaperAccountOut,
    PaperAccountUpdate,
    PaperTradingStatusOut,
    TraderExecuteRequest,
)

from core.routers.trading_dependencies import OwnerIdDependency, SessionDependency, UserIdDependency
from core.services.paper import account_state, load_account
from core.services.trading import (
    build_trader_status,
    execute_approved_paper_trade,
    serialize_executed_trade,
)

router = APIRouter()


@router.post("/trader/execute-approved", response_model=ExecutedTradeOut, status_code=201)
async def execute_approved_trade(
    data: TraderExecuteRequest,
    session: SessionDependency,
    user_id: OwnerIdDependency,
) -> ExecutedTradeOut:
    executed_trade = await execute_approved_paper_trade(session, data.proposal_id, user_id=user_id)
    return serialize_executed_trade(executed_trade)


@router.get("/trader/status", response_model=PaperTradingStatusOut)
async def trader_status(
    session: SessionDependency,
    user_id: UserIdDependency,
) -> PaperTradingStatusOut:
    return await build_trader_status(session, user_id=user_id)


@router.get("/paper/account", response_model=PaperAccountOut)
async def paper_account(session: SessionDependency, user_id: UserIdDependency):
    account = await load_account(session, user_id)
    result = await account_state(session, account)
    await session.commit()
    return result


@router.patch("/paper/account", response_model=PaperAccountOut)
async def update_paper_account(
    data: PaperAccountUpdate, session: SessionDependency, user_id: OwnerIdDependency
):
    account = await load_account(session, user_id)
    account.status = data.status
    result = await account_state(session, account)
    await session.commit()
    return result
