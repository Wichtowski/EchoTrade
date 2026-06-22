"""EchoWire Discord notification service.

Sends formatted messages to configured Discord channels via webhooks.

Channels:
    #echo-daily             — daily portfolio summary
    #echo-alerts            — urgent movement alerts
    #echo-trade-proposals   — trade proposals awaiting approval
    #echo-trade-executions  — confirmed executions
    #echo-risk              — risk alerts, pause notifications
    #echo-journal           — decision journal entries
    #echo-manual-override   — kill switch, manual interventions
"""

from __future__ import annotations

import httpx

from libshared.config import settings

DISCORD_BASE_API = settings.discord_webhook_base


def _resolve_webhook(path: str) -> str:
    """Combine base URL with webhook path."""
    if not path:
        return ""
    if path.startswith("http"):
        return path
    return f"{DISCORD_BASE_API.rstrip('/')}{path}"


async def send_message(webhook_path: str, content: str, embeds: list[dict] | None = None) -> bool:
    """Send a message to a Discord webhook."""
    url = _resolve_webhook(webhook_path)
    if not url:
        return False

    payload: dict[str, object] = {"content": content}
    if embeds:
        payload["embeds"] = embeds

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        return resp.status_code in (200, 204)


async def send_daily_summary(content: str) -> bool:
    return await send_message(settings.discord_webhook_daily, content)


async def send_alert(content: str) -> bool:
    return await send_message(settings.discord_webhook_alerts, content)


async def send_trade_proposal(content: str) -> bool:
    return await send_message(settings.discord_webhook_proposals, content)


async def send_trade_execution(content: str) -> bool:
    return await send_message(settings.discord_webhook_executions, content)


async def send_risk_alert(content: str) -> bool:
    return await send_message(settings.discord_webhook_risk, content)


async def send_journal_entry(content: str) -> bool:
    return await send_message(settings.discord_webhook_journal, content)


async def send_override(content: str) -> bool:
    return await send_message(settings.discord_webhook_override, content)


# ---------------------------------------------------------------------------
# Test helper — send a test message to every configured webhook
# ---------------------------------------------------------------------------

_CHANNELS = {
    "daily": ("discord_webhook_daily", "#echo-daily"),
    "alerts": ("discord_webhook_alerts", "#echo-alerts"),
    "proposals": ("discord_webhook_proposals", "#echo-trade-proposals"),
    "executions": ("discord_webhook_executions", "#echo-trade-executions"),
    "risk": ("discord_webhook_risk", "#echo-risk"),
    "journal": ("discord_webhook_journal", "#echo-journal"),
    "override": ("discord_webhook_override", "#echo-manual-override"),
}


async def test_discord_echos() -> dict[str, bool]:
    """Send a test message to every configured Discord webhook.

    Returns a dict of channel_name -> success.
    """
    results: dict[str, bool] = {}
    for name, (attr, channel) in _CHANNELS.items():
        path = getattr(settings, attr, "")
        if not path:
            results[name] = False
            continue
        ok = await send_message(
            path,
            f"🔔 **EchoTrade test** — `{channel}` webhook is working.",
        )
        results[name] = ok
    return results


async def _run_test() -> None:
    """CLI entrypoint for test_discord_echos."""
    results = await test_discord_echos()
    for name, ok in results.items():
        status = "✅" if ok else "❌ (not configured or failed)"
        print(f"  {name}: {status}")


def main() -> None:
    """Sync wrapper so it can be called from `uv run`."""
    import asyncio

    asyncio.run(_run_test())
