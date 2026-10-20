from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from libdb.models import User
from libdb.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
UserIdDependency = Annotated[UUID, Depends(request_user_id_dependency)]


async def trading_owner(user_id: UserIdDependency, session: SessionDependency) -> UUID:
    user = await session.get(User, user_id)
    if user is None or not user.is_active or user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user_id


OwnerIdDependency = Annotated[UUID, Depends(trading_owner)]
