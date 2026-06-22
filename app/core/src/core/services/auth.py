"""Authentication helpers for EchoTrade."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import hashlib
import secrets
import smtplib
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from libdb.models import Invite, InvestmentPlan, InvestmentPlanAmountChange, InvestmentPlanOneOffContribution, InvestmentPlanPause, InvestmentPlanTarget, ManualTrade, OpportunityScan, PortfolioSnapshot, Position, User, UserSession, WeeklyReview
from libdb.session import get_session
from libshared.config import settings
from libshared.schemas import InviteDeliveryState, InviteOut, UserOut

password_hasher = PasswordHasher()


@dataclass
class AuthenticatedSession:
    user: User
    session: UserSession


@dataclass
class InviteDeliveryResult:
    state: InviteDeliveryState
    error: str | None = None


def normalize_email(value: str) -> str:
    return value.strip().lower()


def hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return password_hasher.check_needs_rehash(password_hash)


def issue_token() -> str:
    return secrets.token_urlsafe(32)


def utc_now() -> datetime:
    return datetime.now(UTC)


def session_expiry() -> datetime:
    return utc_now() + timedelta(hours=settings.auth_session_ttl_hours)


def invite_expiry(hours: int | None = None) -> datetime:
    ttl_hours = hours if hours is not None else settings.auth_invite_ttl_hours
    return utc_now() + timedelta(hours=ttl_hours)


def invite_email_enabled() -> bool:
    return bool(settings.smtp_host and settings.smtp_from_email)


async def has_any_users(session: AsyncSession) -> bool:
    result = await session.execute(select(func.count(User.id)))
    return bool(result.scalar_one())


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    result = await session.execute(select(User).where(User.email == normalize_email(email)))
    return result.scalar_one_or_none()


async def create_owner_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    user = User(
        email=normalize_email(email),
        display_name=display_name.strip() if display_name else None,
        password_hash=hash_password(password),
        role="owner",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await backfill_legacy_data_to_user(session, user.id)
    return user


async def create_invited_user(
    session: AsyncSession,
    *,
    invite: Invite,
    email: str,
    password: str,
    display_name: str | None,
) -> User:
    user = User(
        email=normalize_email(email),
        display_name=display_name.strip() if display_name else None,
        password_hash=hash_password(password),
        role=invite.role,
        is_active=True,
        invited_by_user_id=invite.created_by_user_id,
    )
    session.add(user)
    await session.flush()
    invite.accepted_at = utc_now().replace(tzinfo=None)
    invite.accepted_by_user_id = user.id
    await session.commit()
    await session.refresh(user)
    return user


async def backfill_legacy_data_to_user(session: AsyncSession, user_id: UUID) -> None:
    for model in [ManualTrade, Position, InvestmentPlan, PortfolioSnapshot, WeeklyReview, OpportunityScan]:
        result = await session.execute(select(model).where(model.user_id.is_(None)))  # type: ignore[arg-type]
        for row in result.scalars().all():
            row.user_id = user_id
    await session.commit()


async def create_session_for_user(
    session: AsyncSession,
    *,
    user: User,
) -> tuple[UserSession, str]:
    raw_token = issue_token()
    now = utc_now().replace(tzinfo=None)
    user_session = UserSession(
        user_id=user.id,
        token_hash=hash_secret(raw_token),
        expires_at=session_expiry().replace(tzinfo=None),
        last_seen_at=now,
    )
    user.last_login_at = now
    session.add(user_session)
    await session.commit()
    await session.refresh(user_session)
    await session.refresh(user)
    return user_session, raw_token


async def revoke_session_by_token(session: AsyncSession, raw_token: str) -> None:
    token_hash = hash_secret(raw_token)
    result = await session.execute(select(UserSession).where(UserSession.token_hash == token_hash))
    user_session = result.scalar_one_or_none()
    if user_session is None or user_session.revoked_at is not None:
        return
    user_session.revoked_at = utc_now().replace(tzinfo=None)
    await session.commit()


async def get_valid_invite_by_token(session: AsyncSession, token: str) -> Invite | None:
    token_hash = hash_secret(token)
    now = utc_now().replace(tzinfo=None)
    query: Select[tuple[Invite]] = select(Invite).where(
        Invite.token_hash == token_hash,
        Invite.revoked_at.is_(None),
        Invite.accepted_at.is_(None),
        Invite.expires_at > now,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_invite(
    session: AsyncSession,
    *,
    created_by_user_id,
    email: str | None,
    role: str,
    expires_in_hours: int,
) -> tuple[Invite, str]:
    raw_token = issue_token()
    invite = Invite(
        email=normalize_email(email) if email else None,
        role=role,
        token_hash=hash_secret(raw_token),
        created_by_user_id=created_by_user_id,
        expires_at=invite_expiry(expires_in_hours).replace(tzinfo=None),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    return invite, raw_token


async def revoke_invite(
    session: AsyncSession,
    *,
    invite_id: UUID,
    owner_user_id: UUID,
) -> Invite:
    result = await session.execute(
        select(Invite).where(Invite.id == invite_id, Invite.created_by_user_id == owner_user_id)
    )
    invite = result.scalar_one_or_none()
    if invite is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    accepted_user_id = invite.accepted_by_user_id
    if accepted_user_id is not None:
        await delete_invited_user_workspace(session, user_id=accepted_user_id, owner_user_id=owner_user_id)
        invite.accepted_by_user_id = None
    if invite.revoked_at is None:
        invite.revoked_at = utc_now().replace(tzinfo=None)
        await session.commit()
        await session.refresh(invite)
    return invite


async def delete_invited_user_workspace(
    session: AsyncSession,
    *,
    user_id: UUID,
    owner_user_id: UUID,
) -> None:
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        return
    if user.role == "owner":
        raise HTTPException(status_code=403, detail="Owner accounts cannot be removed")
    if user.invited_by_user_id != owner_user_id:
        raise HTTPException(status_code=403, detail="You can only remove users you invited")

    plan_ids_result = await session.execute(select(InvestmentPlan.id).where(InvestmentPlan.user_id == user_id))
    plan_ids = list(plan_ids_result.scalars().all())
    if plan_ids:
        await session.execute(delete(InvestmentPlanTarget).where(InvestmentPlanTarget.plan_id.in_(plan_ids)))
        await session.execute(delete(InvestmentPlanPause).where(InvestmentPlanPause.plan_id.in_(plan_ids)))
        await session.execute(delete(InvestmentPlanAmountChange).where(InvestmentPlanAmountChange.plan_id.in_(plan_ids)))
        await session.execute(delete(InvestmentPlanOneOffContribution).where(InvestmentPlanOneOffContribution.plan_id.in_(plan_ids)))
        await session.execute(delete(InvestmentPlan).where(InvestmentPlan.id.in_(plan_ids)))

    await session.execute(delete(ManualTrade).where(ManualTrade.user_id == user_id))
    await session.execute(delete(Position).where(Position.user_id == user_id))
    await session.execute(delete(PortfolioSnapshot).where(PortfolioSnapshot.user_id == user_id))
    await session.execute(delete(WeeklyReview).where(WeeklyReview.user_id == user_id))
    await session.execute(delete(OpportunityScan).where(OpportunityScan.user_id == user_id))
    await session.execute(delete(UserSession).where(UserSession.user_id == user_id))
    await session.execute(delete(Invite).where(Invite.created_by_user_id == user_id))
    accepted_invites = await session.execute(select(Invite).where(Invite.accepted_by_user_id == user_id))
    for invite in accepted_invites.scalars().all():
        invite.accepted_by_user_id = None
    user.is_active = False
    await session.flush()
    await session.delete(user)
    await session.commit()


async def authenticate_user(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User:
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await session.commit()
        await session.refresh(user)
    return user


async def get_authenticated_session(
    session: AsyncSession,
    raw_token: str,
) -> AuthenticatedSession | None:
    token_hash = hash_secret(raw_token)
    result = await session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == token_hash)
    )
    row = result.one_or_none()
    if row is None:
        return None
    user_session, user = row
    now = utc_now().replace(tzinfo=None)
    if user_session.revoked_at is not None or user_session.expires_at <= now or not user.is_active:
        return None
    user_session.last_seen_at = now
    await session.commit()
    return AuthenticatedSession(user=user, session=user_session)


async def get_optional_current_user(
    session: AsyncSession,
    session_cookie: str | None,
) -> User | None:
    if not session_cookie:
        return None
    authenticated = await get_authenticated_session(session, session_cookie)
    return authenticated.user if authenticated is not None else None


async def require_current_user(
    session: AsyncSession,
    session_cookie: str | None,
) -> User:
    user = await get_optional_current_user(session, session_cookie)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def require_owner_user(
    session: AsyncSession,
    session_cookie: str | None,
) -> User:
    user = await require_current_user(session, session_cookie)
    if user.role != "owner":
        raise HTTPException(status_code=403, detail="Owner access required")
    return user


async def get_request_user_id(
    session: AsyncSession,
    session_cookie: str | None,
    internal_token: str | None,
    header_user_id: str | None,
) -> UUID:
    if settings.internal_api_token and internal_token == settings.internal_api_token:
        if header_user_id:
            try:
                return UUID(header_user_id)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid X-Echo-User-Id header") from exc
        result = await session.execute(select(User.id).order_by(User.created_at.asc()).limit(2))
        user_ids = list(result.scalars().all())
        if len(user_ids) == 1:
            return user_ids[0]
        raise HTTPException(status_code=400, detail="X-Echo-User-Id header is required for multi-user automation")
    user = await require_current_user(session, session_cookie)
    return user.id


def serialize_user(user: User) -> UserOut:
    return UserOut.model_validate(user)


def build_invite_url(raw_token: str) -> str:
    return f"{settings.public_app_url.rstrip('/')}/?invite={raw_token}"


def send_invite_email(*, recipient_email: str, invite_url: str, invited_by: str | None) -> None:
    if not invite_email_enabled():
        raise RuntimeError("SMTP is not configured")

    sender_name = settings.smtp_from_name.strip() or "EchoTrade"
    invited_by_copy = invited_by.strip() if invited_by else "EchoTrade"
    message = EmailMessage()
    message["Subject"] = "Your EchoTrade invite"
    message["From"] = f"{sender_name} <{settings.smtp_from_email}>"
    message["To"] = recipient_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid(domain=(settings.smtp_from_email.split("@", 1)[1] if "@" in settings.smtp_from_email else None))
    message.set_content(
        "\n".join(
            [
                f"{invited_by_copy} invited you to a private EchoTrade workspace.",
                "",
                "Use this link to create your account:",
                invite_url,
                "",
                "If you were not expecting this invite, you can ignore this email.",
            ]
        )
    )

    if settings.smtp_ssl:
        smtp = smtplib.SMTP_SSL(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )
    else:
        smtp = smtplib.SMTP(
            host=settings.smtp_host,
            port=settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        )
    with smtp:
        if settings.smtp_starttls and not settings.smtp_ssl:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def serialize_invite(
    invite: Invite,
    *,
    raw_token: str | None = None,
    delivery_result: InviteDeliveryResult | None = None,
) -> InviteOut:
    invite_url = None
    if raw_token is not None:
        invite_url = build_invite_url(raw_token)
    return InviteOut(
        id=invite.id,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        accepted_at=invite.accepted_at,
        revoked_at=invite.revoked_at,
        invite_url=invite_url,
        delivery_state=delivery_result.state if delivery_result else None,
        delivery_error=delivery_result.error if delivery_result else None,
    )


async def session_cookie_value(
    session_token: str | None = Cookie(default=None, alias=settings.auth_session_cookie_name),
) -> str | None:
    return session_token


async def get_current_user_dependency(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> User:
    return await require_current_user(session, session_cookie)


async def get_owner_user_dependency(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
) -> User:
    return await require_owner_user(session, session_cookie)


async def require_app_access_dependency(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
    internal_token: str | None = Header(default=None, alias="X-Echo-Internal-Token"),
) -> User | None:
    if settings.internal_api_token and internal_token == settings.internal_api_token:
        return None
    return await require_current_user(session, session_cookie)


async def request_user_id_dependency(
    session: AsyncSession = Depends(get_session),
    session_cookie: str | None = Depends(session_cookie_value),
    internal_token: str | None = Header(default=None, alias="X-Echo-Internal-Token"),
    header_user_id: str | None = Header(default=None, alias="X-Echo-User-Id"),
) -> UUID:
    return await get_request_user_id(session, session_cookie, internal_token, header_user_id)
