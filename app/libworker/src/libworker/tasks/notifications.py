"""Notification Celery tasks — Discord via EchoWire."""

from __future__ import annotations

from libworker.celery_app import app


@app.task(name="notifications.send_daily_summary")
def send_daily_summary(summary: dict) -> dict:
    """Send daily portfolio summary to Discord.

    TODO: Format summary, call wire.discord.send_daily_summary().
    """
    return {"status": "ok", "task": "send_daily_summary"}


@app.task(name="notifications.send_alert")
def send_alert(message: str) -> dict:
    """Send urgent alert to Discord.

    TODO: Call wire.discord.send_alert().
    """
    return {"status": "ok", "task": "send_alert"}


@app.task(name="notifications.send_trade_proposal")
def send_trade_proposal(proposal: dict) -> dict:
    """Send trade proposal to Discord for approval.

    TODO: Format proposal, call wire.discord.send_trade_proposal().
    """
    return {"status": "ok", "task": "send_trade_proposal"}
