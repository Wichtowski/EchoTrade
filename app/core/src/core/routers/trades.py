"""Manual trade journal router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.portfolio import sync_positions_from_manual_trades
from libdb.models import ManualTrade
from libdb.session import get_session
from libshared.schemas import ManualTradeCreate, ManualTradeOut, ManualTradeUpdate

router = APIRouter()


@router.get("/", response_model=list[ManualTradeOut])
async def list_trades(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[ManualTrade]:
    result = await session.execute(
        select(ManualTrade).where(ManualTrade.user_id == user_id).order_by(ManualTrade.executed_at.desc())
    )
    return list(result.scalars().all())


@router.post("/", response_model=ManualTradeOut, status_code=201)
async def create_trade(
    data: ManualTradeCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> ManualTrade:
    trade = ManualTrade(user_id=user_id, **data.model_dump(exclude_none=True))
    session.add(trade)
    await session.commit()
    await session.refresh(trade)
    await sync_positions_from_manual_trades(session, user_id=user_id)
    return trade


@router.get("/{trade_id}", response_model=ManualTradeOut)
async def get_trade(
    trade_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> ManualTrade:
    trade = await session.get(ManualTrade, trade_id)
    if trade is None or trade.user_id != user_id:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.patch("/{trade_id}", response_model=ManualTradeOut)
async def update_trade(
    trade_id: UUID,
    data: ManualTradeUpdate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> ManualTrade:
    trade = await session.get(ManualTrade, trade_id)
    if trade is None or trade.user_id != user_id:
        raise HTTPException(status_code=404, detail="Trade not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(trade, field, value)
    await session.commit()
    await session.refresh(trade)
    await sync_positions_from_manual_trades(session, user_id=user_id)
    return trade


@router.delete("/{trade_id}", status_code=204)
async def delete_trade(
    trade_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    trade = await session.get(ManualTrade, trade_id)
    if trade is None or trade.user_id != user_id:
        raise HTTPException(status_code=404, detail="Trade not found")
    await session.delete(trade)
    await session.commit()
    await sync_positions_from_manual_trades(session, user_id=user_id)
