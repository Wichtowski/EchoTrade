"""EchoPulse summary generation service."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DailySummary:
    """Structured daily portfolio summary."""

    portfolio_value: float
    currency: str
    top_exposure_ticker: str
    top_exposure_pct: float
    main_risk: str
    position_summaries: list[dict[str, object]]
    suggested_action: str


async def generate_daily_summary() -> DailySummary:
    """Generate the daily portfolio summary.

    TODO: Fetch positions from EchoCore, prices from market API,
    compute P/L, allocation, concentration, and build summary.
    """
    return DailySummary(
        portfolio_value=0,
        currency="PLN",
        top_exposure_ticker="",
        top_exposure_pct=0,
        main_risk="",
        position_summaries=[],
        suggested_action="",
    )
