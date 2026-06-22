"""Portfolio snapshot and risk router."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth import request_user_id_dependency
from core.services.browser_capture import (
    extract_latest_capture_close,
    get_latest_capture_document,
)
from core.services.portfolio import build_snapshot_payload, latest_quote_map
from libdb.models import ManualTrade, MarketQuote, PortfolioSnapshot, Position
from libdb.session import get_session
from libshared.schemas import (
    BrowserCaptureProvider,
    Currency,
    PortfolioOverviewOut,
    PortfolioPositionBreakdownOut,
    PortfolioRiskOut,
    PortfolioSnapshotOut,
)

router = APIRouter()


async def _build_quote_map_with_capture_fallback(
    positions: list[Position],
    session: AsyncSession,
) -> dict[str, MarketQuote]:
    quote_result = await session.execute(select(MarketQuote))
    quote_map = latest_quote_map(list(quote_result.scalars().all()))

    missing_positions = [position for position in positions if position.ticker not in quote_map]
    for position in missing_positions:
        document = await get_latest_capture_document(BrowserCaptureProvider.CNBC, position.ticker)
        if document is None:
            continue
        latest_close = extract_latest_capture_close(document.document)
        if latest_close is None:
            continue
        quote_map[position.ticker] = MarketQuote(
            symbol=position.ticker,
            price=latest_close,
            currency=position.currency,
            source="cnbc_capture",
            source_timestamp=None,
            delay_seconds=None,
            confidence="medium",
            warnings=None,
        )

    return quote_map


@router.get("/snapshot", response_model=list[PortfolioSnapshotOut])
async def list_snapshots(
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> list[PortfolioSnapshot]:
    result = await session.execute(
        select(PortfolioSnapshot)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(PortfolioSnapshot.created_at.desc())
        .limit(30)
    )
    return list(result.scalars().all())


@router.post("/snapshot", response_model=PortfolioSnapshotOut, status_code=201)
async def create_snapshot(
    reporting_currency: Currency | None = None,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> PortfolioSnapshot:
    positions_result = await session.execute(select(Position).where(Position.user_id == user_id))
    trades_result = await session.execute(
        select(ManualTrade).where(ManualTrade.user_id == user_id).order_by(ManualTrade.executed_at.asc())
    )
    positions = list(positions_result.scalars().all())
    quote_map = await _build_quote_map_with_capture_fallback(positions, session)
    trades = list(trades_result.scalars().all())
    total_value, positions_payload, allocation, risk = await build_snapshot_payload(
        positions,
        quote_map,
        trades=trades,
        reporting_currency=reporting_currency,
    )

    snapshot = PortfolioSnapshot(
        user_id=user_id,
        account_type="personal",
        total_value=total_value,
        currency=risk.currency,
        positions=positions_payload,
        allocation=allocation,
        risk_summary=risk.model_dump(),
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    return snapshot


@router.get("/risk", response_model=PortfolioRiskOut)
async def portfolio_risk(
    reporting_currency: Currency | None = None,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> PortfolioRiskOut:
    positions_result = await session.execute(select(Position).where(Position.user_id == user_id))
    trades_result = await session.execute(
        select(ManualTrade).where(ManualTrade.user_id == user_id).order_by(ManualTrade.executed_at.asc())
    )
    positions = list(positions_result.scalars().all())
    quote_map = await _build_quote_map_with_capture_fallback(positions, session)
    trades = list(trades_result.scalars().all())
    _, _, _, risk = await build_snapshot_payload(
        positions,
        quote_map,
        trades=trades,
        reporting_currency=reporting_currency,
    )
    return risk


@router.get("/overview", response_model=PortfolioOverviewOut)
async def portfolio_overview(
    reporting_currency: Currency | None = None,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> PortfolioOverviewOut:
    positions_result = await session.execute(select(Position).where(Position.user_id == user_id))
    trades_result = await session.execute(
        select(ManualTrade).where(ManualTrade.user_id == user_id).order_by(ManualTrade.executed_at.asc())
    )
    positions = list(positions_result.scalars().all())
    quote_map = await _build_quote_map_with_capture_fallback(positions, session)
    trades = list(trades_result.scalars().all())
    total_value, positions_payload, _, risk = await build_snapshot_payload(
        positions,
        quote_map,
        trades=trades,
        reporting_currency=reporting_currency,
    )
    breakdown = [
        PortfolioPositionBreakdownOut(**payload)
        for payload in positions_payload.values()
    ]
    return PortfolioOverviewOut(
        total_value=total_value,
        currency=risk.currency,
        positions=breakdown,
        risk=risk,
    )


@router.delete("/snapshot/{snapshot_id}", status_code=204)
async def delete_snapshot(
    snapshot_id: UUID,
    session: AsyncSession = Depends(get_session),
    user_id=Depends(request_user_id_dependency),
) -> None:
    snapshot = await session.get(PortfolioSnapshot, snapshot_id)
    if snapshot is None or snapshot.user_id != user_id:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    await session.delete(snapshot)
    await session.commit()
