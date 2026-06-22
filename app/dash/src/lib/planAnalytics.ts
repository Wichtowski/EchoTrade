import type { BrowserCaptureDocument, InvestmentPlan } from "./api";
import { extractLatestClose, extractPriceBars, extractRanges, type ChartPoint } from "./browserCharts";

export type PlanContribution = {
  id: string;
  ticker: string;
  amount: number;
  executed_at: string;
  price: number;
  action: "BUY";
};

export type PlanProjection = {
  planId: string;
  name: string;
  currency: string;
  investedTotal: number;
  currentValue: number | null;
  pnl: number | null;
  scheduledContributions: number;
  targetCount: number;
  hasFullAllocation: boolean;
  hasAllCharts: boolean;
  contributions: PlanContribution[];
  documents: Record<string, BrowserCaptureDocument | null>;
  activeTickers: string[];
};

export type PlanTickerProjectionSummary = {
  ticker: string;
  investedAmount: number;
  currentValue: number | null;
  pnl: number | null;
  contributionCount: number;
  latestClose: number | null;
};

type PricePoint = {
  time: string;
  timeMs: number;
  close: number;
};

export function isPlanReadyForProjection(plan: Pick<InvestmentPlan, "targets" | "target_allocation_total">): boolean {
  return plan.targets.length > 0 && plan.target_allocation_total >= 99.5;
}

export function buildPlanProjection(
  plan: InvestmentPlan,
  latestCaptures: Record<string, BrowserCaptureDocument | null>
): PlanProjection | null {
  const hasFullAllocation = isPlanReadyForProjection(plan);
  const targetWeightTotal = plan.targets.reduce((sum, target) => sum + target.weight_pct, 0);
  const normalizedWeightBase = targetWeightTotal >= 99.5 ? targetWeightTotal : 100;
  const targetDocuments = Object.fromEntries(
    plan.targets.map((target) => [target.ticker, latestCaptures[target.ticker] ?? null])
  );
  const hasAllCharts =
    hasFullAllocation &&
    plan.targets.every((target) => {
      const document = targetDocuments[target.ticker];
      return Boolean(document && extractLatestClose(document) !== null);
    });

  if (!hasFullAllocation) {
    return null;
  }

  const schedule = buildContributionSchedule(plan);
  const contributions: PlanContribution[] = [];

  for (const scheduledEvent of schedule) {
    for (const target of plan.targets) {
      const weight = normalizedWeightBase > 0 ? target.weight_pct / normalizedWeightBase : 0;
      if (weight <= 0) {
        continue;
      }
      const points = collectSortedPricePoints(targetDocuments[target.ticker]);
      const matchedPoint = findExecutionPoint(points, scheduledEvent.runAt.getTime());
      if (!matchedPoint) {
        continue;
      }
      const amount = scheduledEvent.amount * weight;
      contributions.push({
        id: `${plan.id}:${target.ticker}:${scheduledEvent.kind}:${scheduledEvent.sequence}`,
        ticker: target.ticker,
        amount,
        executed_at: matchedPoint.time,
        price: amount,
        action: "BUY",
      });
    }
  }

  const currentValue = hasAllCharts ? calculatePlanCurrentValue(contributions, targetDocuments) : null;
  const investedTotal = roundCurrency(schedule.reduce((sum, item) => sum + item.amount, 0));

  return {
    planId: plan.id,
    name: plan.name,
    currency: plan.currency,
    investedTotal,
    currentValue,
    pnl: currentValue === null ? null : currentValue - investedTotal,
    scheduledContributions: plan.scheduled_contributions,
    targetCount: plan.targets.length,
    hasFullAllocation,
    hasAllCharts,
    contributions,
    documents: targetDocuments,
    activeTickers: plan.targets.map((target) => target.ticker),
  };
}

export function buildProjectedPlanSeries(
  projection: PlanProjection,
  selectedRange: string
): ChartPoint[] {
  const seriesByTicker = Object.entries(projection.documents)
    .map(([ticker, document]) => ({
      ticker,
      points: collectRangePoints(document, selectedRange),
    }))
    .filter((entry) => entry.points.length > 0);

  const timestamps = Array.from(
    new Set(seriesByTicker.flatMap((entry) => entry.points.map((point) => point.timeMs)))
  ).sort((left, right) => left - right);

  return timestamps
    .map((timeMs, index) => {
      let totalValue = 0;
      for (const contribution of projection.contributions) {
        const contributionTimeMs = new Date(contribution.executed_at).getTime();
        if (Number.isNaN(contributionTimeMs) || contributionTimeMs > timeMs) {
          continue;
        }
        const tickerSeries = seriesByTicker.find((entry) => entry.ticker === contribution.ticker);
        if (!tickerSeries) {
          continue;
        }
        const latestPoint = findLatestPoint(tickerSeries.points, timeMs);
        const entryPoint = findLatestPoint(tickerSeries.points, contributionTimeMs);
        if (!latestPoint || !entryPoint || entryPoint.close <= 0) {
          continue;
        }
        totalValue += contribution.amount * (latestPoint.close / entryPoint.close);
      }
      return {
        index,
        close: totalValue,
        tickLabel: new Date(timeMs).toLocaleDateString("en-GB", { month: "short", day: "numeric" }),
        time: new Date(timeMs).toISOString(),
        timeMs,
      };
    })
    .filter((point) => point.close > 0);
}

export function summarizePlanProjectionByTicker(
  projection: PlanProjection
): PlanTickerProjectionSummary[] {
  return projection.activeTickers.map((ticker) => {
    const tickerContributions = projection.contributions.filter((item) => item.ticker === ticker);
    const investedAmount = tickerContributions.reduce((sum, item) => sum + item.amount, 0);
    const document = projection.documents[ticker] ?? null;
    const latestClose = extractLatestClose(document);
    let currentValue = 0;

    for (const contribution of tickerContributions) {
      const entryPoint = findExecutionPoint(
        collectSortedPricePoints(document),
        new Date(contribution.executed_at).getTime()
      );
      if (latestClose === null || !entryPoint || entryPoint.close <= 0) {
        currentValue = Number.NaN;
        break;
      }
      currentValue += contribution.amount * (latestClose / entryPoint.close);
    }

    return {
      ticker,
      investedAmount,
      currentValue: Number.isNaN(currentValue) ? null : currentValue,
      pnl: Number.isNaN(currentValue) ? null : currentValue - investedAmount,
      contributionCount: tickerContributions.length,
      latestClose,
    };
  });
}

function calculatePlanCurrentValue(
  contributions: PlanContribution[],
  documents: Record<string, BrowserCaptureDocument | null>
): number {
  let total = 0;
  for (const contribution of contributions) {
    const document = documents[contribution.ticker];
    const latestClose = extractLatestClose(document);
    const entryPoint = findExecutionPoint(collectSortedPricePoints(document), new Date(contribution.executed_at).getTime());
    if (latestClose === null || !entryPoint || entryPoint.close <= 0) {
      continue;
    }
    total += contribution.amount * (latestClose / entryPoint.close);
  }
  return total;
}

function buildContributionSchedule(plan: InvestmentPlan) {
  const start = new Date(`${plan.start_date}T00:00:00`);
  if (Number.isNaN(start.getTime())) {
    return [];
  }
  const today = new Date();
  const pauses = plan.pauses.map((pause) => ({
    start: new Date(`${pause.start_date}T00:00:00`).getTime(),
    end: new Date(`${pause.end_date}T23:59:59`).getTime(),
  }));
  const amountChanges = [...plan.amount_changes].sort((left, right) =>
    new Date(left.effective_date).getTime() - new Date(right.effective_date).getTime()
  );
  const events: Array<{ kind: "monthly" | "one_off"; runAt: Date; amount: number; sequence: number }> = [];
  let year = start.getUTCFullYear();
  let month = start.getUTCMonth();
  let sequence = 0;
  while ((year < today.getUTCFullYear()) || (year === today.getUTCFullYear() && month <= today.getUTCMonth())) {
    const day = Math.min(plan.contribution_day, daysInMonthUtc(year, month));
    const runAt = new Date(Date.UTC(year, month, day, 12, 0, 0));
    const isPaused = pauses.some((pause) => runAt.getTime() >= pause.start && runAt.getTime() <= pause.end);
    if (runAt >= start && runAt <= today && !isPaused) {
      events.push({
        kind: "monthly",
        runAt,
        amount: resolveMonthlyAmount(plan.monthly_amount, amountChanges, runAt),
        sequence: sequence++,
      });
    }
    month += 1;
    if (month > 11) {
      month = 0;
      year += 1;
    }
  }

  for (const contribution of plan.one_off_contributions) {
    const runAt = new Date(`${contribution.contribution_date}T12:00:00`);
    if (!Number.isNaN(runAt.getTime()) && runAt >= start && runAt <= today) {
      events.push({
        kind: "one_off",
        runAt,
        amount: contribution.amount,
        sequence: sequence++,
      });
    }
  }

  return events.sort((left, right) => left.runAt.getTime() - right.runAt.getTime());
}

function daysInMonthUtc(year: number, month: number) {
  return new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
}

function resolveMonthlyAmount(
  defaultAmount: number,
  amountChanges: InvestmentPlan["amount_changes"],
  runAt: Date
) {
  let amount = defaultAmount;
  for (const change of amountChanges) {
    const effectiveAt = new Date(`${change.effective_date}T00:00:00`);
    if (!Number.isNaN(effectiveAt.getTime()) && effectiveAt <= runAt) {
      amount = change.monthly_amount;
    } else {
      break;
    }
  }
  return amount;
}

function roundCurrency(value: number) {
  return Math.round(value * 100) / 100;
}

function collectSortedPricePoints(document: BrowserCaptureDocument | null): PricePoint[] {
  if (!document) {
    return [];
  }
  const seen = new Map<number, PricePoint>();
  for (const payload of Object.values(extractRanges(document.document))) {
    for (const bar of extractPriceBars(payload)) {
      const time = extractBarTime(bar.tradeTime, bar.tradeTimeinMills);
      const close = Number.parseFloat(bar.close);
      if (!time || !Number.isFinite(close)) {
        continue;
      }
      const timeMs = new Date(time).getTime();
      if (Number.isNaN(timeMs)) {
        continue;
      }
      seen.set(timeMs, { time, timeMs, close });
    }
  }
  return Array.from(seen.values()).sort((left, right) => left.timeMs - right.timeMs);
}

function collectRangePoints(document: BrowserCaptureDocument | null, range: string): PricePoint[] {
  if (!document) {
    return [];
  }
  return extractPriceBars(extractRanges(document.document)[range])
    .map((bar) => {
      const time = extractBarTime(bar.tradeTime, bar.tradeTimeinMills);
      const close = Number.parseFloat(bar.close);
      if (!time || !Number.isFinite(close)) {
        return null;
      }
      const timeMs = new Date(time).getTime();
      return Number.isNaN(timeMs) ? null : { time, timeMs, close };
    })
    .filter((point): point is PricePoint => point !== null)
    .sort((left, right) => left.timeMs - right.timeMs);
}

function extractBarTime(tradeTime?: string, tradeTimeinMills?: string) {
  if (tradeTime) {
    const parsed = new Date(tradeTime);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }
  if (tradeTimeinMills) {
    const raw = Number.parseInt(tradeTimeinMills, 10);
    if (Number.isFinite(raw)) {
      const normalized = raw < 10_000_000_000 ? raw * 1000 : raw;
      const parsed = new Date(normalized);
      if (!Number.isNaN(parsed.getTime())) {
        return parsed.toISOString();
      }
    }
  }
  return null;
}

function findExecutionPoint(points: PricePoint[], scheduledTimeMs: number): PricePoint | null {
  const nextPoint = points.find((point) => point.timeMs >= scheduledTimeMs);
  if (nextPoint) {
    return nextPoint;
  }
  return findLatestPoint(points, scheduledTimeMs);
}

function findLatestPoint(points: PricePoint[], targetTimeMs: number): PricePoint | null {
  let latest: PricePoint | null = null;
  for (const point of points) {
    if (point.timeMs > targetTimeMs) {
      break;
    }
    latest = point;
  }
  return latest;
}
