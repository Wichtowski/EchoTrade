"""Positions CRUD router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.portfolio import sync_positions_from_manual_trades
from libdb.models import Position
from libdb.session import get_session
from libshared.schemas import PositionCreate, PositionOut, PositionUpdate

router = APIRouter()


@router.get("/", response_model=list[PositionOut])
async def list_positions(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[Position]:
    result = await session.execute(select(Position).where(Position.user_id == user_id))
    return list(result.scalars().all())


@router.post("/", response_model=PositionOut, status_code=201)
async def create_position(
    data: PositionCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> Position:
    position = Position(user_id=user_id, **data.model_dump())
    session.add(position)
    await session.commit()
    await session.refresh(position)
    return position


@router.patch("/{position_id}", response_model=PositionOut)
async def update_position(
    position_id: UUID,
    data: PositionUpdate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> Position:
    position = await session.get(Position, position_id)
    if not position or position.user_id != user_id:
        raise HTTPException(status_code=404, detail="Position not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(position, field, value)
    await session.commit()
    await session.refresh(position)
    return position


@router.delete("/{position_id}", status_code=204)
async def delete_position(
    position_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    position = await session.get(Position, position_id)
    if not position or position.user_id != user_id:
        raise HTTPException(status_code=404, detail="Position not found")
    await session.delete(position)
    await session.commit()


@router.post("/sync-from-trades", response_model=list[PositionOut], status_code=201)
async def sync_positions(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[Position]:
    return await sync_positions_from_manual_trades(session, user_id=user_id)
