"""EchoBot execution service.

EchoBot is an execution-only service.
It MUST NOT generate its own trade ideas.
It only executes trades approved by EchoGuard.

Correct flow:
    EchoSignal → Trade Proposal → EchoGuard → EchoBot → Broker API
"""

from __future__ import annotations

from enum import Enum


class ExecutionMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


class BotStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"


_status = BotStatus.PAUSED
_mode = ExecutionMode.PAPER


async def execute_trade(proposal_id: str, mode: ExecutionMode = ExecutionMode.PAPER) -> dict:
    """Execute an approved trade.

    In paper mode: simulate execution and store fake fill.
    In live mode: call broker API and store real fill.
    """
    if _status == BotStatus.PAUSED:
        return {"error": "Trading is paused", "executed": False}

    if mode == ExecutionMode.PAPER:
        # TODO: simulate execution, store in executed_trades
        return {"proposal_id": proposal_id, "executed": True, "mode": "paper"}

    # TODO: live execution via broker API
    return {"proposal_id": proposal_id, "executed": False, "mode": "live", "error": "not_implemented"}


async def pause() -> dict:
    """Immediately halt all trading (kill switch)."""
    global _status
    _status = BotStatus.PAUSED
    return {"status": "paused"}


async def resume() -> dict:
    """Resume trading after manual review."""
    global _status
    _status = BotStatus.ACTIVE
    return {"status": "active"}


async def get_status() -> dict:
    return {"status": _status.value, "mode": _mode.value}
