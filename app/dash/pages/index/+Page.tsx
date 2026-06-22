import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import {
  BROWSER_CAPTURE_PROVIDERS,
  type BrowserCaptureDocument,
  type InvestmentPlan,
  type ManualTrade,
  type PortfolioOverview,
  getBrowserChartCaptureAvailability,
  getLatestBrowserChartCapture,
  getInvestmentPlans,
  getPortfolioOverview,
  getSnapshots,
  getTrades,
} from "../../src/lib/api";
import { BrowserChartButton } from "../../src/components/BrowserChartModal";
import { PlanAggregateChartButton } from "../../src/components/PlanAggregateChartModal";
import { Spinner } from "../../src/components/ui";
import {
  formatDateTime,
  formatMoney,
  formatPercent,
  formatTicker,
  normalizeTickerSymbol,
} from "../../src/lib/format";
import { buildPlanProjection } from "../../src/lib/planAnalytics";
import { queryKeys } from "../../src/lib/query";
import { useReportingCurrency } from "../../src/lib/reportingCurrency";

export default function Page() {
  const defaultProvider = BROWSER_CAPTURE_PROVIDERS[0];
  const { reportingCurrency } = useReportingCurrency();

  const overviewQuery = useQuery({
    queryKey: ["portfolio-overview", reportingCurrency],
    queryFn: () => getPortfolioOverview(reportingCurrency),
  });
  const plansQuery = useQuery({ queryKey: queryKeys.plans, queryFn: getInvestmentPlans });
  const tradesQuery = useQuery({ queryKey: queryKeys.trades, queryFn: getTrades });
  const snapshotsQuery = useQuery({ queryKey: queryKeys.snapshots, queryFn: getSnapshots });

  const tickers = useMemo(
    () =>
      Array.from(
        new Set([
          ...(overviewQuery.data?.positions ?? []).map((position) => position.ticker),
          ...(plansQuery.data ?? []).flatMap((plan) =>
            plan.targets.map((target) => normalizeTickerSymbol(target.ticker))
          ),
        ])
      ),
    [overviewQuery.data?.positions, plansQuery.data]
  );
  const availabilityQuery = useQuery({
    queryKey: queryKeys.browserCaptureAvailability(defaultProvider, tickers),
    queryFn: async () => {
      if (tickers.length === 0) {
        return { available: {}, provider: defaultProvider };
      }
      return getBrowserChartCaptureAvailability(defaultProvider, tickers);
    },
  });
  const latestCaptureQuery = useQuery({
    queryKey: queryKeys.browserCaptureLatest(defaultProvider, tickers),
    queryFn: async () => {
      const available = availabilityQuery.data?.available ?? {};
      const symbols = tickers.filter((ticker) => available[ticker]);
      const documents = await Promise.all(
        symbols.map(async (ticker) => {
          try {
            return [ticker, await getLatestBrowserChartCapture(defaultProvider, ticker)] as const;
          } catch {
            return [ticker, null] as const;
          }
        })
      );
      return Object.fromEntries(documents) as Record<string, BrowserCaptureDocument | null>;
    },
    enabled: tickers.length > 0 && availabilityQuery.isSuccess,
  });

  const loading =
    overviewQuery.isLoading ||
    plansQuery.isLoading ||
    tradesQuery.isLoading ||
    snapshotsQuery.isLoading;
  const error =
    overviewQuery.error ??
    plansQuery.error ??
    tradesQuery.error ??
    snapshotsQuery.error ??
    availabilityQuery.error;

  const overview = overviewQuery.data ?? null;
  const positions = overview?.positions ?? [];
  const plans = plansQuery.data ?? [];
  const trades = tradesQuery.data ?? [];
  const risk = overview?.risk ?? null;
  const snapshot = snapshotsQuery.data?.[0] ?? null;
  const chartAvailability = availabilityQuery.data?.available ?? {};
  const latestCaptures = latestCaptureQuery.data ?? {};
  const planRows = useMemo(
    () => buildPlanRows(plans, latestCaptures, overview),
    [latestCaptures, overview, plans]
  );
  const combinedOverview = useMemo(
    () => buildCombinedOverview(positions, planRows, risk?.currency ?? reportingCurrency),
    [planRows, positions, reportingCurrency, risk?.currency]
  );
  const topExposure = combinedOverview.topExposure;
  const allocationRows = combinedOverview.positionRows;
  const warningRows = useMemo(
    () => combineRiskWarnings(risk?.warnings ?? [], planRows, positions, combinedOverview.totalValue),
    [combinedOverview.totalValue, planRows, positions, risk?.warnings]
  );

  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Portfolio overview</span>
        <h1 className="page-title">Daily portfolio state, risk, and recent decision flow</h1>
      </header>

      {error ? <div className="status error">{error instanceof Error ? error.message : "Failed to load dashboard data"}</div> : null}
      {loading ? <div className="status">Loading portfolio overview…</div> : null}

      <section className="grid grid-3">
        <StatCard
          hint={snapshot ? `Last snapshot ${formatDateTime(snapshot.created_at)}` : "No snapshot yet"}
          label="Portfolio Value"
          value={formatMoney(combinedOverview.totalValue, combinedOverview.currency)}
        />
        <StatCard
          hint={positions.length > 0 ? "Active journal-derived holdings" : "No positions recorded yet"}
          label="Held Positions"
          value={String(positions.length)}
        />
        <StatCard
          hint="Single-name concentration"
          label="Top Exposure"
          value={topExposure ? `${formatTicker(topExposure.symbol)} ${formatPercent(topExposure.pct)}` : "—"}
        />
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <h2 className="panel-title">Investing allocation</h2>
          <p className="panel-copy">
            Current allocation is calculated from stored positions and the latest available market quotes, with plan rollups shown under the same allocation view.
          </p>
          <div className="list">
            {allocationRows.map((row) => (
              <div className="list-row" key={row.symbol}>
                <div>
                  <strong className="ticker-inline">
                    <BrowserChartButton hasChart={chartAvailability[row.symbol] ?? false} ticker={row.symbol} />
                    {formatTicker(row.symbol)}
                  </strong>
                </div>
                <div style={{ textAlign: "right" }}>
                  <strong style={{ display: "block" }}>{formatPercent(row.pct)}</strong>
                  <span
                    className="list-meta"
                    style={{
                      color:
                        row.pnl === null
                          ? undefined
                          : row.pnl >= 0
                            ? "var(--accent)"
                            : "var(--danger)",
                    }}
                  >
                    {row.pnl === null
                      ? "No chart P/L"
                      : `${row.pnl >= 0 ? "+" : "-"}${formatMoney(Math.abs(row.pnl), row.currency)}`}
                  </span>
                </div>
              </div>
            ))}
            {planRows.map((row) => (
              <div className="list-row" key={`plan-${row.name}`}>
                <div>
                  <strong className="ticker-inline">
                    <PlanAggregateChartButton latestCaptures={latestCaptures} plan={row.plan} />
                    {row.name}
                  </strong>
                </div>
                <div style={{ textAlign: "right" }}>
                  <strong style={{ display: "block" }}>
                    {formatPercent(
                      combinedOverview.totalValue > 0 ? (row.marketValue / combinedOverview.totalValue) * 100 : 0
                    )}
                  </strong>
                  <span
                    className="list-meta"
                    style={{
                      color:
                        row.pnl === null
                          ? undefined
                          : row.pnl >= 0
                            ? "var(--accent)"
                            : "var(--danger)",
                    }}
                  >
                    {row.pnl === null
                      ? <Spinner className="spinner-subtle" />
                      : `${row.pnl >= 0 ? "+" : "-"}${formatMoney(
                          Math.abs(row.pnl),
                          row.currency
                        )}`}
                  </span>
                </div>
              </div>
            ))}
            {!risk || (Object.keys(risk.ticker_allocation).length === 0 && planRows.length === 0) ? (
              <div className="warning empty">No allocation data yet. Add trades and ingest quotes first.</div>
            ) : null}
          </div>
        </div>

        <div className="panel">
          <h2 className="panel-title">Risk warnings</h2>
          <p className="panel-copy">
            High concentration and missing quote issues appear here so the hourly monitor can later reuse the same logic.
          </p>
          <div className="warning-list">
            {warningRows.length ? (
              warningRows.map((warning) => (
                <div className="warning" key={warning}>
                  {warning}
                </div>
              ))
            ) : (
              <div className="warning empty">No active warnings right now.</div>
            )}
          </div>
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <h2 className="panel-title">Recent manual trades</h2>
          <p className="panel-copy">This is the first step toward weekly evaluation and trade reviews.</p>
          <div className="list">
            {trades.slice(0, 5).map((trade) => (
              <div className="list-row" key={trade.id}>
                <div>
                  <strong>
                    {trade.action} {formatTicker(trade.ticker)}
                  </strong>
                  <span className="list-meta">
                    {trade.quantity} @ {formatMoney(trade.price, trade.currency)}
                  </span>
                </div>
                <span className="list-meta">{formatDateTime(trade.executed_at)}</span>
              </div>
            ))}
            {trades.length === 0 ? <div className="warning empty">No manual trades recorded yet.</div> : null}
          </div>
        </div>

        <div className="panel">
          <h2 className="panel-title">Snapshot status</h2>
          <p className="panel-copy">
            Daily reports will build on these stored snapshots, so this panel helps confirm the portfolio history is forming correctly.
          </p>
          {snapshot ? (
            <div className="list">
              <div className="list-row">
                <div>
                  <strong>Snapshot created</strong>
                  <span className="list-meta">{formatDateTime(snapshot.created_at)}</span>
                </div>
                <strong>{formatMoney(snapshot.total_value, snapshot.currency)}</strong>
              </div>
              <div className="list-row">
                <div>
                  <strong>Positions captured</strong>
                  <span className="list-meta">Tickers in snapshot payload</span>
                </div>
                <strong>{Object.keys(snapshot.positions ?? {}).length}</strong>
              </div>
            </div>
          ) : (
            <div className="warning empty">No snapshots stored yet. Use the Positions & Journal page to ingest quotes and create a snapshot.</div>
          )}
        </div>
      </section>
    </div>
  );
}

function StatCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="panel stat-card">
      <span className="stat-label">{label}</span>
      <strong className="stat-value">{value}</strong>
      <span className="stat-hint">{hint}</span>
    </div>
  );
}

function buildCombinedOverview(
  positions: PortfolioOverview["positions"],
  planRows: Array<{ marketValue: number; name: string }>,
  currency: string
) {
  const totalValue =
    positions.reduce((sum, position) => sum + position.market_value, 0) +
    planRows.reduce((sum, row) => sum + row.marketValue, 0);

  const positionRows = positions
    .map((position) => ({
      symbol: position.ticker,
      pct: totalValue > 0 ? (position.market_value / totalValue) * 100 : 0,
      pnl: position.pnl_native,
      currency: position.currency,
    }))
    .sort((left, right) => right.pct - left.pct);

  const topExposureCandidates = [
    ...positionRows.map((row) => ({ symbol: row.symbol, pct: row.pct })),
    ...planRows.map((row) => ({
      symbol: row.name,
      pct: totalValue > 0 ? (row.marketValue / totalValue) * 100 : 0,
    })),
  ].sort((left, right) => right.pct - left.pct);

  return {
    totalValue,
    currency,
    positionRows,
    topExposure: topExposureCandidates[0] ?? null,
  };
}

function buildPlanRows(
  plans: InvestmentPlan[],
  latestCaptures: Record<string, BrowserCaptureDocument | null>,
  overview: PortfolioOverview | null
) {
  if (!overview || overview.total_value <= 0) {
    return [];
  }

  return plans
    .map((plan) => {
      const projection = buildPlanProjection(plan, latestCaptures);
      if (!projection) {
        return null;
      }
      const marketValue = projection.currentValue ?? projection.investedTotal;
      const sectorBreakdown = buildPlanSectorBreakdown(plan, marketValue);
      return {
        plan,
        name: plan.name,
        marketValue,
        pnl: projection.pnl,
        currency: projection.currency,
        scheduledContributions: projection.scheduledContributions,
        targetCount: projection.targetCount,
        sectorBreakdown,
      };
    })
    .filter((row): row is NonNullable<typeof row> => row !== null)
    .sort((left, right) => right.marketValue - left.marketValue);
}

function combineRiskWarnings(
  baseWarnings: string[],
  planRows: Array<{ name: string; marketValue: number; sectorBreakdown: Record<string, number> }>,
  positions: PortfolioOverview["positions"],
  totalValue: number
) {
  const warnings = new Set(
    baseWarnings.filter((warning) => !warning.includes(" concentration is high at "))
  );

  for (const position of positions) {
    const pct = totalValue > 0 ? (position.market_value / totalValue) * 100 : 0;
    if (pct > 40) {
      warnings.add(`${position.ticker} concentration is high at ${pct.toFixed(2)}%`);
    }
  }

  for (const row of planRows) {
    const pct = totalValue > 0 ? (row.marketValue / totalValue) * 100 : 0;
    if (pct > 40) {
      warnings.add(`${row.name} plan concentration is high at ${pct.toFixed(2)}%`);
    }
  }

  const sectorValues = new Map<string, number>();
  for (const position of positions) {
    const sector = position.sector ?? "unknown";
    sectorValues.set(sector, (sectorValues.get(sector) ?? 0) + position.market_value);
  }
  for (const row of planRows) {
    for (const [sector, value] of Object.entries(row.sectorBreakdown)) {
      sectorValues.set(sector, (sectorValues.get(sector) ?? 0) + value);
    }
  }

  for (const [sector, value] of sectorValues.entries()) {
    const pct = totalValue > 0 ? (value / totalValue) * 100 : 0;
    if (pct > 60) {
      warnings.add(`${sector} sector concentration is high at ${pct.toFixed(2)}%`);
    }
  }

  return Array.from(warnings);
}

function buildPlanSectorBreakdown(plan: InvestmentPlan, marketValue: number) {
  const totalWeight = plan.targets.reduce((sum, target) => sum + target.weight_pct, 0);
  const normalizedWeightBase = totalWeight >= 99.5 ? totalWeight : 100;
  const breakdown: Record<string, number> = {};

  for (const target of plan.targets) {
    const sector = target.sector ?? "other";
    const weight = normalizedWeightBase > 0 ? target.weight_pct / normalizedWeightBase : 0;
    breakdown[sector] = (breakdown[sector] ?? 0) + marketValue * weight;
  }

  return breakdown;
}
