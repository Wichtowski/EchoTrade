from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from libdb.models import ExecutedTrade, MarketQuote, PaperAccount, User
from libshared.config import settings
from libshared.schemas import PaperAccountOut, PaperPositionOut
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value))


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def quote_is_fresh(quote: MarketQuote | None, now: datetime) -> bool:
    if quote is None or quote.source not in {"yahoo", "alpaca", "twelve_data", "broker"}:
        return False
    price = money(quote.price)
    if not price.is_finite() or price <= 0 or quote.source_timestamp is None:
        return False
    age = (now - utc(quote.source_timestamp)).total_seconds()
    return -60 <= age <= settings.paper_quote_max_age_seconds


def replay_fills(trades: list[ExecutedTrade]) -> tuple[dict[str, dict[str, Decimal]], Decimal]:
    holdings: dict[str, dict[str, Decimal]] = {}
    realized = Decimal(0)
    for trade in trades:
        position = holdings.setdefault(trade.ticker, {"quantity": Decimal(0), "cost": Decimal(0)})
        quantity, price, fees = money(trade.quantity), money(trade.price), money(trade.fees)
        if trade.action == "BUY":
            position["quantity"] += quantity
            position["cost"] += quantity * price + fees
        else:
            if quantity > position["quantity"] or quantity <= 0:
                raise HTTPException(status_code=409, detail="Paper ledger contains an invalid sell")
            cost = position["cost"] * quantity / position["quantity"]
            realized += quantity * price - fees - cost
            position["quantity"] -= quantity
            position["cost"] -= cost
    return {ticker: value for ticker, value in holdings.items() if value["quantity"] > 0}, realized


async def load_account(session: AsyncSession, user_id: UUID) -> PaperAccount:
    # Lock the user before lazy creation and every fill so budget and cash cannot race.
    owner = await session.scalar(select(User).where(User.id == user_id).with_for_update())
    if owner is None:
        raise HTTPException(status_code=404, detail="User not found")
    account = await session.get(PaperAccount, user_id, populate_existing=True)
    if account is None:
        cash = money(settings.paper_initial_cash)
        if not cash.is_finite() or cash <= 0:
            raise HTTPException(status_code=503, detail="Paper starting cash must be positive")
        account = PaperAccount(
            user_id=user_id,
            initial_cash=cash,
            cash=cash,
            currency="USD",
            status="paused",
            daily_start_equity=cash,
            monthly_start_equity=cash,
        )
        session.add(account)
        await session.flush()
    return account


async def account_state(session: AsyncSession, account: PaperAccount) -> PaperAccountOut:
    from core.services.trading import serialize_executed_trade

    trades = list(
        (
            await session.scalars(
                select(ExecutedTrade)
                .where(ExecutedTrade.paper_account_id == account.user_id)
            .order_by(ExecutedTrade.paper_sequence)
            )
        ).all()
    )
    holdings, realized = replay_fills(trades)
    quotes = (
        list(
            (
                await session.scalars(
                    select(MarketQuote)
                    .where(MarketQuote.symbol.in_(holdings))
                    .order_by(MarketQuote.received_at.desc())
                )
            ).all()
        )
        if holdings
        else []
    )
    latest: dict[str, MarketQuote] = {}
    for quote in quotes:
        latest.setdefault(quote.symbol, quote)
    positions = []
    warnings = []
    total_value = Decimal(0)
    total_cost = Decimal(0)
    now = datetime.now(UTC)
    for ticker, holding in holdings.items():
        quote = latest.get(ticker)
        fresh = quote_is_fresh(quote, now) and quote.currency == account.currency
        value = holding["quantity"] * money(quote.price) if fresh else None
        if value is None:
            warnings.append(
                f"{ticker}: fresh {account.currency} quote required for valuation and execution"
            )
        else:
            total_value += value
        total_cost += holding["cost"]
        positions.append(
            PaperPositionOut(
                ticker=ticker,
                quantity=float(holding["quantity"]),
                average_price=float(holding["cost"] / holding["quantity"]),
                current_price=float(quote.price) if fresh else None,
                market_value=None if value is None else float(value),
                unrealized_pnl=None if value is None else float(value - holding["cost"]),
                quote_fresh=fresh,
            )
        )
    return PaperAccountOut(
        currency=account.currency,
        initial_cash=float(account.initial_cash),
        cash=float(account.cash),
        equity=None if warnings else float(money(account.cash) + total_value),
        realized_pnl=float(realized),
        unrealized_pnl=None if warnings else float(total_value - total_cost),
        status=account.status,
        positions=positions,
        trades=[serialize_executed_trade(trade) for trade in reversed(trades)],
        warnings=warnings,
    )


def update_loss_baselines(account: PaperAccount, equity: float, now: datetime) -> None:
    day, month = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    if account.daily_period != day:
        account.daily_period = day
        account.daily_start_equity = money(equity)
    if account.monthly_period != month:
        account.monthly_period = month
        account.monthly_start_equity = money(equity)


def sector(ticker: str) -> str:
    if ticker in {"AMD", "NVDA", "ASML", "INTC", "SMH", "SOXX"}:
        return "semis"
    return "defense" if ticker == "RHM.DE" else "broad_market"


def execution_failures(
    account: PaperAccount, state: PaperAccountOut, proposal, quote, trades, now: datetime
) -> list[str]:
    failures = []
    if account.status != "active":
        failures.append("trading_paused")
    if proposal.account_type != "experimental":
        failures.append("paper_account_only")
    if proposal.order_type != "MARKET":
        failures.append("market_orders_only")
    if (
        proposal.currency != account.currency
        or quote is not None
        and quote.currency != account.currency
    ):
        failures.append("currency_mismatch")
    if not quote_is_fresh(quote, now):
        failures.append("stale_market_data")
    from core.services.jobs import market_calendar

    market = market_calendar()
    day = now.date().isoformat()
    if (
        not market.is_session(day)
        or not market.session_open(day).to_pydatetime()
        <= now
        < market.session_close(day).to_pydatetime()
    ):
        failures.append("market_closed")
    if state.equity is None:
        failures.append("unvalued_holdings")
    if proposal.review_date is None or utc(proposal.review_date) <= now:
        failures.append("review_date_not_future")
    if sum(utc(t.executed_at).date() == now.date() for t in trades) >= settings.max_daily_trades:
        failures.append("daily_trade_limit")
    if (
        trades
        and utc(trades[-1].executed_at) + timedelta(hours=settings.cooldown_after_trade_hours) > now
    ):
        failures.append("cooldown_period")
    if (
        account.last_loss_at
        and utc(account.last_loss_at) + timedelta(hours=settings.cooldown_after_loss_hours) > now
    ):
        failures.append("loss_cooldown")
    amount = money(proposal.amount)
    if proposal.action == "BUY" and amount > money(account.cash):
        failures.append("insufficient_cash")
    holding = next((p for p in state.positions if p.ticker == proposal.ticker), None)
    if proposal.action == "SELL":
        available = (
            Decimal(0)
            if holding is None or quote is None
            else money(holding.quantity) * money(quote.price)
        )
        if amount > available:
            failures.append("insufficient_holdings")
    if state.equity is not None:
        equity = money(state.equity)
        daily = money(account.daily_start_equity)
        monthly = money(account.monthly_start_equity)
        if daily > 0 and (daily - equity) / daily * 100 >= money(settings.max_daily_loss_pct):
            failures.append("daily_loss_limit")
        if monthly > 0 and (monthly - equity) / monthly * 100 >= money(
            settings.max_monthly_loss_pct
        ):
            failures.append("monthly_loss_limit")
        if proposal.action == "BUY" and equity > 0:
            ticker_value = money(holding.market_value or 0) if holding else Decimal(0)
            sector_value = sum(
                (
                    money(p.market_value or 0)
                    for p in state.positions
                    if sector(p.ticker) == sector(proposal.ticker)
                ),
                Decimal(0),
            )
            if (ticker_value + amount) / equity * 100 > money(settings.max_ticker_exposure_pct):
                failures.append("max_ticker_exposure_pct")
            if (sector_value + amount) / equity * 100 > money(settings.max_sector_exposure_pct):
                failures.append("max_sector_exposure_pct")
    return failures
