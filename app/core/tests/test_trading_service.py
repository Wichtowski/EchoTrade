from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from core.services.trading import (
    _proposal_to_create,
    serialize_risk_check,
    serialize_trade_proposal,
)
from libdb.models import RiskCheck, TradeProposal
from libshared.schemas import AccountType, OrderType, ProposalStatus, TradeAction


def _proposal() -> TradeProposal:
    return TradeProposal(
        id=uuid4(),
        user_id=uuid4(),
        account_type=AccountType.EXPERIMENTAL.value,
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
        ticker="AMD",
        action=TradeAction.BUY.value,
        amount=75,
        currency="PLN",
        order_type=OrderType.MARKET.value,
        limit_price=None,
        reason="Testing paper-mode proposal flow",
        thesis="AMD has a defined follow-up thesis",
        risks=["Semiconductor drawdown"],
        invalidated_if="Guidance weakens",
        expected_holding_period="2-8 weeks",
        review_date=datetime(2026, 8, 9, tzinfo=UTC),
        confidence=0.61,
        used_browser_context=True,
        sources=[{"title": "Market note", "url": "https://example.com"}],
        status=ProposalStatus.PENDING.value,
    )


def test_serialize_trade_proposal_keeps_paper_fields() -> None:
    output = serialize_trade_proposal(_proposal())

    assert output.account_type == AccountType.EXPERIMENTAL
    assert output.ticker == "AMD"
    assert output.status == ProposalStatus.PENDING
    assert output.sources == [{"title": "Market note", "url": "https://example.com"}]


def test_proposal_to_create_restores_evaluator_payload() -> None:
    payload = _proposal_to_create(_proposal())

    assert payload.account_type == AccountType.EXPERIMENTAL
    assert payload.action == TradeAction.BUY
    assert payload.order_type == OrderType.MARKET
    assert payload.risks == ["Semiconductor drawdown"]
    assert payload.sources is not None
    assert payload.sources[0].title == "Market note"


def test_serialize_risk_check_normalizes_json_fields() -> None:
    risk_check = RiskCheck(
        id=uuid4(),
        user_id=uuid4(),
        proposal_id=uuid4(),
        created_at=datetime(2026, 7, 9, tzinfo=UTC),
        passed=False,
        failed_rules=["stale_market_data"],
        warnings=["Market data is stale"],
        position_size_after_trade=None,
        sector_exposure_after_trade=None,
        monthly_budget_remaining=225,
        daily_loss=None,
        monthly_loss=None,
        evaluator_summary="Trade rejected",
    )

    output = serialize_risk_check(risk_check)

    assert output.failed_rules == ["stale_market_data"]
    assert output.warnings == ["Market data is stale"]
    assert output.monthly_budget_remaining == 225
