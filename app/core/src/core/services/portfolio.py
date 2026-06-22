"""Portfolio calculation helpers."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from math import isclose
from typing import NamedTuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libdb.models import ManualTrade, MarketQuote, Position
from libshared.schemas import Currency, PortfolioRiskOut
from core.services.market_data import fetch_frankfurter_rate


def _as_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def latest_quote_map(quotes: list[MarketQuote]) -> dict[str, MarketQuote]:
    latest: dict[str, MarketQuote] = {}
    for quote in quotes:
        existing = latest.get(quote.symbol)
        if existing is None or quote.received_at > existing.received_at:
            latest[quote.symbol] = quote
    return latest


class PositionKey(NamedTuple):
    account_type: str
    ticker: str
    broker: str
    currency: str


@dataclass
class CostLot:
    quantity: float
    unit_price: float
    fees: float
    executed_at: datetime | None


FxRateResolver = Callable[[str, str, datetime | None], Awaitable[float]]


def _same_trade_signature(left: Position, right: Position) -> bool:
    return (
        left.account_type == right.account_type
        and left.broker == right.broker
        and left.currency == right.currency
        and left.ticker != right.ticker
        and left.opened_at == right.opened_at
        and isclose(_as_float(left.quantity), _as_float(right.quantity), rel_tol=0, abs_tol=1e-9)
        and isclose(_as_float(left.average_price), _as_float(right.average_price), rel_tol=0, abs_tol=1e-9)
    )


def build_position_states_from_manual_trades(
    trades: list[ManualTrade],
) -> dict[PositionKey, dict[str, object]]:
    running: dict[PositionKey, dict[str, object]] = {}
    for trade in trades:
        key = PositionKey(trade.account_type, trade.ticker, trade.broker, trade.currency)
        state = running.setdefault(
            key,
            {
                "quantity": 0.0,
                "lots": [],
                "sector": trade.sector,
                "thesis": trade.thesis,
                "opened_at": trade.executed_at,
            },
        )
        quantity = _as_float(trade.quantity)
        gross_amount = _as_float(trade.price)
        fees = _as_float(trade.fees)
        lots = state["lots"]
        assert isinstance(lots, list)
        net_invested_amount = max(gross_amount - fees, 0.0)
        unit_price = net_invested_amount / quantity if quantity else 0.0

        if trade.action == "BUY":
            lots.append(
                CostLot(
                    quantity=quantity,
                    unit_price=unit_price,
                    fees=fees,
                    executed_at=trade.executed_at,
                )
            )
            state["quantity"] = float(state["quantity"]) + quantity
            state["opened_at"] = state["opened_at"] or trade.executed_at
        else:
            remaining_to_sell = quantity
            while remaining_to_sell > 0 and lots:
                first_lot = lots[0]
                if first_lot.quantity <= remaining_to_sell:
                    remaining_to_sell -= first_lot.quantity
                    lots.pop(0)
                else:
                    first_lot.quantity -= remaining_to_sell
                    remaining_to_sell = 0
            state["quantity"] = sum(lot.quantity for lot in lots)

        if trade.sector:
            state["sector"] = trade.sector
        if trade.thesis:
            state["thesis"] = trade.thesis

    return running


async def sync_positions_from_manual_trades(session: AsyncSession, *, user_id: UUID) -> list[Position]:
    trades_result = await session.execute(
        select(ManualTrade).where(ManualTrade.user_id == user_id).order_by(ManualTrade.executed_at.asc())
    )
    existing_result = await session.execute(select(Position).where(Position.user_id == user_id))

    trades = list(trades_result.scalars().all())
    existing_positions = list(existing_result.scalars().all())
    existing_by_key: dict[PositionKey, list[Position]] = defaultdict(list)
    for position in existing_positions:
        existing_by_key[
            PositionKey(position.account_type, position.ticker, position.broker, position.currency)
        ].append(position)

    running = build_position_states_from_manual_trades(trades)

    synced_positions: list[Position] = []
    stale_positions_to_delete: list[Position] = []
    active_keys: set[PositionKey] = set()
    journal_keys = set(running.keys())
    for key, state in running.items():
        quantity = float(state["quantity"])
        if quantity <= 0:
            continue
        active_keys.add(key)
        lots = state["lots"]
        assert isinstance(lots, list)
        cost_basis = sum(lot.quantity * lot.unit_price for lot in lots)
        average_price = cost_basis / quantity if quantity else 0.0
        matches = existing_by_key.get(key, [])
        survivor = matches[0] if matches else Position(
            user_id=user_id,
            account_type=key.account_type,
            ticker=key.ticker,
            broker=key.broker,
            currency=key.currency,
            quantity=quantity,
            average_price=average_price,
        )
        survivor.user_id = user_id
        survivor.quantity = quantity
        survivor.average_price = average_price
        survivor.sector = state["sector"]  # type: ignore[assignment]
        survivor.thesis = state["thesis"]  # type: ignore[assignment]
        survivor.opened_at = state["opened_at"]  # type: ignore[assignment]
        session.add(survivor)
        synced_positions.append(survivor)
        for existing_position in existing_positions:
            existing_key = PositionKey(
                existing_position.account_type,
                existing_position.ticker,
                existing_position.broker,
                existing_position.currency,
            )
            if existing_key == key:
                continue
            if existing_position in stale_positions_to_delete:
                continue
            if _same_trade_signature(existing_position, survivor):
                stale_positions_to_delete.append(existing_position)
        for duplicate in matches[1:]:
            await session.delete(duplicate)

    for key, matches in existing_by_key.items():
        if key in active_keys or key not in journal_keys:
            continue
        for position in matches:
            await session.delete(position)

    for stale_position in stale_positions_to_delete:
        await session.delete(stale_position)

    await session.commit()
    for position in synced_positions:
        await session.refresh(position)
    return synced_positions


async def build_snapshot_payload(
    positions: list[Position],
    quote_map: dict[str, MarketQuote],
    trades: list[ManualTrade] | None = None,
    reporting_currency: Currency | str | None = None,
    resolve_fx_rate: FxRateResolver | None = None,
) -> tuple[float, dict[str, dict[str, float | str | None]], dict[str, float], PortfolioRiskOut]:
    fx_resolver = resolve_fx_rate or _resolve_fx_rate
    normalized_reporting_currency = _resolve_reporting_currency(
        positions,
        quote_map,
        requested_currency=reporting_currency,
    )
    total_value = 0.0
    positions_payload: dict[str, dict[str, float | str | None]] = {}
    ticker_values: dict[str, float] = {}
    sector_values: defaultdict[str, float] = defaultdict(float)
    open_trade_states = (
        build_position_states_from_manual_trades(sorted(trades, key=lambda trade: trade.executed_at))
        if trades
        else {}
    )

    for position in positions:
        quantity = _as_float(position.quantity)
        average_price = _as_float(position.average_price)
        quote = quote_map.get(position.ticker)
        current_price = _as_float(quote.price) if quote else average_price
        price_currency = quote.currency if quote else position.currency
        fx_to_reporting = await fx_resolver(price_currency, normalized_reporting_currency, None)
        market_value_native = quantity * current_price
        market_value = market_value_native * fx_to_reporting
        cost_basis_native = _resolve_cost_basis_native(
            position=position,
            quantity=quantity,
            average_price=average_price,
            open_trade_states=open_trade_states,
        )
        cost_basis = await _resolve_cost_basis_reporting(
            position=position,
            quantity=quantity,
            average_price=average_price,
            reporting_currency=normalized_reporting_currency,
            open_trade_states=open_trade_states,
            fx_resolver=fx_resolver,
        )
        pnl_native = market_value_native - cost_basis_native
        pnl = market_value - cost_basis
        total_value += market_value
        ticker_values[position.ticker] = market_value
        sector_name = position.sector or "unknown"
        sector_values[sector_name] += market_value
        positions_payload[position.ticker] = {
            "ticker": position.ticker,
            "quantity": quantity,
            "average_price": average_price,
            "current_price": current_price,
            "currency": position.currency,
            "reporting_currency": normalized_reporting_currency,
            "market_value": market_value,
            "market_value_native": market_value_native,
            "cost_basis_native": cost_basis_native,
            "cost_basis": cost_basis,
            "pnl_native": pnl_native,
            "pnl": pnl,
            "sector": position.sector,
            "price_source": quote.source if quote else None,
            "fx_rate_to_reporting": fx_to_reporting,
        }

    ticker_allocation = _pct_breakdown(ticker_values, total_value)
    sector_allocation = _pct_breakdown(dict(sector_values), total_value)
    warnings = build_risk_warnings(ticker_allocation, sector_allocation, quote_map, positions)

    risk = PortfolioRiskOut(
        total_value=total_value,
        currency=normalized_reporting_currency,
        ticker_allocation=ticker_allocation,
        sector_allocation=sector_allocation,
        warnings=warnings,
    )
    return total_value, positions_payload, ticker_allocation, risk


def _resolve_reporting_currency(
    positions: list[Position],
    quote_map: dict[str, MarketQuote],
    *,
    requested_currency: Currency | str | None,
) -> str:
    if requested_currency:
        return requested_currency.value if isinstance(requested_currency, Currency) else str(requested_currency).upper()

    inferred_currencies = [
        str((quote_map.get(position.ticker).currency if quote_map.get(position.ticker) else position.currency)).upper()
        for position in positions
    ]
    unique_currencies = {currency for currency in inferred_currencies if currency}
    if len(unique_currencies) == 1:
        return unique_currencies.pop()
    if inferred_currencies:
        counts: defaultdict[str, int] = defaultdict(int)
        for currency in inferred_currencies:
            counts[currency] += 1
        return max(counts, key=counts.get)
    return Currency.USD.value


async def _resolve_fx_rate(
    base_currency: str,
    quote_currency: str,
    on_date: datetime | None,
) -> float:
    return await fetch_frankfurter_rate(base_currency, quote_currency, on_date=on_date)


async def _resolve_cost_basis_reporting(
    *,
    position: Position,
    quantity: float,
    average_price: float,
    reporting_currency: str,
    open_trade_states: dict[PositionKey, dict[str, object]],
    fx_resolver: FxRateResolver,
) -> float:
    key = PositionKey(position.account_type, position.ticker, position.broker, position.currency)
    state = open_trade_states.get(key)
    if state is None:
        fallback_rate = await fx_resolver(position.currency, reporting_currency, position.opened_at)
        return quantity * average_price * fallback_rate

    lots = state.get("lots")
    if not isinstance(lots, list) or not lots:
        return 0.0

    total_cost_basis = 0.0
    for lot in lots:
        if not isinstance(lot, CostLot):
            continue
        fx_rate = await fx_resolver(position.currency, reporting_currency, lot.executed_at)
        total_cost_basis += ((lot.quantity * lot.unit_price) + lot.fees) * fx_rate
    return total_cost_basis


def _resolve_cost_basis_native(
    *,
    position: Position,
    quantity: float,
    average_price: float,
    open_trade_states: dict[PositionKey, dict[str, object]],
) -> float:
    key = PositionKey(position.account_type, position.ticker, position.broker, position.currency)
    state = open_trade_states.get(key)
    if state is None:
        return quantity * average_price

    lots = state.get("lots")
    if not isinstance(lots, list) or not lots:
        return 0.0

    total_cost_basis = 0.0
    for lot in lots:
        if not isinstance(lot, CostLot):
            continue
        total_cost_basis += (lot.quantity * lot.unit_price) + lot.fees
    return total_cost_basis


def _pct_breakdown(values: dict[str, float], total: float) -> dict[str, float]:
    if total <= 0:
        return {key: 0.0 for key in values}
    return {key: round((value / total) * 100, 2) for key, value in values.items()}


def build_risk_warnings(
    ticker_allocation: dict[str, float],
    sector_allocation: dict[str, float],
    quote_map: dict[str, MarketQuote],
    positions: list[Position],
) -> list[str]:
    warnings: list[str] = []

    for ticker, pct in ticker_allocation.items():
        if pct > 40:
            warnings.append(f"{ticker} concentration is high at {pct:.2f}%")

    for sector, pct in sector_allocation.items():
        if pct > 60:
            warnings.append(f"{sector} sector concentration is high at {pct:.2f}%")

    missing_quotes = sorted(position.ticker for position in positions if position.ticker not in quote_map)
    if missing_quotes:
        warnings.append(f"Missing fresh market quotes for: {', '.join(missing_quotes)}")

    return warnings
