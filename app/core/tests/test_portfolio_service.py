from __future__ import annotations

from datetime import UTC
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from core.services.investment_plans import (
    count_scheduled_contributions,
    next_contribution_date,
)
from core.services.market_data import _build_history_bars_from_payload
from core.services.portfolio import (
    PositionKey,
    _same_trade_signature,
    build_position_states_from_manual_trades,
    build_snapshot_payload,
)
from libdb.models import ManualTrade, MarketQuote, Position


def _position(
    ticker: str,
    quantity: float,
    average_price: float,
    sector: str | None = None,
) -> Position:
    return Position(
        id=uuid4(),
        account_type="personal",
        ticker=ticker,
        quantity=quantity,
        average_price=average_price,
        currency="PLN",
        sector=sector,
        thesis=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def _quote(symbol: str, price: float) -> MarketQuote:
    now = datetime.now(timezone.utc)
    return MarketQuote(
        id=uuid4(),
        symbol=symbol,
        price=price,
        currency="PLN",
        source="manual",
        source_timestamp=now,
        received_at=now,
        delay_seconds=0,
        confidence="high",
        warnings=[],
    )


def _trade(
    ticker: str,
    action: str,
    quantity: float,
    price: float,
    executed_at: datetime,
) -> ManualTrade:
    return ManualTrade(
        id=uuid4(),
        account_type="personal",
        ticker=ticker,
        action=action,
        quantity=quantity,
        price=price,
        broker="Revolut",
        currency="USD",
        fees=0,
        sector="semis",
        thesis=None,
        notes=None,
        review_date=None,
        executed_at=executed_at,
        created_at=executed_at,
    )


@pytest.mark.asyncio
async def test_snapshot_builds_allocation_and_risk_warnings() -> None:
    positions = [
        _position("AMD", 10, 100, sector="semis"),
        _position("NVDA", 2, 120, sector="semis"),
    ]
    quote_map = {
        "AMD": _quote("AMD", 150),
        "NVDA": _quote("NVDA", 100),
    }

    async def fx_rate(base: str, quote: str, on_date: datetime | None) -> float:
        del on_date
        return 1.0 if base == quote else 4.0

    total_value, positions_payload, allocation, risk = await build_snapshot_payload(
        positions,
        quote_map,
        reporting_currency="PLN",
        resolve_fx_rate=fx_rate,
    )

    assert total_value == 1700
    assert positions_payload["AMD"]["pnl"] == 500
    assert allocation["AMD"] == 88.24
    assert risk.ticker_allocation["NVDA"] == 11.76
    assert "AMD concentration is high at 88.24%" in risk.warnings
    assert "semis sector concentration is high at 100.00%" in risk.warnings


@pytest.mark.asyncio
async def test_snapshot_warns_when_quotes_are_missing() -> None:
    positions = [_position("ASML", 1, 900, sector="semis")]

    async def fx_rate(base: str, quote: str, on_date: datetime | None) -> float:
        del on_date
        return 1.0 if base == quote else 4.0

    _, payload, allocation, risk = await build_snapshot_payload(
        positions,
        {},
        reporting_currency="PLN",
        resolve_fx_rate=fx_rate,
    )

    assert payload["ASML"]["current_price"] == 900
    assert allocation["ASML"] == 100.0
    assert "Missing fresh market quotes for: ASML" in risk.warnings


@pytest.mark.asyncio
async def test_snapshot_uses_historical_fx_for_remaining_open_lots() -> None:
    positions = [_position("AMD", 2, 275, sector="semis")]
    positions[0].currency = "USD"
    positions[0].broker = "Revolut"
    quote_map = {"AMD": _quote("AMD", 300)}
    quote_map["AMD"].currency = "USD"
    trades = [
        _trade("AMD", "BUY", 1, 200, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _trade("AMD", "BUY", 1, 250, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        _trade("AMD", "BUY", 1, 300, datetime(2026, 1, 3, tzinfo=timezone.utc)),
        _trade("AMD", "SELL", 1, 350, datetime(2026, 1, 4, tzinfo=timezone.utc)),
    ]

    async def fx_rate(base: str, quote: str, on_date: datetime | None) -> float:
        if base == quote:
            return 1.0
        assert quote == "PLN"
        if on_date is None:
            return 5.0
        mapping = {
            datetime(2026, 1, 2, tzinfo=UTC).date(): 4.0,
            datetime(2026, 1, 3, tzinfo=UTC).date(): 5.0,
        }
        return mapping[on_date.date()]

    total_value, payload, _, risk = await build_snapshot_payload(
        positions,
        quote_map,
        trades=trades,
        reporting_currency="PLN",
        resolve_fx_rate=fx_rate,
    )

    assert total_value == 3000
    assert payload["AMD"]["cost_basis"] == 250 * 4.0 + 300 * 5.0
    assert payload["AMD"]["pnl"] == 500
    assert risk.currency == "PLN"


def test_trade_state_uses_fifo_for_remaining_average_price() -> None:
    trades = [
        _trade("AMD", "BUY", 1, 200, datetime(2026, 1, 1, tzinfo=timezone.utc)),
        _trade("AMD", "BUY", 1, 250, datetime(2026, 1, 2, tzinfo=timezone.utc)),
        _trade("AMD", "BUY", 1, 300, datetime(2026, 1, 3, tzinfo=timezone.utc)),
        _trade("AMD", "SELL", 1, 350, datetime(2026, 1, 4, tzinfo=timezone.utc)),
    ]

    states = build_position_states_from_manual_trades(trades)
    state = states[PositionKey("personal", "AMD", "Revolut", "USD")]
    lots = state["lots"]

    assert state["quantity"] == 2
    assert len(lots) == 2
    assert lots[0].unit_price == 250
    assert lots[1].unit_price == 300


def test_trade_signature_matches_renamed_position_duplicate() -> None:
    stale = _position("RHM", 0.02544888, 86.94)
    stale.broker = "Revolut"
    stale.currency = "EUR"
    stale.opened_at = datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc)

    renamed = _position("RHM.DE", 0.02544888, 86.94)
    renamed.broker = "Revolut"
    renamed.currency = "EUR"
    renamed.opened_at = datetime(2026, 1, 19, 8, 0, tzinfo=timezone.utc)

    assert _same_trade_signature(stale, renamed) is True


def test_investment_plan_counts_monthly_runs_from_start_date() -> None:
    total = count_scheduled_contributions(
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
        contribution_day=10,
        today=datetime(2026, 6, 18, tzinfo=timezone.utc).date(),
    )

    assert total == 6


def test_investment_plan_next_run_stays_in_current_month_when_due_date_is_ahead() -> None:
    next_run = next_contribution_date(
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc).date(),
        contribution_day=10,
        today=datetime(2026, 6, 3, tzinfo=timezone.utc).date(),
    )

    assert next_run == datetime(2026, 6, 10, tzinfo=timezone.utc).date()


def test_build_history_bars_from_payload_creates_weekly_bars() -> None:
    payload = {
        "s": "ok",
        "t": [1736294400, 1736899200],
        "o": [100.0, 105.0],
        "h": [110.0, 112.0],
        "l": [99.0, 101.0],
        "c": [108.0, 109.0],
        "v": [1000, 1200],
    }

    bars = _build_history_bars_from_payload(symbol="NVDA", resolution="W", payload=payload)

    assert len(bars) == 2
    assert bars[0].symbol == "NVDA"
    assert bars[0].resolution == "W"
    assert bars[0].open_price == 100.0
    assert bars[1].close_price == 109.0
