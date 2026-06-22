from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.review import (
    create_opportunity_scan,
    create_weekly_review,
    serialize_opportunity_scan,
    serialize_weekly_review,
)
from libdb.models import OpportunityScan, WeeklyReview
from libdb.session import get_session
from libshared.schemas import (
    OpportunityScanOut,
    OpportunityScanRunRequest,
    WeeklyReviewOut,
    WeeklyReviewRunRequest,
)

router = APIRouter()


@router.get("/weekly", response_model=list[WeeklyReviewOut])
async def list_weekly_reviews(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[WeeklyReviewOut]:
    result = await session.execute(
        select(WeeklyReview).where(WeeklyReview.user_id == user_id).order_by(WeeklyReview.created_at.desc()).limit(20)
    )
    return [serialize_weekly_review(review) for review in result.scalars().all()]


@router.get("/weekly/{review_id}", response_model=WeeklyReviewOut)
async def get_weekly_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> WeeklyReviewOut:
    review = await session.get(WeeklyReview, review_id)
    if review is None or review.user_id != user_id:
        raise HTTPException(status_code=404, detail="Weekly review not found")
    return serialize_weekly_review(review)


@router.post("/weekly/run", response_model=WeeklyReviewOut, status_code=201)
async def run_weekly_review(
    data: WeeklyReviewRunRequest,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> WeeklyReviewOut:
    review = await create_weekly_review(session, data, user_id=user_id)
    return serialize_weekly_review(review)


@router.get("/opportunity-scans", response_model=list[OpportunityScanOut])
async def list_opportunity_scans(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[OpportunityScanOut]:
    result = await session.execute(
        select(OpportunityScan).where(OpportunityScan.user_id == user_id).order_by(OpportunityScan.created_at.desc()).limit(20)
    )
    return [serialize_opportunity_scan(scan) for scan in result.scalars().all()]


@router.get("/opportunity-scans/{scan_id}", response_model=OpportunityScanOut)
async def get_opportunity_scan(
    scan_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> OpportunityScanOut:
    scan = await session.get(OpportunityScan, scan_id)
    if scan is None or scan.user_id != user_id:
        raise HTTPException(status_code=404, detail="Opportunity scan not found")
    return serialize_opportunity_scan(scan)


@router.post("/opportunity-scans/run", response_model=OpportunityScanOut, status_code=201)
async def run_opportunity_scan(
    data: OpportunityScanRunRequest,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> OpportunityScanOut:
    try:
        scan = await create_opportunity_scan(session, data, user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return serialize_opportunity_scan(scan)
