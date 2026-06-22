"""Helpers for recurring investment plan scheduling."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date


@dataclass
class PlanPauseWindow:
    start_date: date
    end_date: date


@dataclass
class PlanAmountChangeEvent:
    effective_date: date
    monthly_amount: float


@dataclass
class PlanOneOffContributionEvent:
    contribution_date: date
    amount: float


def _scheduled_day(year: int, month: int, contribution_day: int) -> date:
    return date(year, month, min(contribution_day, monthrange(year, month)[1]))


def count_scheduled_contributions(
    start_date: date,
    contribution_day: int,
    today: date | None = None,
    pauses: list[PlanPauseWindow] | None = None,
) -> int:
    return len(
        build_monthly_contribution_schedule(
            start_date=start_date,
            contribution_day=contribution_day,
            today=today,
            pauses=pauses,
        )
    )


def calculate_expected_contributions_total(
    start_date: date,
    contribution_day: int,
    monthly_amount: float,
    today: date | None = None,
    pauses: list[PlanPauseWindow] | None = None,
    amount_changes: list[PlanAmountChangeEvent] | None = None,
    one_off_contributions: list[PlanOneOffContributionEvent] | None = None,
) -> float:
    schedule = build_monthly_contribution_schedule(
        start_date=start_date,
        contribution_day=contribution_day,
        today=today,
        pauses=pauses,
    )
    total = 0.0
    for run_date in schedule:
        total += resolve_monthly_amount_for_date(
            default_monthly_amount=monthly_amount,
            run_date=run_date,
            amount_changes=amount_changes,
        )

    for contribution in one_off_contributions or []:
        if contribution.contribution_date <= (today or date.today()):
            total += contribution.amount
    return round(total, 2)


def next_contribution_date(
    start_date: date,
    contribution_day: int,
    today: date | None = None,
    pauses: list[PlanPauseWindow] | None = None,
) -> date | None:
    today = today or date.today()
    candidate_year = max(today.year, start_date.year)
    candidate_month = today.month if candidate_year == today.year else start_date.month

    while True:
        run_date = _scheduled_day(candidate_year, candidate_month, contribution_day)
        if (
            run_date >= start_date
            and run_date >= today
            and not _date_is_paused(run_date, pauses or [])
        ):
            return run_date
        if candidate_month == 12:
            candidate_year += 1
            candidate_month = 1
        else:
            candidate_month += 1


def build_monthly_contribution_schedule(
    *,
    start_date: date,
    contribution_day: int,
    today: date | None = None,
    pauses: list[PlanPauseWindow] | None = None,
) -> list[date]:
    today = today or date.today()
    if start_date > today:
        return []

    year = start_date.year
    month = start_date.month
    runs: list[date] = []
    while (year, month) <= (today.year, today.month):
        run_date = _scheduled_day(year, month, contribution_day)
        if (
            run_date >= start_date
            and run_date <= today
            and not _date_is_paused(run_date, pauses or [])
        ):
            runs.append(run_date)
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return runs


def resolve_monthly_amount_for_date(
    *,
    default_monthly_amount: float,
    run_date: date,
    amount_changes: list[PlanAmountChangeEvent] | None = None,
) -> float:
    amount = default_monthly_amount
    for change in sorted(amount_changes or [], key=lambda item: item.effective_date):
        if change.effective_date <= run_date:
            amount = change.monthly_amount
        else:
            break
    return amount


def _date_is_paused(run_date: date, pauses: list[PlanPauseWindow]) -> bool:
    return any(pause.start_date <= run_date <= pause.end_date for pause in pauses)
