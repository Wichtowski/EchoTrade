from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from libdb.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency

SessionDependency = Annotated[AsyncSession, Depends(get_session)]
UserIdDependency = Annotated[UUID, Depends(request_user_id_dependency)]
