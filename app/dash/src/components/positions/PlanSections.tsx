import type { Dispatch, FormEvent, SetStateAction } from "react";
import { useState } from "react";
import { MdDeleteForever, MdEdit } from "react-icons/md";

import { BrowserChartButton } from "../BrowserChartModal";
import { AccordionSection, Field, Metric } from "../ui";
import {
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
  type BrowserCaptureTask,
  type Currency,
  type InvestmentPlan,
  type InvestmentPlanTarget,
  type Sector,
} from "../../lib/api";
import type {
  PlanAmountChangeFormState,
  PlanFormState,
  PlanOneOffContributionFormState,
  PlanPauseFormState,
  PlanTargetFormState,
} from "./types";
import { ChartActionIcon, resolveChartActionState } from "./chartActions";

type Setter<T> = Dispatch<SetStateAction<T>>;

const emptyPauseForm: PlanPauseFormState = {
  plan_id: "",
  start_date: "",
  end_date: "",
  reason: "",
};

const emptyAmountChangeForm: PlanAmountChangeFormState = {
  plan_id: "",
  effective_date: "",
  monthly_amount: "",
  note: "",
};

const emptyOneOffForm: PlanOneOffContributionFormState = {
  plan_id: "",
  contribution_date: "",
  amount: "",
  note: "",
};

function PlanEditorForm({
  planForm,
  setPlanForm,
  busyAction,
  isEditing,
  onSubmit,
  onCancel,
}: {
  planForm: PlanFormState;
  setPlanForm: Setter<PlanFormState>;
  busyAction: string | null;
  isEditing: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel?: () => void;
}) {
  return (
    <div className="panel panel-subsection">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Recurring investing</p>
          <h3 className="panel-title">{isEditing ? "Edit investment plan" : "Add investment plan"}</h3>
        </div>
        <span className="pill">{isEditing ? "Editing" : "Monthly schedule"}</span>
      </div>
      <form className="form" onSubmit={onSubmit}>
        <Field label="Plan name">
          <input onChange={(event) => setPlanForm({ ...planForm, name: event.target.value })} placeholder="XTB Auto-Invest" required value={planForm.name} />
        </Field>
        <Field label="Broker">
          <select onChange={(event) => setPlanForm({ ...planForm, broker: event.target.value as Broker })} value={planForm.broker}>
            {BROKERS.map((broker) => (
              <option key={broker} value={broker}>
                {broker}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Monthly amount">
          <input min="0" onChange={(event) => setPlanForm({ ...planForm, monthly_amount: event.target.value })} required step="any" type="number" value={planForm.monthly_amount} />
        </Field>
        <Field label="Currency">
          <select onChange={(event) => setPlanForm({ ...planForm, currency: event.target.value as Currency })} value={planForm.currency}>
            {CURRENCIES.map((currency) => (
              <option key={currency} value={currency}>
                {currency}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Contribution day">
          <input max="31" min="1" onChange={(event) => setPlanForm({ ...planForm, contribution_day: event.target.value })} required step="1" type="number" value={planForm.contribution_day} />
        </Field>
        <Field label="Start date">
          <input onChange={(event) => setPlanForm({ ...planForm, start_date: event.target.value })} required type="date" value={planForm.start_date} />
        </Field>
        <Field label="Notes">
          <textarea onChange={(event) => setPlanForm({ ...planForm, notes: event.target.value })} placeholder="Optional context for this recurring plan" value={planForm.notes} />
        </Field>
        <div className="actions-inline">
          <button className="button" disabled={busyAction === "plan"} type="submit">
            {busyAction === "plan" ? "Saving plan…" : isEditing ? "Update plan" : "Save plan"}
          </button>
          {isEditing && onCancel ? (
            <button className="button secondary" onClick={onCancel} type="button">
              Cancel edit
            </button>
          ) : null}
        </div>
      </form>
    </div>
  );
}

function PlanTargetEditorForm({
  plans,
  selectedPlan,
  planTargetForm,
  setPlanTargetForm,
  busyAction,
  isEditing,
  onSubmit,
  onCancel,
  onAppendCompositionSector,
  onRemoveCompositionSector,
}: {
  plans: InvestmentPlan[];
  selectedPlan: InvestmentPlan | null;
  planTargetForm: PlanTargetFormState;
  setPlanTargetForm: Setter<PlanTargetFormState>;
  busyAction: string | null;
  isEditing: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel?: () => void;
  onAppendCompositionSector: () => void;
  onRemoveCompositionSector: (sector: string) => void;
}) {
  return (
    <div className="panel panel-subsection">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">Target allocation</p>
          <h3 className="panel-title">{isEditing ? "Edit plan ETF" : "Add plan ETF"}</h3>
        </div>
        <span className="pill">{isEditing ? "Editing" : "One ETF at a time"}</span>
      </div>
      <form className="form" onSubmit={onSubmit}>
        <div className="stats-grid plan-stats-grid">
          <div className="metric-card plan-selector-card">
            <span className="metric-label">Selected plan</span>
            <select onChange={(event) => setPlanTargetForm({ ...planTargetForm, plan_id: event.target.value })} value={planTargetForm.plan_id}>
              <option value="">Select plan</option>
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.name}
                </option>
              ))}
            </select>
          </div>
          {selectedPlan ? (
            <>
              <Metric label="Current allocation" value={formatPlanAllocationPercent(selectedPlan.target_allocation_total)} />
              <Metric label="Monthly amount" value={formatMoney(selectedPlan.monthly_amount, selectedPlan.currency)} />
              <Metric label="Broker" value={selectedPlan.broker} />
              <Metric label="ETFs" value={String(selectedPlan.targets.length)} />
            </>
          ) : null}
        </div>
        {selectedPlan ? (
          <>
            <div className="form-grid form-grid-2">
              <Field label="Ticker">
                <input onChange={(event) => setPlanTargetForm({ ...planTargetForm, ticker: normalizeTickerInput(event.target.value) })} placeholder="VWCE" required value={formatTicker(planTargetForm.ticker)} />
              </Field>
              <Field label="Currency">
                <select onChange={(event) => setPlanTargetForm({ ...planTargetForm, currency: event.target.value as Currency })} value={planTargetForm.currency}>
                  {CURRENCIES.map((currency) => (
                    <option key={currency} value={currency}>
                      {currency}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Target %">
                <input max="100" min="0" onChange={(event) => setPlanTargetForm({ ...planTargetForm, weight_pct: event.target.value })} required step="any" type="number" value={planTargetForm.weight_pct} />
              </Field>
              <Field label="Sector">
                <div className="actions-inline">
                  <select onChange={(event) => setPlanTargetForm({ ...planTargetForm, sector: event.target.value as Sector })} value={planTargetForm.sector}>
                    {SECTORS.map((sector) => (
                      <option key={sector} value={sector}>
                        {sector}
                      </option>
                    ))}
                  </select>
                  <button className="button secondary button-small" onClick={onAppendCompositionSector} type="button">
                    Add
                  </button>
                </div>
                {planTargetForm.composition_sectors.length > 0 ? (
                  <div className="actions-inline" style={{ marginTop: "0.5rem" }}>
                    {planTargetForm.composition_sectors.map((sector) => (
                      <span className="pill" key={sector}>
                        {sector}
                        <button
                          aria-label={`Remove ${sector}`}
                          className="tag-remove"
                          onClick={() => onRemoveCompositionSector(sector)}
                          type="button"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}
              </Field>
              <Field label="Notes">
                <textarea onChange={(event) => setPlanTargetForm({ ...planTargetForm, notes: event.target.value })} placeholder="Why this ETF belongs in the plan" value={planTargetForm.notes} />
              </Field>
            </div>
            <div className="actions-inline">
              <button className="button" disabled={busyAction === "plan-target"} type="submit">
                {busyAction === "plan-target" ? "Saving target…" : isEditing ? "Update target" : "Save target"}
              </button>
              {isEditing && onCancel ? (
                <button className="button secondary" onClick={onCancel} type="button">
                  Cancel edit
                </button>
              ) : null}
            </div>
          </>
        ) : (
          <div className="empty-state">Select a valid investment plan to see and edit its allocation.</div>
        )}
      </form>
    </div>
  );
}

function PlanTargetRow({
  target,
  planId,
  showNotes,
  busyAction,
  browserCaptureAvailability,
  browserCaptureStatuses,
  onQueuePlanChart,
  onStartEditPlanTarget,
  onDeletePlanTarget,
}: {
  target: InvestmentPlanTarget;
  planId: string;
  showNotes: boolean;
  busyAction: string | null;
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
  onQueuePlanChart: (target: InvestmentPlanTarget) => void;
  onStartEditPlanTarget: (planId: string, target: InvestmentPlanTarget) => void;
  onDeletePlanTarget: (targetId: string) => void;
}) {
  const chartState = resolveChartActionState(
    browserCaptureStatuses[target.ticker],
    busyAction === `queue-cnbc-${target.id}`
  );

  return (
    <tr>
      <td>
        <strong className="ticker-inline">
          {formatTicker(target.ticker)}
          <BrowserChartButton
            hasChart={browserCaptureAvailability[target.ticker] ?? false}
            ticker={target.ticker}
          />
        </strong>
      </td>
      <td>{target.currency}</td>
      <td>{target.weight_pct}%</td>
      <td>{target.sector ?? "—"}</td>
      <td>{target.composition_sectors.length > 0 ? target.composition_sectors.join(", ") : "—"}</td>
      {showNotes ? <td>{target.notes ?? "—"}</td> : null}
      <td>
        <div className="actions-inline">
          <button
            className="chart-action-button"
            disabled={chartState.isBlocked}
            onClick={() => onQueuePlanChart(target)}
            title={browserCaptureStatuses[target.ticker]?.error ?? undefined}
            type="button"
          >
            <ChartActionIcon kind={chartState.kind} title={chartState.title} />
          </button>
          <button
            aria-label={`Edit ${formatTicker(target.ticker)} target`}
            className="chart-action-button"
            onClick={() => onStartEditPlanTarget(planId, target)}
            type="button"
          >
            <MdEdit />
          </button>
          <button
            aria-label={`Delete ${formatTicker(target.ticker)} target`}
            className="chart-action-button"
            disabled={busyAction === `delete-plan-target-${target.id}`}
            onClick={() => onDeletePlanTarget(target.id)}
            type="button"
          >
            {busyAction === `delete-plan-target-${target.id}` ? "Deleting…" : <MdDeleteForever />}
          </button>
        </div>
      </td>
    </tr>
  );
}

function PlanCard({
  plan,
  showTargetNotes,
  busyAction,
  browserCaptureAvailability,
  browserCaptureStatuses,
  onStartEditPlan,
  onDeletePlan,
  onQueuePlanCharts,
  onQueuePlanChart,
  onStartEditPlanTarget,
  onDeletePlanTarget,
  onCreatePlanPause,
  onDeletePlanPause,
  onCreatePlanAmountChange,
  onDeletePlanAmountChange,
  onCreatePlanOneOffContribution,
  onDeletePlanOneOffContribution,
}: {
  plan: InvestmentPlan;
  showTargetNotes: boolean;
  busyAction: string | null;
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
  onStartEditPlan: (plan: InvestmentPlan) => void;
  onDeletePlan: (planId: string) => void;
  onQueuePlanCharts: (plan: InvestmentPlan) => void;
  onQueuePlanChart: (target: InvestmentPlanTarget) => void;
  onStartEditPlanTarget: (planId: string, target: InvestmentPlanTarget) => void;
  onDeletePlanTarget: (targetId: string) => void;
  onCreatePlanPause: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanPause: (pauseId: string) => void;
  onCreatePlanAmountChange: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanAmountChange: (changeId: string) => void;
  onCreatePlanOneOffContribution: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanOneOffContribution: (contributionId: string) => void;
}) {
  const [pauseForm, setPauseForm] = useState<PlanPauseFormState>({ ...emptyPauseForm, plan_id: plan.id });
  const [amountChangeForm, setAmountChangeForm] = useState<PlanAmountChangeFormState>({
    ...emptyAmountChangeForm,
    plan_id: plan.id,
  });
  const [oneOffForm, setOneOffForm] = useState<PlanOneOffContributionFormState>({
    ...emptyOneOffForm,
    plan_id: plan.id,
  });
  return (
    <div className="panel panel-subsection">
      <div className="panel-head">
        <div>
          <p className="panel-kicker">{plan.broker}</p>
          <h3 className="panel-title">{plan.name}</h3>
        </div>
        <span className="pill">
          {formatMoney(plan.monthly_amount, plan.currency)} on day {plan.contribution_day}
        </span>
      </div>
      <div className="stats-grid">
        <Metric label="Start" value={plan.start_date} />
        <Metric label="Next run" value={plan.next_run_on ?? "—"} />
        <Metric label="Scheduled months" value={String(plan.scheduled_contributions)} />
        <Metric label="Expected total" value={formatMoney(plan.expected_contributions_total, plan.currency)} />
        <Metric label="Target allocation" value={formatPlanAllocationPercent(plan.target_allocation_total)} />
      </div>
      {plan.notes ? <p className="panel-copy">{plan.notes}</p> : null}
      <div className="actions-inline" style={{ marginBottom: "1rem" }}>
        <button aria-label={`Edit ${plan.name}`} className="chart-action-button" onClick={() => onStartEditPlan(plan)} type="button">
          <MdEdit />
        </button>
        <button
          className="chart-action-button"
          disabled={busyAction === `queue-plan-${plan.id}` || plan.targets.length === 0}
          onClick={() => onQueuePlanCharts(plan)}
          type="button"
        >
          <ChartActionIcon
            kind={busyAction === `queue-plan-${plan.id}` ? "running" : "bulk"}
            title={busyAction === `queue-plan-${plan.id}` ? "Queueing all history ingests" : "Ingest all histories"}
          />
        </button>
        <button
          aria-label={`Delete ${plan.name}`}
          className="chart-action-button"
          disabled={busyAction === `delete-plan-${plan.id}`}
          onClick={() => onDeletePlan(plan.id)}
          type="button"
        >
          {busyAction === `delete-plan-${plan.id}` ? "Deleting…" : <MdDeleteForever />}
        </button>
      </div>
      {plan.targets.length === 0 ? (
        <div className="empty-state">No plan ETFs added yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Currency</th>
              <th>Target %</th>
              <th>Sector</th>
              <th>Composition</th>
              {showTargetNotes ? <th>Notes</th> : null}
              <th></th>
            </tr>
          </thead>
          <tbody>
            {plan.targets.map((target) => (
              <PlanTargetRow
                browserCaptureAvailability={browserCaptureAvailability}
                browserCaptureStatuses={browserCaptureStatuses}
                busyAction={busyAction}
                key={target.id}
                onDeletePlanTarget={onDeletePlanTarget}
                onQueuePlanChart={onQueuePlanChart}
                onStartEditPlanTarget={onStartEditPlanTarget}
                planId={plan.id}
                showNotes={showTargetNotes}
                target={target}
              />
            ))}
          </tbody>
        </table>
      )}

      <div style={{ marginTop: "1rem" }}>
        <AccordionSection
          badge={`${plan.amount_changes.length + plan.one_off_contributions.length + plan.pauses.length} items`}
          kicker="Plan controls"
          title="Adjustments"
        >
          <div className="form-grid form-grid-2">
            <div className="panel panel-subsection">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Payment pauses</p>
                  <h4 className="panel-title">Pause monthly buys</h4>
                </div>
              </div>
              <form
                className="form"
                onSubmit={(event) => {
                  event.preventDefault();
                  onCreatePlanPause(plan.id, {
                    start_date: pauseForm.start_date,
                    end_date: pauseForm.end_date,
                    reason: pauseForm.reason || null,
                  });
                  setPauseForm({ ...emptyPauseForm, plan_id: plan.id });
                }}
              >
                <Field label="Start">
                  <input required type="date" value={pauseForm.start_date} onChange={(event) => setPauseForm((current) => ({ ...current, start_date: event.target.value }))} />
                </Field>
                <Field label="End">
                  <input required type="date" value={pauseForm.end_date} onChange={(event) => setPauseForm((current) => ({ ...current, end_date: event.target.value }))} />
                </Field>
                <Field label="Reason">
                  <input value={pauseForm.reason} onChange={(event) => setPauseForm((current) => ({ ...current, reason: event.target.value }))} />
                </Field>
                <button className="button" disabled={busyAction === `plan-pause-${plan.id}`} type="submit">
                  {busyAction === `plan-pause-${plan.id}` ? "Saving…" : "Add pause"}
                </button>
              </form>
              <AdjustmentList
                items={plan.pauses}
                renderLabel={(pause) => `${pause.start_date} -> ${pause.end_date}${pause.reason ? ` · ${pause.reason}` : ""}`}
                onDelete={(pause) => onDeletePlanPause(pause.id)}
                busyAction={busyAction}
                deletePrefix="delete-plan-pause"
              />
            </div>

            <div className="panel panel-subsection">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Amount changes</p>
                  <h4 className="panel-title">Change monthly amount</h4>
                </div>
              </div>
              <form
                className="form"
                onSubmit={(event) => {
                  event.preventDefault();
                  onCreatePlanAmountChange(plan.id, {
                    effective_date: amountChangeForm.effective_date,
                    monthly_amount: Number(amountChangeForm.monthly_amount),
                    note: amountChangeForm.note || null,
                  });
                  setAmountChangeForm({ ...emptyAmountChangeForm, plan_id: plan.id });
                }}
              >
                <Field label="Effective date">
                  <input required type="date" value={amountChangeForm.effective_date} onChange={(event) => setAmountChangeForm((current) => ({ ...current, effective_date: event.target.value }))} />
                </Field>
                <Field label="New monthly amount">
                  <input required min="0" step="any" type="number" value={amountChangeForm.monthly_amount} onChange={(event) => setAmountChangeForm((current) => ({ ...current, monthly_amount: event.target.value }))} />
                </Field>
                <Field label="Note">
                  <input value={amountChangeForm.note} onChange={(event) => setAmountChangeForm((current) => ({ ...current, note: event.target.value }))} />
                </Field>
                <button className="button" disabled={busyAction === `plan-amount-change-${plan.id}`} type="submit">
                  {busyAction === `plan-amount-change-${plan.id}` ? "Saving…" : "Add amount change"}
                </button>
              </form>
              <AdjustmentList
                items={plan.amount_changes}
                renderLabel={(change) => `${change.effective_date} -> ${formatMoney(change.monthly_amount, plan.currency)}${change.note ? ` · ${change.note}` : ""}`}
                onDelete={(change) => onDeletePlanAmountChange(change.id)}
                busyAction={busyAction}
                deletePrefix="delete-plan-amount-change"
              />
            </div>

            <div className="panel panel-subsection">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Standalone top-ups</p>
                  <h4 className="panel-title">Add one-off contribution</h4>
                </div>
              </div>
              <form
                className="form"
                onSubmit={(event) => {
                  event.preventDefault();
                  onCreatePlanOneOffContribution(plan.id, {
                    contribution_date: oneOffForm.contribution_date,
                    amount: Number(oneOffForm.amount),
                    note: oneOffForm.note || null,
                  });
                  setOneOffForm({ ...emptyOneOffForm, plan_id: plan.id });
                }}
              >
                <Field label="Date">
                  <input required type="date" value={oneOffForm.contribution_date} onChange={(event) => setOneOffForm((current) => ({ ...current, contribution_date: event.target.value }))} />
                </Field>
                <Field label="Amount">
                  <input required min="0" step="any" type="number" value={oneOffForm.amount} onChange={(event) => setOneOffForm((current) => ({ ...current, amount: event.target.value }))} />
                </Field>
                <Field label="Note">
                  <input value={oneOffForm.note} onChange={(event) => setOneOffForm((current) => ({ ...current, note: event.target.value }))} />
                </Field>
                <button className="button" disabled={busyAction === `plan-one-off-${plan.id}`} type="submit">
                  {busyAction === `plan-one-off-${plan.id}` ? "Saving…" : "Add top-up"}
                </button>
              </form>
              <AdjustmentList
                items={plan.one_off_contributions}
                renderLabel={(contribution) => `${contribution.contribution_date} -> ${formatMoney(contribution.amount, plan.currency)}${contribution.note ? ` · ${contribution.note}` : ""}`}
                onDelete={(contribution) => onDeletePlanOneOffContribution(contribution.id)}
                busyAction={busyAction}
                deletePrefix="delete-plan-one-off"
              />
            </div>
          </div>
        </AccordionSection>
      </div>
    </div>
  );
}

function AdjustmentList<T extends { id: string }>({
  items,
  renderLabel,
  onDelete,
  busyAction,
  deletePrefix,
}: {
  items: T[];
  renderLabel: (item: T) => string;
  onDelete: (item: T) => void;
  busyAction: string | null;
  deletePrefix: string;
}) {
  if (items.length === 0) {
    return <></>;
  }

  return (
    <div className="saved-query-list" style={{ marginTop: "0.75rem" }}>
      {items.map((item) => (
        <div className="saved-query-row" key={item.id}>
          <div className="list-meta">{renderLabel(item)}</div>
          <button
            className="chart-action-button"
            disabled={busyAction === `${deletePrefix}-${item.id}`}
            onClick={() => onDelete(item)}
            type="button"
          >
            {busyAction === `${deletePrefix}-${item.id}` ? "Deleting…" : <MdDeleteForever />}
          </button>
        </div>
      ))}
    </div>
  );
}

export function RecurringInvestingSection(props: {
  plans: InvestmentPlan[];
  selectedPlan: InvestmentPlan | null;
  planForm: PlanFormState;
  setPlanForm: Setter<PlanFormState>;
  planTargetForm: PlanTargetFormState;
  setPlanTargetForm: Setter<PlanTargetFormState>;
  editingPlanId: string | null;
  editingPlanTargetId: string | null;
  busyAction: string | null;
  browserCaptureAvailability: Record<string, boolean>;
  browserCaptureStatuses: Record<string, BrowserCaptureTask | null>;
  onPlanSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancelEditPlan: () => void;
  onPlanTargetSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancelEditPlanTarget: () => void;
  onAppendCompositionSector: () => void;
  onRemoveCompositionSector: (sector: string) => void;
  onStartEditPlan: (plan: InvestmentPlan) => void;
  onDeletePlan: (planId: string) => void;
  onQueuePlanCharts: (plan: InvestmentPlan) => void;
  onQueuePlanChart: (target: InvestmentPlanTarget) => void;
  onStartEditPlanTarget: (planId: string, target: InvestmentPlanTarget) => void;
  onDeletePlanTarget: (targetId: string) => void;
  onCreatePlanPause: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanPause: (pauseId: string) => void;
  onCreatePlanAmountChange: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanAmountChange: (changeId: string) => void;
  onCreatePlanOneOffContribution: (planId: string, payload: Record<string, unknown>) => void;
  onDeletePlanOneOffContribution: (contributionId: string) => void;
}) {
  const {
    plans,
    selectedPlan,
    planForm,
    setPlanForm,
    planTargetForm,
    setPlanTargetForm,
    editingPlanId,
    editingPlanTargetId,
    busyAction,
    browserCaptureAvailability,
    browserCaptureStatuses,
    onPlanSubmit,
    onCancelEditPlan,
    onPlanTargetSubmit,
    onCancelEditPlanTarget,
    onAppendCompositionSector,
    onRemoveCompositionSector,
    onStartEditPlan,
    onDeletePlan,
    onQueuePlanCharts,
    onQueuePlanChart,
    onStartEditPlanTarget,
    onDeletePlanTarget,
    onCreatePlanPause,
    onDeletePlanPause,
    onCreatePlanAmountChange,
    onDeletePlanAmountChange,
    onCreatePlanOneOffContribution,
    onDeletePlanOneOffContribution,
  } = props;
  const showTargetNotes = plans.some((plan) => plan.targets.some((target) => Boolean(target.notes?.trim())));
  const isEditingPlan = Boolean(editingPlanId);
  const isEditingPlanTarget = Boolean(editingPlanTargetId);

  return (
    <div className="stack">
      {isEditingPlan || isEditingPlanTarget ? (
        <section className="stack sticky-editor-stack">
          {isEditingPlan ? (
            <PlanEditorForm
              busyAction={busyAction}
              isEditing
              onCancel={onCancelEditPlan}
              onSubmit={onPlanSubmit}
              planForm={planForm}
              setPlanForm={setPlanForm}
            />
          ) : null}
          {isEditingPlanTarget ? (
            <PlanTargetEditorForm
              busyAction={busyAction}
              isEditing
              onAppendCompositionSector={onAppendCompositionSector}
              onCancel={onCancelEditPlanTarget}
              onRemoveCompositionSector={onRemoveCompositionSector}
              onSubmit={onPlanTargetSubmit}
              planTargetForm={planTargetForm}
              plans={plans}
              selectedPlan={selectedPlan}
              setPlanTargetForm={setPlanTargetForm}
            />
          ) : null}
        </section>
      ) : null}

      <section className="stack">
        {!isEditingPlan ? (
          <AccordionSection kicker="Recurring investing" title="Add investment plan">
            <PlanEditorForm
              busyAction={busyAction}
              isEditing={false}
              onSubmit={onPlanSubmit}
              planForm={planForm}
              setPlanForm={setPlanForm}
            />
          </AccordionSection>
        ) : null}
        {!isEditingPlanTarget ? (
          <AccordionSection kicker="Target allocation" title="Add plan ETF">
            <PlanTargetEditorForm
              busyAction={busyAction}
              isEditing={false}
              onAppendCompositionSector={onAppendCompositionSector}
              onRemoveCompositionSector={onRemoveCompositionSector}
              onSubmit={onPlanTargetSubmit}
              planTargetForm={planTargetForm}
              plans={plans}
              selectedPlan={selectedPlan}
              setPlanTargetForm={setPlanTargetForm}
            />
          </AccordionSection>
        ) : null}
      </section>

      <AccordionSection badge={`${plans.length} plans`} defaultOpen kicker="Auto-invest tracker" title="Investment plans">
        <div className="stack">
          {plans.length === 0 ? (
            <div className="empty-state">No recurring investment plans saved yet.</div>
          ) : (
            plans.map((plan) => (
              <PlanCard
                browserCaptureAvailability={browserCaptureAvailability}
                browserCaptureStatuses={browserCaptureStatuses}
                busyAction={busyAction}
                key={plan.id}
              onDeletePlan={onDeletePlan}
              onCreatePlanAmountChange={onCreatePlanAmountChange}
              onCreatePlanOneOffContribution={onCreatePlanOneOffContribution}
              onCreatePlanPause={onCreatePlanPause}
              onDeletePlanAmountChange={onDeletePlanAmountChange}
              onDeletePlanOneOffContribution={onDeletePlanOneOffContribution}
              onDeletePlanPause={onDeletePlanPause}
              onDeletePlanTarget={onDeletePlanTarget}
                onQueuePlanChart={onQueuePlanChart}
                onQueuePlanCharts={onQueuePlanCharts}
                onStartEditPlan={onStartEditPlan}
                onStartEditPlanTarget={onStartEditPlanTarget}
                plan={plan}
                showTargetNotes={showTargetNotes}
              />
            ))
          )}
        </div>
      </AccordionSection>
    </div>
  );
}
