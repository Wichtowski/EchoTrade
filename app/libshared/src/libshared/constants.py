"""Global constants for EchoTrade."""

from __future__ import annotations

# Initial experimental whitelist
WHITELIST: list[str] = [
    "AMD",
    "NVDA",
    "ASML",
    "INTC",
    "RHM.DE",
    "SMH",
    "SOXX",
    "QQQ",
    "EQQQ",
    "SPY",
    "VWCE",
]

# Risk-rule identifiers
RISK_RULES: list[str] = [
    "no_leverage",
    "no_margin",
    "no_options",
    "no_short_selling",
    "no_cfds",
    "no_crypto_futures",
    "no_penny_stocks",
    "instrument_whitelist",
    "max_single_trade_amount",
    "max_position_size_pct",
    "max_ticker_exposure_pct",
    "max_sector_exposure_pct",
    "daily_loss_limit",
    "monthly_loss_limit",
    "stale_market_data",
    "price_source_divergence",
    "evaluator_rejection",
    "cooldown_period",
    "broker_account_inconsistency",
    "manual_rule_change_only",
    "no_price_target_only",
    "no_browser_only",
    "missing_proposal_fields",
]

# ---------------------------------------------------------------------------
# Time horizon definitions
# ---------------------------------------------------------------------------
# Used by EchoSignal when generating trade proposals and by EchoGuard when
# validating that a proposal's expected_holding_period is sensible.

TIME_HORIZONS: dict[str, dict[str, str]] = {
    "intraday":    {"label": "Intraday",    "range": "< 1 day",       "description": "Opened and closed within a single trading session."},
    "short_term":  {"label": "Short-term",  "range": "1–5 days",      "description": "Swing trade lasting up to one trading week."},
    "medium_term": {"label": "Medium-term", "range": "1–8 weeks",     "description": "Position held across several weeks; typical EchoTrade experimental range."},
    "long_term":   {"label": "Long-term",   "range": "2–6 months",    "description": "Multi-month thesis play; requires quarterly review."},
    "strategic":   {"label": "Strategic",   "range": "> 6 months",    "description": "Core conviction position; reviewed semi-annually."},
}

# The experimental trader should default to medium_term.
# Intraday is forbidden for the experimental account.
ALLOWED_EXPERIMENTAL_HORIZONS: list[str] = ["short_term", "medium_term", "long_term"]

# Personal portfolio positions are typically strategic/long_term.
DEFAULT_PERSONAL_HORIZON: str = "strategic"
