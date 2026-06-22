"""EchoReview — evaluates past trades and generates review reports."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libdb.models import ExecutedTrade, PostTradeReview


async def run_trade_review(session: AsyncSession, trade_id: UUID) -> PostTradeReview:
    """Run a review for a single executed trade.

    TODO: Fetch current price, compare with execution price,
    compute 1d/7d/30d performance, assess decision quality.
    """
    trade = await session.get(ExecutedTrade, trade_id)
    if not trade:
        raise ValueError(f"Trade {trade_id} not found")

    review = PostTradeReview(
        trade_id=trade_id,
        review_date=trade.executed_at,  # placeholder
    )
    session.add(review)
    await session.commit()
    await session.refresh(review)
    return review


async def run_weekly_review(session: AsyncSession) -> list[PostTradeReview]:
    """Run reviews for all trades executed in the past week.

    TODO: Select trades from past 7 days without existing reviews,
    run individual reviews, generate weekly summary.
    """
    result = await session.execute(
        select(ExecutedTrade).order_by(ExecutedTrade.executed_at.desc()).limit(20)
    )
    trades = result.scalars().all()
    reviews = []
    for trade in trades:
        review = await run_trade_review(session, trade.id)
        reviews.append(review)
    return reviews
