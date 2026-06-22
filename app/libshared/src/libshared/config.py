from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application-wide settings shared across all services."""

    # --- database ---
    database_url: str = "postgresql+asyncpg://echo:echo@localhost:5432/echotrade"

    # --- celery ---
    celery_broker_url: str = "amqp://echo:echo@localhost:5672//"
    celery_result_backend: str = "db+postgresql://echo:echo@localhost:5432/echotrade"
    redis_url: str = "redis://localhost:6379/0"
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "echotrade"
    mongodb_chart_collection: str = "browser_chart_payloads"
    mongodb_saved_query_collection: str = "saved_queries"

    # --- discord ---
    discord_webhook_base: str = "https://discord.com/api/webhooks"
    discord_webhook_daily: str = ""
    discord_webhook_alerts: str = ""
    discord_webhook_proposals: str = ""
    discord_webhook_executions: str = ""
    discord_webhook_risk: str = ""
    discord_webhook_journal: str = ""
    discord_webhook_override: str = ""

    # --- market data api keys ---
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    twelve_data_api_key: str = ""

    # --- broker ---
    broker_api_key: str = ""
    broker_api_secret: str = ""
    broker_base_url: str = ""

    # --- LLM ---
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""

    # --- frontend / api ---
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    public_app_url: str = "http://localhost:3000"

    # --- auth ---
    auth_session_cookie_name: str = "echotrade_session"
    auth_session_ttl_hours: int = 24 * 14
    auth_invite_ttl_hours: int = 24 * 7
    auth_cookie_secure: bool = False
    internal_api_token: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "EchoTrade"
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    smtp_timeout_seconds: int = 15

    # --- risk defaults ---
    max_monthly_budget: float = 300.0
    max_single_trade: float = 75.0
    max_daily_trades: int = 2
    max_daily_loss_pct: float = 3.0
    max_monthly_loss_pct: float = 15.0
    cooldown_after_trade_hours: int = 24
    cooldown_after_loss_hours: int = 72

    model_config = {"env_prefix": "ECHO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
