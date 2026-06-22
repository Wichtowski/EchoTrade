from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from core.services.review import rank_opportunity_candidates, summarize_weekly_review
from libdb.models import ManualTrade, Position


def _trade(
    ticker: str,
    action: str,
    executed_at: datetime,
    *,
    review_date: datetime | None = None,
) -> ManualTrade:
    return ManualTrade(
        id=uuid4(),
        account_type="personal",
        ticker=ticker,
        action=action,
        quantity=1,
        price=100,
        broker="Revolut",
        currency="USD",
        fees=0,
        sector="semis",
        thesis=None,
        notes=None,
        review_date=review_date,
        executed_at=executed_at,
        created_at=executed_at,
    )


def _position(ticker: str, quantity: float, *, sector: str | None = None, currency: str = "USD") -> Position:
    now = datetime.now(UTC)
    return Position(
        id=uuid4(),
        account_type="personal",
        ticker=ticker,
        quantity=quantity,
        average_price=100,
        broker="Revolut",
        currency=currency,
        sector=sector,
        thesis=None,
        opened_at=now,
        created_at=now,
        updated_at=now,
    )


def test_summarize_weekly_review_tracks_winners_losers_and_drifts() -> None:
    period_start = datetime(2026, 6, 14, tzinfo=UTC)
    period_end = datetime(2026, 6, 21, tzinfo=UTC)
    details = summarize_weekly_review(
        positions_payload={
            "AMD": {"market_value": 1500, "pnl": 200, "sector": "semis"},
            "ASML": {"market_value": 500, "pnl": -50, "sector": "semis"},
        },
        current_allocation={"AMD": 75.0, "ASML": 25.0},
        current_warnings=["AMD concentration is high at 75.00%"],
        previous_total_value=1800,
        previous_allocation={"AMD": 60.0, "ASML": 40.0},
        recent_trades=[
            _trade("AMD", "BUY", period_start),
            _trade("ASML", "SELL", period_start, review_date=period_end),
        ],
        period_start=period_start,
        period_end=period_end,
    )

    assert details["buy_count"] == 1
    assert details["sell_count"] == 1
    assert details["top_winners"][0]["ticker"] == "AMD"
    assert details["top_losers"][0]["ticker"] == "ASML"
    assert details["concentration_changes"]["AMD"] == 15.0
    assert details["due_review_tickers"] == ["ASML"]
    assert details["total_value_change"] == 200.0


def test_rank_opportunity_candidates_prefers_plan_targets_with_data() -> None:
    candidates = rank_opportunity_candidates(
        tickers=["AMD", "CRM"],
        positions_by_ticker={"AMD": _position("AMD", 2, sector="semis")},
        target_payloads={
            "CRM": {"weight_pct": 12.5, "sector": "software", "currency": "USD"}
        },
        quote_payloads={
            "AMD": {"price": 150.0, "currency": "USD", "source": "yahoo"},
            "CRM": {"price": 280.0, "currency": "USD", "source": "yahoo"},
        },
        chart_payloads={
            "AMD": {"latest_close": 149.0, "document_id": "1"},
            "CRM": {"latest_close": 279.0, "document_id": "2"},
        },
        due_review_tickers={"AMD"},
    )

    assert candidates[0]["ticker"] == "CRM"
    assert candidates[0]["source"] == "plan_target"
    assert candidates[0]["held"] is False
    assert candidates[0]["has_fresh_quote"] is True
    assert candidates[1]["ticker"] == "AMD"
    assert candidates[1]["thesis_due"] is True
    assert candidates[1]["market_value"] == 300.0
