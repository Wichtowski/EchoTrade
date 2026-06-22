"""Recurring investment plan router."""

from __future__ import annotations

from datetime import date, datetime, time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.investment_plans import (
    PlanAmountChangeEvent,
    PlanOneOffContributionEvent,
    PlanPauseWindow,
    calculate_expected_contributions_total,
    build_monthly_contribution_schedule,
    count_scheduled_contributions,
    next_contribution_date,
    resolve_monthly_amount_for_date,
)
from libdb.models import (
    InvestmentPlan,
    InvestmentPlanAmountChange,
    InvestmentPlanOneOffContribution,
    InvestmentPlanPause,
    InvestmentPlanTarget,
)
from libdb.session import get_session
from libshared.schemas import (
    InvestmentPlanAmountChangeCreate,
    InvestmentPlanAmountChangeOut,
    InvestmentPlanCreate,
    InvestmentPlanOut,
    InvestmentPlanOneOffContributionCreate,
    InvestmentPlanOneOffContributionOut,
    InvestmentPlanPauseCreate,
    InvestmentPlanPauseOut,
    InvestmentPlanTargetCreate,
    InvestmentPlanTargetOut,
    InvestmentPlanTargetUpdate,
    InvestmentPlanUpdate,
)

router = APIRouter()


def _normalize_ticker(value: str) -> str:
    return value.replace(".", "-").upper()


def _to_plan_date(value: datetime) -> date:
    return value.date()


def _from_plan_date(value: date) -> datetime:
    return datetime.combine(value, time.min)


def _serialize_target(target: InvestmentPlanTarget) -> InvestmentPlanTargetOut:
    return InvestmentPlanTargetOut(
        id=target.id,
        plan_id=target.plan_id,
        ticker=target.ticker,
        currency=target.currency,
        weight_pct=float(target.weight_pct),
        sector=target.sector,
        composition_sectors=list(target.composition_sectors or []),
        notes=target.notes,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


def _serialize_pause(pause: InvestmentPlanPause) -> InvestmentPlanPauseOut:
    return InvestmentPlanPauseOut(
        id=pause.id,
        plan_id=pause.plan_id,
        start_date=_to_plan_date(pause.start_date),
        end_date=_to_plan_date(pause.end_date),
        reason=pause.reason,
        created_at=pause.created_at,
    )


def _serialize_amount_change(change: InvestmentPlanAmountChange) -> InvestmentPlanAmountChangeOut:
    return InvestmentPlanAmountChangeOut(
        id=change.id,
        plan_id=change.plan_id,
        effective_date=_to_plan_date(change.effective_date),
        monthly_amount=float(change.monthly_amount),
        note=change.note,
        created_at=change.created_at,
    )


def _serialize_one_off(contribution: InvestmentPlanOneOffContribution) -> InvestmentPlanOneOffContributionOut:
    return InvestmentPlanOneOffContributionOut(
        id=contribution.id,
        plan_id=contribution.plan_id,
        contribution_date=_to_plan_date(contribution.contribution_date),
        amount=float(contribution.amount),
        note=contribution.note,
        created_at=contribution.created_at,
    )


async def _serialize_plan(
    session: AsyncSession,
    plan: InvestmentPlan,
) -> InvestmentPlanOut:
    targets_result = await session.execute(
        select(InvestmentPlanTarget)
        .where(InvestmentPlanTarget.plan_id == plan.id)
        .order_by(InvestmentPlanTarget.ticker.asc())
    )
    pauses_result = await session.execute(
        select(InvestmentPlanPause)
        .where(InvestmentPlanPause.plan_id == plan.id)
        .order_by(InvestmentPlanPause.start_date.asc())
    )
    amount_changes_result = await session.execute(
        select(InvestmentPlanAmountChange)
        .where(InvestmentPlanAmountChange.plan_id == plan.id)
        .order_by(InvestmentPlanAmountChange.effective_date.asc())
    )
    one_offs_result = await session.execute(
        select(InvestmentPlanOneOffContribution)
        .where(InvestmentPlanOneOffContribution.plan_id == plan.id)
        .order_by(InvestmentPlanOneOffContribution.contribution_date.asc())
    )
    targets = list(targets_result.scalars().all())
    pauses = list(pauses_result.scalars().all())
    amount_changes = list(amount_changes_result.scalars().all())
    one_offs = list(one_offs_result.scalars().all())
    start_date = _to_plan_date(plan.start_date)
    pause_windows = [
        PlanPauseWindow(start_date=_to_plan_date(pause.start_date), end_date=_to_plan_date(pause.end_date))
        for pause in pauses
    ]
    amount_change_events = [
        PlanAmountChangeEvent(
            effective_date=_to_plan_date(change.effective_date),
            monthly_amount=float(change.monthly_amount),
        )
        for change in amount_changes
    ]
    one_off_events = [
        PlanOneOffContributionEvent(
            contribution_date=_to_plan_date(contribution.contribution_date),
            amount=float(contribution.amount),
        )
        for contribution in one_offs
    ]
    scheduled_contributions = len(
        build_monthly_contribution_schedule(
            start_date=start_date,
            contribution_day=plan.contribution_day,
            pauses=pause_windows,
        )
    )
    total_target_allocation = round(sum(float(target.weight_pct) for target in targets), 2)
    return InvestmentPlanOut(
        id=plan.id,
        account_type=plan.account_type,
        name=plan.name,
        broker=plan.broker,
        currency=plan.currency,
        monthly_amount=float(plan.monthly_amount),
        contribution_day=plan.contribution_day,
        start_date=start_date,
        notes=plan.notes,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
        next_run_on=next_contribution_date(start_date, plan.contribution_day, pauses=pause_windows),
        scheduled_contributions=scheduled_contributions,
        expected_contributions_total=calculate_expected_contributions_total(
            start_date=start_date,
            contribution_day=plan.contribution_day,
            monthly_amount=float(plan.monthly_amount),
            pauses=pause_windows,
            amount_changes=amount_change_events,
            one_off_contributions=one_off_events,
        ),
        target_allocation_total=total_target_allocation,
        targets=[_serialize_target(target) for target in targets],
        pauses=[_serialize_pause(pause) for pause in pauses],
        amount_changes=[_serialize_amount_change(change) for change in amount_changes],
        one_off_contributions=[_serialize_one_off(contribution) for contribution in one_offs],
    )


async def _require_plan(session: AsyncSession, plan_id: UUID, *, user_id) -> InvestmentPlan:
    plan = await session.get(InvestmentPlan, plan_id)
    if plan is None or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Investment plan not found")
    return plan


@router.get("/", response_model=list[InvestmentPlanOut])
async def list_investment_plans(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[InvestmentPlanOut]:
    result = await session.execute(
        select(InvestmentPlan).where(InvestmentPlan.user_id == user_id).order_by(InvestmentPlan.created_at.desc())
    )
    plans = list(result.scalars().all())
    return [await _serialize_plan(session, plan) for plan in plans]


@router.post("/", response_model=InvestmentPlanOut, status_code=201)
async def create_investment_plan(
    data: InvestmentPlanCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanOut:
    plan = InvestmentPlan(
        user_id=user_id,
        account_type=data.account_type,
        name=data.name,
        broker=data.broker,
        currency=data.currency,
        monthly_amount=data.monthly_amount,
        contribution_day=data.contribution_day,
        start_date=_from_plan_date(data.start_date),
        notes=data.notes,
    )
    session.add(plan)
    await session.commit()
    await session.refresh(plan)
    return await _serialize_plan(session, plan)


@router.patch("/{plan_id}", response_model=InvestmentPlanOut)
async def update_investment_plan(
    plan_id: UUID,
    data: InvestmentPlanUpdate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanOut:
    plan = await _require_plan(session, plan_id, user_id=user_id)

    updates = data.model_dump(exclude_unset=True)
    if "start_date" in updates:
        updates["start_date"] = _from_plan_date(updates["start_date"])
    for field, value in updates.items():
        setattr(plan, field, value)
    await session.commit()
    await session.refresh(plan)
    return await _serialize_plan(session, plan)


@router.delete("/{plan_id}", status_code=204)
async def delete_investment_plan(
    plan_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    plan = await _require_plan(session, plan_id, user_id=user_id)
    targets_result = await session.execute(
        select(InvestmentPlanTarget).where(InvestmentPlanTarget.plan_id == plan_id)
    )
    for target in list(targets_result.scalars().all()):
        await session.delete(target)
    pauses_result = await session.execute(
        select(InvestmentPlanPause).where(InvestmentPlanPause.plan_id == plan_id)
    )
    for pause in list(pauses_result.scalars().all()):
        await session.delete(pause)
    amount_changes_result = await session.execute(
        select(InvestmentPlanAmountChange).where(InvestmentPlanAmountChange.plan_id == plan_id)
    )
    for change in list(amount_changes_result.scalars().all()):
        await session.delete(change)
    one_offs_result = await session.execute(
        select(InvestmentPlanOneOffContribution).where(InvestmentPlanOneOffContribution.plan_id == plan_id)
    )
    for contribution in list(one_offs_result.scalars().all()):
        await session.delete(contribution)
    await session.delete(plan)
    await session.commit()


@router.post("/{plan_id}/targets", response_model=InvestmentPlanTargetOut, status_code=201)
async def create_investment_plan_target(
    plan_id: UUID,
    data: InvestmentPlanTargetCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanTargetOut:
    await _require_plan(session, plan_id, user_id=user_id)
    target = InvestmentPlanTarget(
        plan_id=plan_id,
        ticker=_normalize_ticker(data.ticker),
        currency=data.currency,
        weight_pct=data.weight_pct,
        sector=data.sector,
        composition_sectors=data.composition_sectors,
        notes=data.notes,
    )
    session.add(target)
    await session.commit()
    await session.refresh(target)
    return _serialize_target(target)


@router.patch("/targets/{target_id}", response_model=InvestmentPlanTargetOut)
async def update_investment_plan_target(
    target_id: UUID,
    data: InvestmentPlanTargetUpdate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanTargetOut:
    target = await session.get(InvestmentPlanTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Investment plan target not found")
    await _require_plan(session, target.plan_id, user_id=user_id)
    updates = data.model_dump(exclude_unset=True)
    if "ticker" in updates and updates["ticker"] is not None:
        updates["ticker"] = _normalize_ticker(updates["ticker"])
    for field, value in updates.items():
        setattr(target, field, value)
    await session.commit()
    await session.refresh(target)
    return _serialize_target(target)


@router.delete("/targets/{target_id}", status_code=204)
async def delete_investment_plan_target(
    target_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    target = await session.get(InvestmentPlanTarget, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Investment plan target not found")
    await _require_plan(session, target.plan_id, user_id=user_id)
    await session.delete(target)
    await session.commit()


@router.post("/{plan_id}/pauses", response_model=InvestmentPlanPauseOut, status_code=201)
async def create_investment_plan_pause(
    plan_id: UUID,
    data: InvestmentPlanPauseCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanPauseOut:
    await _require_plan(session, plan_id, user_id=user_id)
    pause = InvestmentPlanPause(
        plan_id=plan_id,
        start_date=_from_plan_date(data.start_date),
        end_date=_from_plan_date(data.end_date),
        reason=data.reason,
    )
    session.add(pause)
    await session.commit()
    await session.refresh(pause)
    return _serialize_pause(pause)


@router.delete("/pauses/{pause_id}", status_code=204)
async def delete_investment_plan_pause(
    pause_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    pause = await session.get(InvestmentPlanPause, pause_id)
    if pause is None:
        raise HTTPException(status_code=404, detail="Investment plan pause not found")
    await _require_plan(session, pause.plan_id, user_id=user_id)
    await session.delete(pause)
    await session.commit()


@router.post("/{plan_id}/amount-changes", response_model=InvestmentPlanAmountChangeOut, status_code=201)
async def create_investment_plan_amount_change(
    plan_id: UUID,
    data: InvestmentPlanAmountChangeCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanAmountChangeOut:
    await _require_plan(session, plan_id, user_id=user_id)
    change = InvestmentPlanAmountChange(
        plan_id=plan_id,
        effective_date=_from_plan_date(data.effective_date),
        monthly_amount=data.monthly_amount,
        note=data.note,
    )
    session.add(change)
    await session.commit()
    await session.refresh(change)
    return _serialize_amount_change(change)


@router.delete("/amount-changes/{change_id}", status_code=204)
async def delete_investment_plan_amount_change(
    change_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    change = await session.get(InvestmentPlanAmountChange, change_id)
    if change is None:
        raise HTTPException(status_code=404, detail="Investment plan amount change not found")
    await _require_plan(session, change.plan_id, user_id=user_id)
    await session.delete(change)
    await session.commit()


@router.post("/{plan_id}/one-off-contributions", response_model=InvestmentPlanOneOffContributionOut, status_code=201)
async def create_investment_plan_one_off_contribution(
    plan_id: UUID,
    data: InvestmentPlanOneOffContributionCreate,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> InvestmentPlanOneOffContributionOut:
    await _require_plan(session, plan_id, user_id=user_id)
    contribution = InvestmentPlanOneOffContribution(
        plan_id=plan_id,
        contribution_date=_from_plan_date(data.contribution_date),
        amount=data.amount,
        note=data.note,
    )
    session.add(contribution)
    await session.commit()
    await session.refresh(contribution)
    return _serialize_one_off(contribution)


@router.delete("/one-off-contributions/{contribution_id}", status_code=204)
async def delete_investment_plan_one_off_contribution(
    contribution_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    contribution = await session.get(InvestmentPlanOneOffContribution, contribution_id)
    if contribution is None:
        raise HTTPException(status_code=404, detail="Investment plan one-off contribution not found")
    await _require_plan(session, contribution.plan_id, user_id=user_id)
    await session.delete(contribution)
    await session.commit()
