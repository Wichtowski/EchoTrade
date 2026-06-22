"""Authentication and invite management router."""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import (
    authenticate_user,
    build_invite_url,
    create_invite,
    create_invited_user,
    create_session_for_user,
    get_optional_current_user,
    get_user_by_email,
    get_valid_invite_by_token,
    has_any_users,
    invite_email_enabled,
    InviteDeliveryResult,
    normalize_email,
    require_current_user,
    require_owner_user,
    revoke_invite,
    revoke_session_by_token,
    send_invite_email,
    serialize_invite,
    serialize_user,
    session_cookie_value,
)
from libdb.models import Invite
from libdb.session import get_session
from libshared.config import settings
from libshared.schemas import (
    AuthStatusOut,
    InviteAcceptRequest,
    InviteCreate,
    InviteDeliveryState,
    InviteOut,
    LoginRequest,
    UserRole,
    UserOut,
)

router = APIRouter()


def _set_session_cookie(response: Response, session_token: str) -> None:
    response.set_cookie(
        key=settings.auth_session_cookie_name,
        value=session_token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_hours * 60 * 60,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
    )


@router.get("/status", response_model=AuthStatusOut)
async def auth_status(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> AuthStatusOut:
    authenticated = await get_optional_current_user(session, session_cookie)
    return AuthStatusOut(
        has_users=await has_any_users(session),
        authenticated=authenticated is not None,
    )


@router.post("/login", response_model=UserOut)
async def login(
    data: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    user = await authenticate_user(session, email=data.email, password=data.password)
    _, session_token = await create_session_for_user(session, user=user)
    _set_session_cookie(response, session_token)
    return serialize_user(user)


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> None:
    if session_cookie:
        await revoke_session_by_token(session, session_cookie)
    _clear_session_cookie(response)


@router.get("/me", response_model=UserOut)
async def me(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> UserOut:
    user = await require_current_user(session, session_cookie)
    return serialize_user(user)


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> list[InviteOut]:
    owner = await require_owner_user(session, session_cookie)
    result = await session.execute(
        select(Invite)
        .where(Invite.created_by_user_id == owner.id)
        .order_by(Invite.created_at.desc())
        .limit(50)
    )
    return [serialize_invite(invite) for invite in result.scalars().all()]


@router.post("/invites", response_model=InviteOut, status_code=201)
async def create_user_invite(
    data: InviteCreate,
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> InviteOut:
    owner = await require_owner_user(session, session_cookie)
    if data.role != UserRole.INVITED_VIEWER:
        raise HTTPException(status_code=400, detail="Only invited viewer accounts can be created by invite")
    invite, raw_token = await create_invite(
        session,
        created_by_user_id=owner.id,
        email=data.email,
        role=data.role.value,
        expires_in_hours=data.expires_in_hours,
    )
    delivery_result = InviteDeliveryResult(state=InviteDeliveryState.LINK_ONLY)
    if invite.email and invite_email_enabled():
        try:
            await asyncio.to_thread(
                send_invite_email,
                recipient_email=invite.email,
                invite_url=build_invite_url(raw_token),
                invited_by=owner.display_name or owner.email,
            )
            delivery_result = InviteDeliveryResult(state=InviteDeliveryState.SENT)
        except Exception as exc:
            delivery_result = InviteDeliveryResult(
                state=InviteDeliveryState.FAILED,
                error=str(exc),
            )
    return serialize_invite(invite, raw_token=raw_token, delivery_result=delivery_result)


@router.post("/invites/{invite_id}/revoke", response_model=InviteOut)
async def revoke_user_invite(
    invite_id: UUID,
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> InviteOut:
    owner = await require_owner_user(session, session_cookie)
    invite = await revoke_invite(session, invite_id=invite_id, owner_user_id=owner.id)
    return serialize_invite(invite)


@router.post("/invites/accept", response_model=UserOut, status_code=201)
async def accept_invite(
    data: InviteAcceptRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    invite = await get_valid_invite_by_token(session, data.token)
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite is invalid or expired")
    normalized_email = normalize_email(data.email)
    if invite.email is not None and invite.email != normalized_email:
        raise HTTPException(status_code=403, detail="Invite email does not match")
    existing = await get_user_by_email(session, normalized_email)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Email is already registered")

    user = await create_invited_user(
        session,
        invite=invite,
        email=normalized_email,
        password=data.password,
        display_name=data.display_name,
    )
    _, session_token = await create_session_for_user(session, user=user)
    _set_session_cookie(response, session_token)
    return serialize_user(user)
