from __future__ import annotations

from fastapi import APIRouter
from libdb.models import AutomationRun
from libshared.schemas import AISettingsOut, AISettingsUpdate, AutomationRunOut
from sqlalchemy import select

from core.routers.trading_dependencies import OwnerIdDependency, SessionDependency, UserIdDependency
from core.services.ai import get_ai_settings, serialize_settings
from core.services.jobs import enqueue

router = APIRouter()


@router.get("/ai/settings", response_model=AISettingsOut)
async def ai_settings(session: SessionDependency, user_id: UserIdDependency):
    config = await get_ai_settings(session, user_id)
    result = serialize_settings(config)
    await session.commit()
    return result


@router.put("/ai/settings", response_model=AISettingsOut)
async def update_ai_settings(
    data: AISettingsUpdate, session: SessionDependency, user_id: OwnerIdDependency
):
    config = await get_ai_settings(session, user_id)
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    await session.commit()
    return serialize_settings(config)


@router.post("/ai/commentary", response_model=AutomationRunOut, status_code=202)
async def commentary(session: SessionDependency, user_id: OwnerIdDependency):
    return await enqueue(session, "commentary", user_id)


@router.post("/ai/proposal", response_model=AutomationRunOut, status_code=202)
async def proposal(session: SessionDependency, user_id: OwnerIdDependency):
    return await enqueue(session, "proposal", user_id)


@router.get("/automation/runs", response_model=list[AutomationRunOut])
async def runs(session: SessionDependency, user_id: UserIdDependency):
    return list(
        (
            await session.scalars(
                select(AutomationRun)
                .where(AutomationRun.user_id == user_id)
                .order_by(AutomationRun.created_at.desc())
                .limit(50)
            )
        ).all()
    )
