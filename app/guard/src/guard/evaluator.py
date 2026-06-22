"""EchoGuard risk evaluator — deterministic rules + LLM evaluation."""

from __future__ import annotations

from libshared.constants import WHITELIST
from libshared.schemas import RiskCheckResult, RiskLevel, TradeProposalCreate

EVALUATOR_SYSTEM_PROMPT = """\
You are EchoTrade EchoGuard, a conservative risk evaluator.

Your role is to review AI-generated trade proposals.

You must be skeptical, conservative, and rule-based.

Reject a trade if:
- It violates any hard risk rule.
- It uses stale or unreliable data.
- It lacks a clear thesis.
- It lacks risk factors.
- It lacks an invalidation condition.
- It lacks a review date.
- It exceeds the monthly budget.
- It exceeds position size limits.
- It increases concentration beyond configured limits.
- It proposes forbidden instruments.
- It appears emotionally driven.
- It relies only on analyst price targets.
- It relies only on browser-extracted data.
- It claims certainty.
- It does not include sources.
- It uses scraped/browser prices as execution-grade data.

Return only structured JSON with approval status, failed rules, warnings, risk level, and summary.
"""


def evaluate_hard_rules(
    proposal: TradeProposalCreate,
    current_exposure: dict[str, float] | None = None,
    monthly_budget_remaining: float | None = None,
) -> RiskCheckResult:
    """Run deterministic hard risk rules against a trade proposal."""
    failed: list[str] = []
    warnings: list[str] = []

    # Rule 8: instrument whitelist
    if proposal.ticker not in WHITELIST:
        failed.append("instrument_whitelist")

    # Rule 9: max single trade
    from libshared.config import settings

    if proposal.amount > settings.max_single_trade:
        failed.append("max_single_trade_amount")

    # Rule 23: missing fields
    if not proposal.thesis:
        failed.append("missing_proposal_fields")
        warnings.append("Missing thesis")
    if not proposal.risks:
        failed.append("missing_proposal_fields")
        warnings.append("Missing risk factors")
    if not proposal.invalidated_if:
        failed.append("missing_proposal_fields")
        warnings.append("Missing invalidation condition")
    if not proposal.review_date:
        failed.append("missing_proposal_fields")
        warnings.append("Missing review date")

    # Budget check
    if monthly_budget_remaining is not None and proposal.amount > monthly_budget_remaining:
        failed.append("monthly_budget_exceeded")

    # Browser-only check (Rule 22)
    if proposal.used_browser_context and not proposal.risks:
        failed.append("no_browser_only")
        warnings.append("Trade relies on browser-extracted data without other risk factors")

    approved = len(failed) == 0
    risk_level = RiskLevel.LOW if approved else RiskLevel.HIGH

    return RiskCheckResult(
        approved=approved,
        risk_level=risk_level,
        failed_rules=list(set(failed)),
        warnings=warnings,
        summary="Trade approved" if approved else f"Trade rejected: {', '.join(set(failed))}",
        requires_manual_review=not approved,
        monthly_budget_remaining=monthly_budget_remaining,
    )
