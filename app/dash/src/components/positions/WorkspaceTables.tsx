import type { Dispatch, FormEvent, SetStateAction } from "react";
import { MdDeleteForever, MdEdit } from "react-icons/md";

import { BrowserChartButton } from "../BrowserChartModal";
import { PlanAggregateChartButton } from "../PlanAggregateChartModal";
import { AccordionSection, Field, Metric, Spinner } from "../ui";
import {
  formatDateTime,
  formatMoney,
  formatPlanAllocationPercent,
  formatTicker,
  normalizeTickerInput,
} from "../../lib/format";
import {
  BROKERS,
  CURRENCIES,
  SECTORS,
  type Broker,
  type BrowserCaptureDocument,
  type BrowserCaptureTask,
  type Currency,
  type InvestmentPlan,
  type ManualTrade,
  type PortfolioSnapshot,
  type Position,
  type QuoteRefreshTask,
  type Sector,
} from "../../lib/api";
import { buildPlanProjection } from "../../lib/planAnalytics";
import type { TradeFormState } from "./types";
import { ChartActionIcon, resolveChartActionState } from "./chartActions";

type Setter<T> = Dispatch<SetStateAction<T>>;

export function TradeEntrySection({
  tradeForm,
  setTradeForm,
  editingTradeId,
  busyAction,
  onTradeSubmit,
  onCancelEditTrade,
}: {
  tradeForm: TradeFormState;
  setTradeForm: Setter<TradeFormState>;
  editingTradeId: string | null;
  busyAction: string | null;
  onTradeSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancelEditTrade: () => void;
}) {
  return (
    <div className="panel panel-subsection">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Journal</p>
          <h3 className="panel-title">{editingTradeId ? "Edit manual trade" : "Record manual trade"}</h3>
        </div>
        <span className="pill">{editingTradeId ? "Editing" : "Single entry"}</span>
      </div>
      <form className="form" onSubmit={onTradeSubmit}>
        <div className="form-grid form-grid-2">
          <Field label="Ticker">
            <input onChange={(event) => setTradeForm({ ...tradeForm, ticker: normalizeTickerInput(event.target.value) })} placeholder="NVDA" required value={formatTicker(tradeForm.ticker)} />
          </Field>
          <Field label="Action">
            <select onChange={(event) => setTradeForm({ ...tradeForm, action: event.target.value as "BUY" | "SELL" })} value={tradeForm.action}>
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </Field>
          <Field label="Quantity">
            <input min="0" onChange={(event) => setTradeForm({ ...tradeForm, quantity: event.target.value })} required step="any" type="number" value={tradeForm.quantity} />
          </Field>
          <Field label="Cash amount">
            <input min="0" onChange={(event) => setTradeForm({ ...tradeForm, price: event.target.value })} required step="any" type="number" value={tradeForm.price} />
          </Field>
          <Field label="Broker">
            <select onChange={(event) => setTradeForm({ ...tradeForm, broker: event.target.value as Broker })} value={tradeForm.broker}>
              {BROKERS.map((broker) => (
                <option key={broker} value={broker}>
                  {broker}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Currency">
            <select onChange={(event) => setTradeForm({ ...tradeForm, currency: event.target.value as Currency })} value={tradeForm.currency}>
              {CURRENCIES.map((currency) => (
                <option key={currency} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Fees">
            <input min="0" onChange={(event) => setTradeForm({ ...tradeForm, fees: event.target.value })} required step="any" type="number" value={tradeForm.fees} />
          </Field>
          <Field label="Sector">
            <select onChange={(event) => setTradeForm({ ...tradeForm, sector: event.target.value as Sector })} value={tradeForm.sector}>
              {SECTORS.map((sector) => (
                <option key={sector} value={sector}>
                  {sector}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Executed at">
            <input onChange={(event) => setTradeForm({ ...tradeForm, executed_at: event.target.value })} type="datetime-local" value={tradeForm.executed_at} />
          </Field>
          <Field label="Review date">
            <input onChange={(event) => setTradeForm({ ...tradeForm, review_date: event.target.value })} type="datetime-local" value={tradeForm.review_date} />
          </Field>
          <Field label="Thesis">
            <textarea onChange={(event) => setTradeForm({ ...tradeForm, thesis: event.target.value })} placeholder="Why this trade exists and what should prove it right" value={tradeForm.thesis} />
          </Field>
          <Field label="Thesis / notes">
            <textarea onChange={(event) => setTradeForm({ ...tradeForm, notes: event.target.value })} placeholder="What changed, why now, and what to review later" value={tradeForm.notes} />
          </Field>
        </div>
        <div className="actions-inline">
          <button className="button" disabled={busyAction === "trade"} type="submit">
            {busyAction === "trade" ? "Saving trade…" : editingTradeId ? "Update trade" : "Save trade"}
          </button>
          {editingTradeId ? (
            <button className="button secondary" onClick={onCancelEditTrade} type="button">
              Cancel edit
            </button>
          ) : null}
        </div>
      </form>
      <p className="panel-copy" style={{ marginTop: "0.75rem" }}>
        Positions are rebuilt from the journal automatically. This cash amount is the total money committed for that trade fill, not a per-share quote.
      </p>
    </div>
  );
}

export function QuoteRefreshSection({
  refreshTask,
  onRefreshHeldQuotes,
}: {
  refreshTask: QuoteRefreshTask | null;
  onRefreshHeldQuotes: () => void;
}) {
  const isRefreshQueued = refreshTask?.status === "queued";
  const isRefreshRunning = refreshTask?.status === "running";
  const refreshSummary = refreshTask
    ? `${refreshTask.stored_count} stored${refreshTask.failed_symbols.length ? `, ${refreshTask.failed_symbols.length} failed` : ""}`
    : "No background refresh queued yet.";

  return (
    <div className="panel panel-subsection">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Held quotes</p>
          <h3 className="panel-title">Refresh held quotes</h3>
        </div>
        <span className="pill">Worker queue</span>
      </div>
      <div className="stack">
        <button className="button" disabled={isRefreshQueued || isRefreshRunning} onClick={onRefreshHeldQuotes} type="button">
          {isRefreshRunning ? "Refreshing in worker…" : isRefreshQueued ? "Queued in worker…" : "Queue held quote refresh"}
        </button>
        <div className="status">
          {refreshTask ? (
            <>
              <strong style={{ display: "block", marginBottom: "0.25rem" }}>
                Status: {refreshTask.status}
              </strong>
              <span>
                {refreshSummary}
                {refreshTask.requested_symbols.length
                  ? ` across ${refreshTask.requested_symbols.length} symbols`
                  : ""}
                .
              </span>
              {refreshTask.error ? (
                <span style={{ display: "block", marginTop: "0.35rem" }}>{refreshTask.error}</span>
              ) : null}
              {refreshTask.failed_symbols.length ? (
                <span style={{ display: "block", marginTop: "0.35rem" }}>
                  Failed: {refreshTask.failed_symbols.join(", ")}
                </span>
              ) : null}
            </>
          ) : (
            "Queue the job here to let the worker throttle Yahoo calls and reduce 429 errors."
          )}
        </div>
      </div>
    </div>
  );
}

function PositionRow({
  position,
  browserCaptureAvailability,
  browserCaptureStatuses,
  busyAction,
  onQueueCnbcCapture,
}: {
  position: Position;
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
  busyAction: string | null;
  onQueueCnbcCapture: (position: Position) => void;
}) {
  const captureStatus = browserCaptureStatuses[position.ticker];
  const chartState = resolveChartActionState(captureStatus, busyAction === `queue-cnbc-${position.id}`);
  const investedAmount = position.quantity * position.average_price;

  return (
    <tr>
      <td>
        <strong className="ticker-inline">
          {formatTicker(position.ticker)}
          <BrowserChartButton hasChart={browserCaptureAvailability[position.ticker] ?? false} ticker={position.ticker} />
        </strong>
      </td>
      <td><strong>{formatMoney(investedAmount, position.currency)}</strong></td>
      <td>{position.quantity}</td>
      <td>{formatMoney(position.average_price, position.currency)}</td>
      <td>{position.broker}</td>
      <td>{position.sector ?? "—"}</td>
      <td>{formatDateTime(position.opened_at)}</td>
      <td>{position.currency}</td>
      <td>
        <div className="actions-inline">
          <button
            className="chart-action-button"
            disabled={chartState.isBlocked}
            onClick={() => onQueueCnbcCapture(position)}
            title={captureStatus?.error ?? undefined}
            type="button"
          >
            <ChartActionIcon kind={chartState.kind} title={chartState.title} />
          </button>
        </div>
      </td>
    </tr>
  );
}

function PlanPositionRow({
  plan,
  latestCaptures,
}: {
  plan: InvestmentPlan;
  latestCaptures: Record<string, BrowserCaptureDocument | null>;
}) {
  const projection = buildPlanProjection(plan, latestCaptures);
  if (!projection) {
    return null;
  }

  return (
    <tr>
      <td>
        <strong className="ticker-inline">
          {plan.name}
          <PlanAggregateChartButton latestCaptures={latestCaptures} plan={plan} />
        </strong>
      </td>
      <td><strong>{formatMoney(projection.investedTotal, projection.currency)}</strong></td>
      <td>{projection.currentValue === null ? "—" : formatMoney(projection.currentValue, projection.currency)}</td>
      <td>{projection.pnl === null ? "—" : formatMoney(projection.pnl, projection.currency)}</td>
      <td>{plan.broker}</td>
      <td>{projection.scheduledContributions}</td>
      <td>{projection.targetCount}</td>
      <td>{projection.hasAllCharts ? "Ready" : <Spinner className="spinner-subtle" />}</td>
    </tr>
  );
}

function PlanCollectiveRow({
  target,
  browserCaptureAvailability,
  browserCaptureStatuses,
}: {
  target: InvestmentPlan["targets"][number];
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
}) {
  const chartState = resolveChartActionState(browserCaptureStatuses[target.ticker], false);

  return (
    <tr>
      <td>
        <strong className="ticker-inline">
          {formatTicker(target.ticker)}
          <BrowserChartButton hasChart={browserCaptureAvailability[target.ticker] ?? false} ticker={target.ticker} />
        </strong>
      </td>
      <td>{target.weight_pct}%</td>
      <td>{target.currency}</td>
      <td>{target.sector ?? "—"}</td>
      <td>{target.composition_sectors.length > 0 ? target.composition_sectors.join(", ") : "—"}</td>
      <td><ChartActionIcon kind={chartState.kind} title={chartState.title} /></td>
    </tr>
  );
}

function PlanCollectiveCard({
  plan,
  latestCaptures,
  browserCaptureAvailability,
  browserCaptureStatuses,
}: {
  plan: InvestmentPlan;
  latestCaptures: Record<string, BrowserCaptureDocument | null>;
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
}) {
  const projection = buildPlanProjection(plan, latestCaptures);

  return (
    <details className="panel panel-subsection">
      <summary className="accordion-summary">
        <div>
          <p className="panel-kicker">Plan collective</p>
          <h3 className="panel-title">{plan.name}</h3>
          <p className="panel-copy">
            {formatMoney(plan.monthly_amount, plan.currency)} monthly, {plan.targets.length} ETFs, target allocation{" "}
            {formatPlanAllocationPercent(plan.target_allocation_total)}
          </p>
        </div>
        <div className="accordion-summary-meta">
          <span className="pill">{plan.broker}</span>
          <span className="accordion-chevron" aria-hidden="true">
            ▾
          </span>
        </div>
      </summary>
      <div className="accordion-body">
        <div className="stats-grid" style={{ marginBottom: "1rem" }}>
          <Metric label="Start" value={plan.start_date} />
          <Metric label="Next run" value={plan.next_run_on ?? "—"} />
          <Metric label="Expected total" value={formatMoney(plan.expected_contributions_total, plan.currency)} />
          <Metric label="Target allocation" value={formatPlanAllocationPercent(plan.target_allocation_total)} />
          {projection ? (
            <>
              <Metric
                label="Projected value"
                value={projection.currentValue === null ? "Waiting for charts" : formatMoney(projection.currentValue, projection.currency)}
              />
              <Metric
                label="Projected P/L"
                value={projection.pnl === null ? "—" : formatMoney(projection.pnl, projection.currency)}
              />
            </>
          ) : null}
        </div>
        {plan.targets.length === 0 ? (
          <div className="empty-state">No ETFs configured in this plan yet.</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>Target %</th>
                <th>Currency</th>
                <th>Sector</th>
                <th>Composition</th>
                <th>Chart</th>
              </tr>
            </thead>
            <tbody>
              {plan.targets.map((target) => (
                <PlanCollectiveRow
                  browserCaptureAvailability={browserCaptureAvailability}
                  browserCaptureStatuses={browserCaptureStatuses}
                  key={target.id}
                  target={target}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </details>
  );
}

export function PositionsSection({
  browserCaptureAvailability,
  latestCaptures,
  positions,
  plans,
  browserCaptureStatuses,
  busyAction,
  onQueueCnbcCapture,
}: {
  browserCaptureAvailability: Record<string, boolean>;
  latestCaptures: Record<string, BrowserCaptureDocument | null>;
  positions: Position[];
  plans: InvestmentPlan[];
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
  busyAction: string | null;
  onQueueCnbcCapture: (position: Position) => void;
}) {
  const sortedPositions = [...positions].sort(
    (left, right) =>
      right.quantity * right.average_price - left.quantity * left.average_price
  );

  return (
    <AccordionSection badge={`${positions.length} tracked`} defaultOpen kicker="Portfolio ledger" title="Positions">
      {positions.length === 0 ? (
        <div className="empty-state">No positions saved yet. Record trades in the journal to build them automatically.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Invested</th>
              <th>Qty</th>
              <th>Avg Price</th>
              <th>Broker</th>
              <th>Sector</th>
              <th>Opened</th>
              <th>Currency</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sortedPositions.map((position) => (
              <PositionRow
                browserCaptureAvailability={browserCaptureAvailability}
                browserCaptureStatuses={browserCaptureStatuses}
                busyAction={busyAction}
                key={position.id}
                onQueueCnbcCapture={onQueueCnbcCapture}
                position={position}
              />
            ))}
          </tbody>
        </table>
      )}

      {plans.some((plan) => buildPlanProjection(plan, latestCaptures)) ? (
        <div style={{ marginTop: "1rem" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Plan</th>
                <th>Invested</th>
                <th>Current Value</th>
                <th>P/L</th>
                <th>Broker</th>
                <th>Buys</th>
                <th>ETFs</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((plan) => (
                <PlanPositionRow key={`projection-${plan.id}`} latestCaptures={latestCaptures} plan={plan} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {plans.length > 0 ? (
        <div className="stack" style={{ marginTop: positions.length > 0 ? "1rem" : 0 }}>
          {plans.map((plan) => (
            <PlanCollectiveCard
              latestCaptures={latestCaptures}
              browserCaptureAvailability={browserCaptureAvailability}
              browserCaptureStatuses={browserCaptureStatuses}
              key={plan.id}
              plan={plan}
            />
          ))}
        </div>
      ) : null}
    </AccordionSection>
  );
}

export function TradesSection({
  trades,
  busyAction,
  onStartEditTrade,
  onDeleteTrade,
}: {
  trades: ManualTrade[];
  busyAction: string | null;
  onStartEditTrade: (trade: ManualTrade) => void;
  onDeleteTrade: (tradeId: string) => void;
}) {
  const hasAnyTradeNotes = trades.some((trade) => Boolean((trade.notes ?? trade.thesis)?.trim()));

  return (
    <AccordionSection badge={`${trades.length} entries`} defaultOpen kicker="Manual trading log" title="Trade journal">
      {trades.length === 0 ? (
        <div className="empty-state">No manual trades recorded yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Ticker</th>
              <th>Action</th>
              <th>Qty</th>
              <th>Price</th>
              <th>Broker</th>
              <th>Fees</th>
              <th>Review</th>
              {hasAnyTradeNotes ? <th>Notes</th> : null}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {trades.map((trade) => (
              <tr key={trade.id}>
                <td>{formatDateTime(trade.executed_at)}</td>
                <td><strong>{formatTicker(trade.ticker)}</strong></td>
                <td>{trade.action}</td>
                <td>{trade.quantity}</td>
                <td>{formatMoney(trade.price, trade.currency)}</td>
                <td>{trade.broker}</td>
                <td>{formatMoney(trade.fees, trade.currency)}</td>
                <td>{formatDateTime(trade.review_date)}</td>
                {hasAnyTradeNotes ? <td>{trade.notes ?? trade.thesis ?? "—"}</td> : null}
                <td>
                  <div className="actions-inline">
                    <button
                      aria-label={`Edit ${trade.action} ${formatTicker(trade.ticker)}`}
                      className="chart-action-button"
                      onClick={() => onStartEditTrade(trade)}
                      type="button"
                    >
                      <MdEdit />
                    </button>
                    <button
                      aria-label={`Delete ${trade.action} ${formatTicker(trade.ticker)}`}
                      className="chart-action-button"
                      disabled={busyAction === `delete-trade-${trade.id}`}
                      onClick={() => onDeleteTrade(trade.id)}
                      type="button"
                    >
                      {busyAction === `delete-trade-${trade.id}` ? "Deleting…" : <MdDeleteForever />}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AccordionSection>
  );
}

export function SnapshotsSection({
  snapshots,
  busyAction,
  onDeleteSnapshot,
}: {
  snapshots: PortfolioSnapshot[];
  busyAction: string | null;
  onDeleteSnapshot: (snapshotId: string) => void;
}) {
  return (
    <AccordionSection badge={`${snapshots.length} saved`} kicker="History" title="Snapshots">
      {snapshots.length === 0 ? (
        <></>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Created</th>
              <th>Total value</th>
              <th>Holdings</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((snapshot) => (
              <tr key={snapshot.id}>
                <td>{formatDateTime(snapshot.created_at)}</td>
                <td>{formatMoney(snapshot.total_value, snapshot.currency)}</td>
                <td>{Object.keys(snapshot.positions ?? {}).length}</td>
                <td>
                  <button
                    aria-label={`Delete snapshot from ${formatDateTime(snapshot.created_at)}`}
                    className="chart-action-button"
                    disabled={busyAction === `delete-snapshot-${snapshot.id}`}
                    onClick={() => onDeleteSnapshot(snapshot.id)}
                    type="button"
                  >
                    {busyAction === `delete-snapshot-${snapshot.id}` ? "Deleting…" : <MdDeleteForever />}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AccordionSection>
  );
}
