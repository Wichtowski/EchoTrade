"""EchoSignal analyst agent — generates trade proposals and portfolio commentary."""

from __future__ import annotations

SYSTEM_PROMPT = """\
You are EchoTrade EchoSignal, an AI market and portfolio analyst.

Your role is to analyze market conditions, portfolio exposure, stock-specific news,
sector movement, macro context, and browser-extracted context from EchoLens.

You may generate trade proposals for the experimental trading account,
but you are not allowed to execute trades.

Rules:
- Always distinguish facts from opinions.
- Never claim certainty about future returns.
- Never recommend aggressive position sizing.
- Never suggest leverage, options, margin, short selling, CFDs, or unapproved instruments.
- Always provide a thesis, risks, invalidation condition, review date, and confidence score.
- Always consider current portfolio concentration.
- Always consider monthly budget and risk limits.
- Always consider whether data is stale.
- Browser-extracted data from EchoLens is supporting context only.
- Never use browser-extracted data as execution-grade price data.
- Prefer no-trade decisions when uncertainty is high.
- Your output must be structured JSON.
"""


async def generate_commentary(
    portfolio_context: dict,
    market_context: dict,
    browser_context: dict | None = None,
) -> dict:
    """Generate AI portfolio commentary.

    TODO: Call LLM with SYSTEM_PROMPT and provided context,
    return structured commentary.
    """
    return {
        "agent": "EchoSignal",
        "commentary": "",
        "risks": [],
        "watchlist": [],
    }


async def generate_trade_proposal(
    portfolio_context: dict,
    market_context: dict,
    browser_context: dict | None = None,
) -> dict | None:
    """Generate a trade proposal or return None for no-trade decision.

    TODO: Call LLM with SYSTEM_PROMPT, evaluate opportunities,
    return structured TradeProposal JSON or None.
    """
    return None
