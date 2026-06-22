from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.browser_capture import (
    extract_latest_capture_close,
    get_latest_capture_document,
)
from core.services.portfolio import build_snapshot_payload, latest_quote_map
from libdb.models import (
    InvestmentPlan,
    InvestmentPlanTarget,
    ManualTrade,
    MarketQuote,
    OpportunityScan,
    PortfolioSnapshot,
    Position,
    WeeklyReview,
)
from libshared.schemas import (
    BrowserCaptureProvider,
    OpportunityCandidateOut,
    OpportunityScanOut,
    OpportunityScanRunRequest,
    WeeklyReviewOut,
    WeeklyReviewPositionInsight,
    WeeklyReviewRunRequest,
)


def _as_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


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
            received_at=datetime.now(UTC),
            delay_seconds=None,
            confidence="medium",
            warnings=None,
        )
    return quote_map


def summarize_weekly_review(
    *,
    positions_payload: dict[str, dict[str, Any]],
    current_allocation: dict[str, float],
    current_warnings: list[str],
    previous_total_value: float | None,
    previous_allocation: dict[str, float] | None,
    recent_trades: list[ManualTrade],
    period_start: datetime,
    period_end: datetime,
) -> dict[str, Any]:
    buy_count = sum(1 for trade in recent_trades if trade.action == "BUY")
    sell_count = sum(1 for trade in recent_trades if trade.action == "SELL")
    due_review_tickers = sorted(
        {
            trade.ticker
            for trade in recent_trades
            if trade.review_date is not None and trade.review_date <= period_end
        }
    )

    insights: list[dict[str, Any]] = []
    for ticker, payload in positions_payload.items():
        market_value = float(payload.get("market_value", 0.0) or 0.0)
        pnl = float(payload.get("pnl", 0.0) or 0.0)
        current_pct = float(current_allocation.get(ticker, 0.0))
        previous_pct = (
            float((previous_allocation or {}).get(ticker, 0.0))
            if previous_allocation is not None
            else None
        )
        allocation_change = None if previous_pct is None else round(current_pct - previous_pct, 2)
        insights.append(
            {
                "ticker": ticker,
                "market_value": round(market_value, 2),
                "pnl": round(pnl, 2),
                "allocation_pct": round(current_pct, 2),
                "allocation_change_pct": allocation_change,
                "sector": payload.get("sector"),
            }
        )

    top_winners = sorted(insights, key=lambda item: item["pnl"], reverse=True)[:3]
    top_losers = sorted(insights, key=lambda item: item["pnl"])[:3]

    concentration_changes: dict[str, float] = {}
    for ticker in sorted(set(current_allocation) | set(previous_allocation or {})):
        previous_pct = float((previous_allocation or {}).get(ticker, 0.0))
        current_pct = float(current_allocation.get(ticker, 0.0))
        concentration_changes[ticker] = round(current_pct - previous_pct, 2)

    summary_parts = [
        f"Weekly review for {period_start.date()} to {period_end.date()}",
        f"{len(recent_trades)} trades",
    ]
    total_value = round(sum(float(payload.get("market_value", 0.0) or 0.0) for payload in positions_payload.values()), 2)
    if previous_total_value is not None:
        change = round(total_value - previous_total_value, 2)
        direction = "up" if change >= 0 else "down"
        summary_parts.append(f"portfolio value {direction} {abs(change):.2f}")
    summary = ", ".join(summary_parts) + "."

    insight_lines: list[str] = []
    if top_winners:
        winner = top_winners[0]
        insight_lines.append(
            f"Best holding this week: {winner['ticker']} with P/L {winner['pnl']:.2f}."
        )
    if top_losers:
        loser = top_losers[0]
        insight_lines.append(
            f"Weakest holding this week: {loser['ticker']} with P/L {loser['pnl']:.2f}."
        )
    if concentration_changes:
        drift_ticker = max(concentration_changes, key=lambda ticker: abs(concentration_changes[ticker]))
        drift_value = concentration_changes[drift_ticker]
        if drift_value != 0:
            insight_lines.append(
                f"Largest allocation drift: {drift_ticker} moved {drift_value:+.2f} percentage points."
            )
    if due_review_tickers:
        insight_lines.append(
            f"Review follow-up due for: {', '.join(due_review_tickers)}."
        )
    if previous_total_value is None:
        insight_lines.append("No prior comparable snapshot was available for week-over-week comparison.")

    return {
        "buy_count": buy_count,
        "sell_count": sell_count,
        "top_winners": top_winners,
        "top_losers": top_losers,
        "concentration_changes": concentration_changes,
        "due_review_tickers": due_review_tickers,
        "warnings": current_warnings,
        "summary": summary,
        "insights": insight_lines,
        "total_value": total_value,
        "total_value_change": None if previous_total_value is None else round(total_value - previous_total_value, 2),
    }


def rank_opportunity_candidates(
    *,
    tickers: list[str],
    positions_by_ticker: dict[str, Position],
    target_payloads: dict[str, dict[str, Any]],
    quote_payloads: dict[str, dict[str, Any]],
    chart_payloads: dict[str, dict[str, Any] | None],
    due_review_tickers: set[str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for ticker in tickers:
        position = positions_by_ticker.get(ticker)
        target = target_payloads.get(ticker)
        quote = quote_payloads.get(ticker)
        chart_document = chart_payloads.get(ticker)
        has_chart = chart_document is not None
        latest_price = None
        has_fresh_quote = quote is not None
        if quote is not None:
            latest_price = quote["price"]
        elif chart_document is not None:
            latest_price = chart_document.get("latest_close")

        held = position is not None
        target_weight_pct = None if target is None else target.get("weight_pct")
        currency = None
        sector = None
        if quote is not None:
            currency = quote.get("currency")
        elif position is not None:
            currency = position.currency
        elif target is not None:
            currency = target.get("currency")
        if position is not None and position.sector:
            sector = position.sector
        elif target is not None:
            sector = target.get("sector")

        notes: list[str] = []
        score = 0.0
        if target is not None:
            notes.append("Tracked in an investment plan target list.")
            score += 20
        if held:
            notes.append("Already held in the portfolio.")
            score += 6
        else:
            notes.append("Not currently held.")
            score += 12
        if has_fresh_quote:
            notes.append("Fresh market quote available.")
            score += 10
        else:
            notes.append("Fresh quote missing; using research context only.")
            score -= 8
        if has_chart:
            notes.append("Browser chart context available.")
            score += 6
        if ticker in due_review_tickers:
            notes.append("Follow-up review date is due or overdue.")
            score += 4

        market_value = None
        if held and latest_price is not None:
            market_value = round(_as_float(position.quantity) * float(latest_price), 2)

        source = "manual_input"
        if target is not None:
            source = "plan_target"
        elif held:
            source = "held_position"

        candidates.append(
            {
                "ticker": ticker,
                "sector": sector,
                "currency": currency,
                "source": source,
                "held": held,
                "has_fresh_quote": has_fresh_quote,
                "has_chart": has_chart,
                "latest_price": None if latest_price is None else round(float(latest_price), 4),
                "market_value": market_value,
                "target_weight_pct": None if target_weight_pct is None else round(float(target_weight_pct), 2),
                "thesis_due": ticker in due_review_tickers,
                "score": round(score, 2),
                "notes": notes,
            }
        )

    return sorted(candidates, key=lambda item: (-item["score"], item["ticker"]))


async def create_weekly_review(
    session: AsyncSession,
    data: WeeklyReviewRunRequest,
    *,
    user_id: UUID,
) -> WeeklyReview:
    now = datetime.now(UTC)
    period_end = now
    period_start = now - timedelta(days=data.period_days)

    positions_result = await session.execute(
        select(Position).where(Position.account_type == data.account_type.value, Position.user_id == user_id)
    )
    trades_result = await session.execute(
        select(ManualTrade)
        .where(ManualTrade.account_type == data.account_type.value, ManualTrade.user_id == user_id)
        .order_by(ManualTrade.executed_at.asc())
    )
    positions = list(positions_result.scalars().all())
    trades = list(trades_result.scalars().all())
    quote_map = await _build_quote_map_with_capture_fallback(positions, session)
    _, positions_payload, allocation, risk = await build_snapshot_payload(
        positions,
        quote_map,
        trades=trades,
        reporting_currency=data.reporting_currency,
    )

    previous_snapshot_result = await session.execute(
        select(PortfolioSnapshot)
        .where(
            PortfolioSnapshot.account_type == data.account_type.value,
            PortfolioSnapshot.user_id == user_id,
            PortfolioSnapshot.currency == risk.currency,
            PortfolioSnapshot.created_at < period_start,
        )
        .order_by(PortfolioSnapshot.created_at.desc())
        .limit(1)
    )
    previous_snapshot = previous_snapshot_result.scalar_one_or_none()
    recent_trades = [trade for trade in trades if period_start <= trade.executed_at <= period_end]

    details = summarize_weekly_review(
        positions_payload=positions_payload,
        current_allocation=risk.ticker_allocation,
        current_warnings=risk.warnings,
        previous_total_value=_as_float(previous_snapshot.total_value) if previous_snapshot else None,
        previous_allocation=previous_snapshot.allocation if previous_snapshot else None,
        recent_trades=recent_trades,
        period_start=period_start,
        period_end=period_end,
    )

    review = WeeklyReview(
        user_id=user_id,
        account_type=data.account_type.value,
        period_start=period_start,
        period_end=period_end,
        reporting_currency=risk.currency,
        total_value=details["total_value"],
        total_value_change=details["total_value_change"],
        trade_count=len(recent_trades),
        summary=details["summary"],
        insights={
            "buy_count": details["buy_count"],
            "sell_count": details["sell_count"],
            "top_winners": details["top_winners"],
            "top_losers": details["top_losers"],
            "concentration_changes": details["concentration_changes"],
            "due_review_tickers": details["due_review_tickers"],
            "insights": details["insights"],
        },
        warnings=details["warnings"],
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


def serialize_weekly_review(review: WeeklyReview) -> WeeklyReviewOut:
    insights = review.insights or {}
    return WeeklyReviewOut(
        id=review.id,
        created_at=review.created_at,
        account_type=review.account_type,
        period_start=review.period_start,
        period_end=review.period_end,
        reporting_currency=review.reporting_currency,
        total_value=_as_float(review.total_value),
        total_value_change=None if review.total_value_change is None else _as_float(review.total_value_change),
        trade_count=review.trade_count,
        buy_count=int(insights.get("buy_count", 0)),
        sell_count=int(insights.get("sell_count", 0)),
        top_winners=[WeeklyReviewPositionInsight.model_validate(item) for item in insights.get("top_winners", [])],
        top_losers=[WeeklyReviewPositionInsight.model_validate(item) for item in insights.get("top_losers", [])],
        concentration_changes={
            key: float(value) for key, value in dict(insights.get("concentration_changes", {})).items()
        },
        due_review_tickers=list(insights.get("due_review_tickers", [])),
        warnings=list(review.warnings or []),
        summary=review.summary,
        insights=list(insights.get("insights", [])),
    )


async def create_opportunity_scan(
    session: AsyncSession,
    data: OpportunityScanRunRequest,
    *,
    user_id: UUID,
) -> OpportunityScan:
    if data.plan_id is not None:
        plan = await session.get(InvestmentPlan, data.plan_id)
        if plan is None or plan.user_id != user_id:
            raise ValueError("Investment plan not found")

    positions_result = await session.execute(
        select(Position).where(Position.account_type == data.account_type.value, Position.user_id == user_id)
    )
    trades_result = await session.execute(
        select(ManualTrade)
        .where(ManualTrade.account_type == data.account_type.value, ManualTrade.user_id == user_id)
        .order_by(ManualTrade.executed_at.desc())
    )
    targets_query = (
        select(InvestmentPlanTarget)
        .join(InvestmentPlan, InvestmentPlan.id == InvestmentPlanTarget.plan_id)
        .where(InvestmentPlan.user_id == user_id)
    )
    if data.plan_id is not None:
        targets_query = targets_query.where(InvestmentPlanTarget.plan_id == data.plan_id)
    targets_result = await session.execute(targets_query)

    positions = list(positions_result.scalars().all())
    trades = list(trades_result.scalars().all())
    targets = list(targets_result.scalars().all())
    positions_by_ticker = {position.ticker: position for position in positions}

    tickers: list[str] = []
    warnings: list[str] = []
    if data.tickers:
        tickers = sorted({ticker.strip().upper() for ticker in data.tickers if ticker.strip()})
    elif targets:
        tickers = sorted({target.ticker.strip().upper() for target in targets})
    else:
        tickers = sorted({position.ticker.strip().upper() for position in positions})
        warnings.append("No explicit tickers or plan targets were provided; scanning current holdings instead.")

    quote_result = await session.execute(select(MarketQuote))
    latest_quotes = latest_quote_map(list(quote_result.scalars().all()))
    target_payloads = {
        target.ticker.upper(): {
            "weight_pct": _as_float(target.weight_pct),
            "sector": target.sector,
            "currency": target.currency,
        }
        for target in targets
    }
    quote_payloads = {
        symbol.upper(): {
            "price": _as_float(quote.price),
            "currency": quote.currency,
            "source": quote.source,
        }
        for symbol, quote in latest_quotes.items()
    }
    due_review_tickers = {
        trade.ticker
        for trade in trades
        if trade.review_date is not None and trade.review_date <= datetime.now(UTC)
    }

    chart_payloads: dict[str, dict[str, Any] | None] = {}
    for ticker in tickers:
        document = await get_latest_capture_document(BrowserCaptureProvider.CNBC, ticker)
        if document is None:
            chart_payloads[ticker] = None
            continue
        chart_payloads[ticker] = {
            "latest_close": extract_latest_capture_close(document.document),
            "document_id": document.document_id,
        }

    candidates = rank_opportunity_candidates(
        tickers=tickers,
        positions_by_ticker=positions_by_ticker,
        target_payloads=target_payloads,
        quote_payloads=quote_payloads,
        chart_payloads=chart_payloads,
        due_review_tickers=due_review_tickers,
    )[: data.limit]

    if not candidates:
        warnings.append("No candidates were available for the requested scan inputs.")
    if any(not candidate["has_fresh_quote"] for candidate in candidates):
        warnings.append("Some candidates are missing fresh quotes and rely on supporting context only.")

    scan = OpportunityScan(
        user_id=user_id,
        account_type=data.account_type.value,
        cadence=data.cadence,
        plan_id=data.plan_id,
        summary=f"Opportunity scan reviewed {len(tickers)} tickers and returned {len(candidates)} candidates.",
        tickers=tickers,
        candidates=candidates,
        warnings=warnings,
    )
    session.add(scan)
    await session.commit()
    await session.refresh(scan)
    return scan


def serialize_opportunity_scan(scan: OpportunityScan) -> OpportunityScanOut:
    return OpportunityScanOut(
        id=scan.id,
        created_at=scan.created_at,
        account_type=scan.account_type,
        cadence=scan.cadence,
        plan_id=scan.plan_id,
        candidate_count=len(scan.candidates or []),
        summary=scan.summary,
        warnings=list(scan.warnings or []),
        tickers=list(scan.tickers or []),
        candidates=[OpportunityCandidateOut.model_validate(item) for item in (scan.candidates or [])],
    )
