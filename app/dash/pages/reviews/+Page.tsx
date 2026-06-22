import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type Currency,
  type OpportunityScan,
  type WeeklyReview,
  getInvestmentPlans,
  getOpportunityScans,
  getWeeklyReviews,
  runOpportunityScan,
  runWeeklyReview,
} from "../../src/lib/api";
import { formatDateTime, formatMoney, formatPercent, formatTicker } from "../../src/lib/format";
import { queryKeys } from "../../src/lib/query";
import { useReportingCurrency } from "../../src/lib/reportingCurrency";
import { Spinner } from "../../src/components/ui";

export default function Page() {
  const queryClient = useQueryClient();
  const { reportingCurrency } = useReportingCurrency();
  const [periodDays, setPeriodDays] = useState("7");
  const [selectedPlanId, setSelectedPlanId] = useState("");
  const [scanCadence, setScanCadence] = useState("manual");
  const [scanLimit, setScanLimit] = useState("12");
  const [tickerInput, setTickerInput] = useState("");
  const [status, setStatus] = useState<{ kind: "success" | "error"; message: string } | null>(null);

  const weeklyReviewsQuery = useQuery({
    queryKey: queryKeys.weeklyReviews,
    queryFn: getWeeklyReviews,
  });
  const scansQuery = useQuery({
    queryKey: queryKeys.opportunityScans,
    queryFn: getOpportunityScans,
  });
  const plansQuery = useQuery({
    queryKey: queryKeys.plans,
    queryFn: getInvestmentPlans,
  });

  const weeklyReviewMutation = useMutation({
    mutationFn: () =>
      runWeeklyReview({
        reporting_currency: reportingCurrency,
        period_days: Number(periodDays) || 7,
      }),
    onSuccess: async (review) => {
      setStatus({ kind: "success", message: `Weekly review stored for ${review.period_start.slice(0, 10)} to ${review.period_end.slice(0, 10)}.` });
      await queryClient.invalidateQueries({ queryKey: queryKeys.weeklyReviews });
    },
    onError: (error) => {
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Failed to run weekly review" });
    },
  });

  const opportunityScanMutation = useMutation({
    mutationFn: () =>
      runOpportunityScan({
        cadence: scanCadence,
        limit: Number(scanLimit) || 12,
        plan_id: selectedPlanId || null,
        tickers: parseTickerInput(tickerInput),
      }),
    onSuccess: async (scan) => {
      setStatus({ kind: "success", message: `Opportunity scan stored with ${scan.candidate_count} candidates.` });
      await queryClient.invalidateQueries({ queryKey: queryKeys.opportunityScans });
    },
    onError: (error) => {
      setStatus({ kind: "error", message: error instanceof Error ? error.message : "Failed to run opportunity scan" });
    },
  });

  const loading = weeklyReviewsQuery.isLoading || scansQuery.isLoading || plansQuery.isLoading;
  const error = weeklyReviewsQuery.error ?? scansQuery.error ?? plansQuery.error;

  const latestReview = weeklyReviewsQuery.data?.[0] ?? null;
  const latestScan = scansQuery.data?.[0] ?? null;
  const reviewWarnings = latestReview?.warnings ?? [];
  const cadencePresets = useMemo(
    () => [
      { label: "Manual", value: "manual" },
      { label: "Monday", value: "monday" },
      { label: "Wednesday", value: "wednesday" },
      { label: "Friday", value: "friday" },
    ],
    []
  );

  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Opportunity scans & Reviews</span>
        <h1 className="page-title">Weekly evaluation and opportunity scans</h1>
        <p className="page-copy">
          This is where EchoTrade starts learning from the portfolio state instead of only storing it. Run weekly reviews, compare drift, and keep a ranked research queue.
        </p>
      </header>

      {status ? <div className={`status${status.kind === "error" ? " error" : ""}`}>{status.message}</div> : null}
      {error ? <div className="status error">{error instanceof Error ? error.message : "Failed to load review data"}</div> : null}
      {loading ? <div className="status">Loading review workspace…</div> : null}

      <section className="grid grid-3">
        <StatCard
          label="Latest Review"
          value={latestReview ? formatDateTime(latestReview.created_at) : "—"}
          hint={latestReview ? `${latestReview.trade_count} trades in window` : "No weekly review stored yet"}
        />
        <StatCard
          label="Review Delta"
          value={
            latestReview?.total_value_change != null
              ? `${latestReview.total_value_change >= 0 ? "+" : "-"}${formatMoney(Math.abs(latestReview.total_value_change), latestReview.reporting_currency)}`
              : "—"
          }
          hint="Compared against the prior compatible snapshot"
        />
        <StatCard
          label="Latest Scan"
          value={latestScan ? String(latestScan.candidate_count) : "—"}
          hint={latestScan ? `${latestScan.cadence} cadence` : "No opportunity scan stored yet"}
        />
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Weekly evaluation</p>
              <h2 className="panel-title">Run weekly review</h2>
              <p className="panel-copy">Create a stored weekly evaluation from current positions, quotes, snapshots, and journal follow-up dates.</p>
            </div>
            <span className="pill">{reportingCurrency}</span>
          </div>
          <div className="form-grid form-grid-2">
            <div className="field">
              <label htmlFor="period-days">Lookback window</label>
              <select id="period-days" onChange={(event) => setPeriodDays(event.target.value)} value={periodDays}>
                <option value="7">7 days</option>
                <option value="10">10 days</option>
                <option value="14">14 days</option>
              </select>
            </div>
            <div className="field">
              <label>Reporting currency</label>
              <div className="status">{reportingCurrency}</div>
            </div>
          </div>
          <div className="page-toolbar-inline">
            <button className="button" disabled={weeklyReviewMutation.isPending} onClick={() => weeklyReviewMutation.mutate()} type="button">
              {weeklyReviewMutation.isPending ? <Spinner /> : null}
              Run weekly review
            </button>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <p className="panel-kicker">Research queue</p>
              <h2 className="panel-title">Run opportunity scan</h2>
              <p className="panel-copy">Scan plan targets, manual ticker lists, or held names and store a ranked follow-up queue.</p>
            </div>
          </div>
          <div className="form-grid form-grid-2">
            <div className="field">
              <label htmlFor="scan-plan">Plan scope</label>
              <select id="scan-plan" onChange={(event) => setSelectedPlanId(event.target.value)} value={selectedPlanId}>
                <option value="">All available inputs</option>
                {(plansQuery.data ?? []).map((plan) => (
                  <option key={plan.id} value={plan.id}>
                    {plan.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="scan-cadence">Cadence label</label>
              <select id="scan-cadence" onChange={(event) => setScanCadence(event.target.value)} value={scanCadence}>
                {cadencePresets.map((preset) => (
                  <option key={preset.value} value={preset.value}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="scan-limit">Candidate limit</label>
              <input id="scan-limit" min="1" max="50" onChange={(event) => setScanLimit(event.target.value)} step="1" type="number" value={scanLimit} />
            </div>
            <div className="field">
              <label htmlFor="scan-tickers">Optional manual tickers</label>
              <input id="scan-tickers" onChange={(event) => setTickerInput(event.target.value)} placeholder="NVDA, AMD, ASML" value={tickerInput} />
            </div>
          </div>
          <div className="page-toolbar-inline">
            <button className="button" disabled={opportunityScanMutation.isPending} onClick={() => opportunityScanMutation.mutate()} type="button">
              {opportunityScanMutation.isPending ? <Spinner /> : null}
              Run opportunity scan
            </button>
          </div>
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <h2 className="panel-title">Latest weekly review</h2>
          {latestReview ? <WeeklyReviewCard review={latestReview} /> : <div className="warning empty">No weekly review stored yet.</div>}
        </div>
        <div className="panel">
          <h2 className="panel-title">Latest opportunity scan</h2>
          {latestScan ? <OpportunityScanCard scan={latestScan} /> : <div className="warning empty">No opportunity scan stored yet.</div>}
        </div>
      </section>

      <section className="grid grid-2">
        <div className="panel">
          <h2 className="panel-title">Weekly review history</h2>
          <div className="list">
            {(weeklyReviewsQuery.data ?? []).map((review) => (
              <div className="list-row" key={review.id}>
                <div>
                  <strong>{formatDateTime(review.created_at)}</strong>
                  <span className="list-meta">
                    {review.trade_count} trades · {review.buy_count} buys · {review.sell_count} sells
                  </span>
                </div>
                <span className="list-meta">
                  {review.total_value_change != null ? `${review.total_value_change >= 0 ? "+" : "-"}${formatMoney(Math.abs(review.total_value_change), review.reporting_currency)}` : "No prior comparison"}
                </span>
              </div>
            ))}
            {(weeklyReviewsQuery.data ?? []).length === 0 ? <div className="warning empty">Weekly reviews will appear here after the first run.</div> : null}
          </div>
        </div>
        <div className="panel">
          <h2 className="panel-title">Scan history</h2>
          <div className="list">
            {(scansQuery.data ?? []).map((scan) => (
              <div className="list-row" key={scan.id}>
                <div>
                  <strong>{formatDateTime(scan.created_at)}</strong>
                  <span className="list-meta">
                    {scan.cadence} · {scan.candidate_count} candidates
                  </span>
                </div>
                <span className="list-meta">{scan.tickers.slice(0, 3).map(formatTicker).join(", ") || "No tickers"}</span>
              </div>
            ))}
            {(scansQuery.data ?? []).length === 0 ? <div className="warning empty">Opportunity scans will appear here after the first run.</div> : null}
          </div>
        </div>
      </section>

      {reviewWarnings.length ? (
        <section className="panel">
          <h2 className="panel-title">Current review warnings</h2>
          <div className="warning-list">
            {reviewWarnings.map((warning) => (
              <div className="warning" key={warning}>
                {warning}
              </div>
            ))}
          </div>
        </section>
      ) : null}
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

function WeeklyReviewCard({ review }: { review: WeeklyReview }) {
  return (
    <div className="stack">
      <div className="status">{review.summary}</div>
      <div className="stats-grid stats-grid-3">
        <Metric label="Portfolio value" value={formatMoney(review.total_value, review.reporting_currency)} />
        <Metric label="Trades" value={String(review.trade_count)} />
        <Metric label="Due reviews" value={String(review.due_review_tickers.length)} />
      </div>

      <div className="grid grid-2">
        <div>
          <p className="panel-kicker">Top winners</p>
          <div className="list">
            {review.top_winners.map((item) => (
              <div className="list-row" key={`winner-${item.ticker}`}>
                <div>
                  <strong>{formatTicker(item.ticker)}</strong>
                  <span className="list-meta">{formatPercent(item.allocation_pct)}</span>
                </div>
                <span className="list-meta">{`${item.pnl >= 0 ? "+" : "-"}${formatMoney(Math.abs(item.pnl), review.reporting_currency)}`}</span>
              </div>
            ))}
            {review.top_winners.length === 0 ? <div className="warning empty">No winning positions in this window.</div> : null}
          </div>
        </div>
        <div>
          <p className="panel-kicker">Top losers</p>
          <div className="list">
            {review.top_losers.map((item) => (
              <div className="list-row" key={`loser-${item.ticker}`}>
                <div>
                  <strong>{formatTicker(item.ticker)}</strong>
                  <span className="list-meta">{formatPercent(item.allocation_pct)}</span>
                </div>
                <span className="list-meta">{`${item.pnl >= 0 ? "+" : "-"}${formatMoney(Math.abs(item.pnl), review.reporting_currency)}`}</span>
              </div>
            ))}
            {review.top_losers.length === 0 ? <div className="warning empty">No losing positions in this window.</div> : null}
          </div>
        </div>
      </div>

      <div className="list">
        {review.insights.map((insight) => (
          <div className="list-row" key={insight}>
            <span className="list-meta">{insight}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function OpportunityScanCard({ scan }: { scan: OpportunityScan }) {
  return (
    <div className="stack">
      <div className="status">{scan.summary}</div>
      <div className="list">
        {scan.candidates.slice(0, 8).map((candidate) => (
          <div className="list-row" key={candidate.ticker}>
            <div>
              <strong>{formatTicker(candidate.ticker)}</strong>
              <span className="list-meta">
                {candidate.source.replaceAll("_", " ")} · score {candidate.score.toFixed(1)}
              </span>
            </div>
            <div style={{ textAlign: "right" }}>
              <strong>{candidate.latest_price != null && candidate.currency ? formatMoney(candidate.latest_price, candidate.currency) : "—"}</strong>
              <span className="list-meta">
                {candidate.notes[0] ?? "No notes"}
              </span>
            </div>
          </div>
        ))}
        {scan.candidates.length === 0 ? <div className="warning empty">No ranked candidates were returned.</div> : null}
      </div>
      {scan.warnings.length ? (
        <div className="warning-list">
          {scan.warnings.map((warning) => (
            <div className="warning" key={warning}>
              {warning}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric-card">
      <span className="metric-label">{label}</span>
      <strong className="metric-value">{value}</strong>
    </div>
  );
}

function parseTickerInput(value: string) {
  return value
    .split(",")
    .map((ticker) => ticker.trim().toUpperCase())
    .filter(Boolean);
}
