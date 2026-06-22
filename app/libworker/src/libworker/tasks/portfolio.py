"""Portfolio-related Celery tasks."""

from __future__ import annotations

from libworker.celery_app import app


@app.task(name="portfolio.create_daily_snapshot")
def create_daily_snapshot() -> dict:
    """Create a daily portfolio snapshot.

    Called by n8n cron or scheduled beat.
    TODO: Fetch positions, prices, compute P/L, store snapshot.
    """
    return {"status": "ok", "task": "create_daily_snapshot"}


@app.task(name="portfolio.calculate_risk")
def calculate_risk(account_type: str = "personal") -> dict:
    """Calculate portfolio risk metrics.

    TODO: Compute concentration, sector exposure, drawdown.
    """
    return {"status": "ok", "task": "calculate_risk", "account_type": account_type}
