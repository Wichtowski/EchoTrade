import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  BROWSER_CAPTURE_PROVIDERS,
  type BrowserCaptureProvider,
  type BrowserCaptureTask,
  type ManualTrade,
  getRefreshHeldQuotesStatus,
  createInvestmentPlan,
  createInvestmentPlanAmountChange,
  createInvestmentPlanOneOffContribution,
  createInvestmentPlanPause,
  createInvestmentPlanTarget,
  createSnapshot,
  createTrade,
  deleteInvestmentPlan,
  deleteInvestmentPlanAmountChange,
  deleteInvestmentPlanOneOffContribution,
  deleteInvestmentPlanPause,
  deleteInvestmentPlanTarget,
  deleteSnapshot,
  deleteTrade,
  getBrowserChartCaptureAvailability,
  getBrowserChartCaptureStatuses,
  getInvestmentPlans,
  getLatestBrowserChartCapture,
  getPositions,
  getSnapshots,
  getTrades,
  queueRefreshHeldQuotes,
  queueBrowserChartCapture,
  syncPositionsFromTrades,
  updateInvestmentPlan,
  updateInvestmentPlanTarget,
  updateTrade,
} from "../../src/lib/api";
import { queryKeys } from "../../src/lib/query";
import {
  PortfolioToolbar,
  PositionsSection,
  PositionsWorkspaceTabs,
  type PositionsWorkspaceTab,
  QuoteRefreshSection,
  RecurringInvestingSection,
  SnapshotsSection,
  TradeEntrySection,
  TradesSection,
} from "../../src/components/positions/WorkspaceSections";
import type {
  PlanFormState,
  PlanTargetFormState,
  TradeFormState,
} from "../../src/components/positions/types";
import { ToastViewport, type ToastItem, type ToastTone } from "../../src/components/ui";
import { formatTicker } from "../../src/lib/format";

const initialTradeForm: TradeFormState = {
  account_type: "personal",
  ticker: "",
  action: "BUY",
  quantity: "",
  price: "",
  broker: "XTB",
  currency: "PLN",
  fees: "0",
  sector: "semis",
  thesis: "",
  notes: "",
  executed_at: "",
  review_date: "",
};

function createInitialPlanForm(): PlanFormState {
  const currentYear = new Date().getFullYear();
  return {
    account_type: "personal",
    name: "XTB Auto-Invest",
    broker: "XTB",
    currency: "PLN",
    monthly_amount: "100",
    contribution_day: "10",
    start_date: `${currentYear}-01-10`,
    notes: "",
  };
}

const initialPlanTargetForm: PlanTargetFormState = {
  plan_id: "",
  ticker: "",
  currency: "PLN",
  weight_pct: "",
  sector: "other",
  composition_sectors: [],
  notes: "",
};

const DEFAULT_BROWSER_CAPTURE_PROVIDER: BrowserCaptureProvider = BROWSER_CAPTURE_PROVIDERS[0];

export default function Page() {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<PositionsWorkspaceTab>("positions");
  const [planForm, setPlanForm] = useState<PlanFormState>(createInitialPlanForm);
  const [planTargetForm, setPlanTargetForm] = useState<PlanTargetFormState>(initialPlanTargetForm);
  const [tradeForm, setTradeForm] = useState<TradeFormState>(initialTradeForm);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [editingPlanTargetId, setEditingPlanTargetId] = useState<string | null>(null);
  const [editingTradeId, setEditingTradeId] = useState<string | null>(null);
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastCounter = useRef(0);
  const lastAutoSyncSignatureRef = useRef<string | null>(null);
  const lastHandledQuoteRefreshRef = useRef<string | null>(null);
  const lastHandledBrowserCaptureFailuresRef = useRef<Record<string, string>>({});
  const mountedAtRef = useRef(Date.now());

  function pushToast(message: string, tone: ToastTone = "info") {
    const id = ++toastCounter.current;
    setToasts((current) => [...current, { id, message, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 6000);
  }

  function dismissToast(id: number) {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }

  const plansQuery = useQuery({
    queryKey: queryKeys.plans,
    queryFn: getInvestmentPlans,
  });
  const positionsQuery = useQuery({
    queryKey: queryKeys.positions,
    queryFn: getPositions,
  });
  const tradesQuery = useQuery({
    queryKey: queryKeys.trades,
    queryFn: getTrades,
  });
  const snapshotsQuery = useQuery({
    queryKey: queryKeys.snapshots,
    queryFn: getSnapshots,
  });

  const positions = positionsQuery.data ?? [];
  const trades = tradesQuery.data ?? [];
  const snapshots = snapshotsQuery.data ?? [];
  const plans = plansQuery.data ?? [];
  const selectedPlan = plans.find((plan) => plan.id === planTargetForm.plan_id) ?? null;
  const tickers = useMemo(
    () =>
      Array.from(
        new Set([
          ...positions.map((position) => position.ticker),
          ...plans.flatMap((plan) => plan.targets.map((target) => target.ticker)),
        ])
      ),
    [plans, positions]
  );

  const browserStatusesQuery = useQuery({
    queryKey: queryKeys.browserCaptureStatuses(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers),
    queryFn: async () => {
      if (tickers.length === 0) {
        return { statuses: {}, time_ranges: [], provider: DEFAULT_BROWSER_CAPTURE_PROVIDER };
      }
      return getBrowserChartCaptureStatuses(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers);
    },
    enabled: tickers.length >= 0,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data || !("statuses" in data)) return false;
      const hasPending = Object.values(data.statuses).some(
        (status) => status?.status === "queued" || status?.status === "running"
      );
      return hasPending ? 5000 : false;
    },
  });

  const browserAvailabilityQuery = useQuery({
    queryKey: queryKeys.browserCaptureAvailability(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers),
    queryFn: async () => {
      if (tickers.length === 0) {
        return { available: {}, provider: DEFAULT_BROWSER_CAPTURE_PROVIDER };
      }
      return getBrowserChartCaptureAvailability(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers);
    },
  });

  const latestCaptureQuery = useQuery({
    queryKey: queryKeys.browserCaptureLatest(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers),
    queryFn: async () => {
      const available = browserAvailabilityQuery.data?.available ?? {};
      const symbols = tickers.filter((ticker) => available[ticker]);
      const documents = await Promise.all(
        symbols.map(async (ticker) => {
          try {
            return [ticker, await getLatestBrowserChartCapture(DEFAULT_BROWSER_CAPTURE_PROVIDER, ticker)] as const;
          } catch {
            return [ticker, null] as const;
          }
        })
      );
      return Object.fromEntries(documents);
    },
    enabled: tickers.length > 0 && browserAvailabilityQuery.isSuccess,
  });

  const quoteRefreshStatusQuery = useQuery({
    queryKey: queryKeys.quoteRefreshStatus,
    queryFn: getRefreshHeldQuotesStatus,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "queued" || status === "running" ? 5000 : false;
    },
  });

  const invalidateWorkspace = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.plans }),
      queryClient.invalidateQueries({ queryKey: queryKeys.positions }),
      queryClient.invalidateQueries({ queryKey: queryKeys.trades }),
      queryClient.invalidateQueries({ queryKey: queryKeys.snapshots }),
    ]);
  };

  const planMutation = useMutation({
    mutationFn: async (event: { payload: Record<string, unknown>; editingId: string | null }) => {
      if (event.editingId) {
        return updateInvestmentPlan(event.editingId, event.payload);
      }
      return createInvestmentPlan(event.payload);
    },
    onSuccess: async (_, variables) => {
      setPlanForm(createInitialPlanForm());
      setEditingPlanId(null);
      await invalidateWorkspace();
      pushToast(variables.editingId ? "Investment plan updated." : "Investment plan saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save investment plan", "error");
    },
  });

  const planTargetMutation = useMutation({
    mutationFn: async (event: { payload: Record<string, unknown>; editingId: string | null; planId: string }) => {
      if (event.editingId) {
        return updateInvestmentPlanTarget(event.editingId, event.payload);
      }
      return createInvestmentPlanTarget(event.planId, event.payload);
    },
    onSuccess: async (_, variables) => {
      setPlanTargetForm((current) => ({ ...initialPlanTargetForm, plan_id: current.plan_id }));
      setEditingPlanTargetId(null);
      await invalidateWorkspace();
      pushToast(variables.editingId ? "Plan target updated." : "Plan target saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save investment plan target", "error");
    },
  });

  const tradeMutation = useMutation({
    mutationFn: async (event: { payload: Record<string, unknown>; editingId: string | null }) => {
      if (event.editingId) {
        return updateTrade(event.editingId, event.payload);
      }
      return createTrade(event.payload);
    },
    onSuccess: async (_, variables) => {
      setTradeForm(initialTradeForm);
      setEditingTradeId(null);
      await invalidateWorkspace();
      pushToast(variables.editingId ? "Trade updated." : "Trade saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save trade", "error");
    },
  });

  const queueRefreshQuotesMutation = useMutation({
    mutationFn: queueRefreshHeldQuotes,
    onSuccess: async (task) => {
      queryClient.setQueryData(queryKeys.quoteRefreshStatus, task);
      pushToast(`Queued held quote refresh for ${task.requested_symbols.length} symbols.`, "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to queue held quote refresh", "error");
    },
  });

  const snapshotMutation = useMutation({
    mutationFn: createSnapshot,
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Snapshot created from current positions and latest quotes.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to create snapshot", "error");
    },
  });

  const syncPositionsMutation = useMutation({
    mutationFn: syncPositionsFromTrades,
    onSuccess: async (synced) => {
      lastAutoSyncSignatureRef.current = buildTradeSignature(trades);
      await invalidateWorkspace();
      pushToast(`Synced ${synced.length} positions from the trade journal.`, "success");
    },
    onError: (error) => {
      lastAutoSyncSignatureRef.current = null;
      pushToast(error instanceof Error ? error.message : "Failed to sync positions from trades", "error");
    },
  });

  const deletePlanMutation = useMutation({
    mutationFn: deleteInvestmentPlan,
    onSuccess: async (_, planId) => {
      if (editingPlanId === planId) {
        setEditingPlanId(null);
        setPlanForm(createInitialPlanForm());
      }
      if (planTargetForm.plan_id === planId) {
        setPlanTargetForm({ ...initialPlanTargetForm, plan_id: "" });
      }
      await invalidateWorkspace();
      pushToast("Investment plan deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete investment plan", "error");
    },
  });

  const deletePlanTargetMutation = useMutation({
    mutationFn: deleteInvestmentPlanTarget,
    onSuccess: async (_, targetId) => {
      if (editingPlanTargetId === targetId) {
        setEditingPlanTargetId(null);
        setPlanTargetForm((current) => ({ ...initialPlanTargetForm, plan_id: current.plan_id }));
      }
      await invalidateWorkspace();
      pushToast("Investment plan target deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete investment plan target", "error");
    },
  });

  const deleteTradeMutation = useMutation({
    mutationFn: deleteTrade,
    onSuccess: async (_, tradeId) => {
      if (editingTradeId === tradeId) {
        setEditingTradeId(null);
        setTradeForm(initialTradeForm);
      }
      await invalidateWorkspace();
      pushToast("Trade deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete trade", "error");
    },
  });

  const deleteSnapshotMutation = useMutation({
    mutationFn: deleteSnapshot,
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Snapshot deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete snapshot", "error");
    },
  });

  const queueCaptureMutation = useMutation({
    mutationFn: async (position: { id: string; ticker: string }) =>
      queueBrowserChartCapture(DEFAULT_BROWSER_CAPTURE_PROVIDER, position.ticker),
    onSuccess: async (task, position) => {
      queryClient.setQueryData(queryKeys.browserCaptureStatuses(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers), (current: { statuses: Record<string, BrowserCaptureTask | null>; time_ranges: string[]; provider: string } | undefined) => ({
        statuses: { ...(current?.statuses ?? {}), [position.ticker]: task },
        time_ranges: current?.time_ranges ?? [],
        provider: current?.provider ?? DEFAULT_BROWSER_CAPTURE_PROVIDER,
      }));
      pushToast(`Queued CNBC chart capture for ${formatTicker(task.symbol)}.`, "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to queue browser capture", "error");
    },
  });

  const planPauseMutation = useMutation({
    mutationFn: async (event: { planId: string; payload: Record<string, unknown> }) =>
      createInvestmentPlanPause(event.planId, event.payload),
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan pause saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save plan pause", "error");
    },
  });

  const deletePlanPauseMutation = useMutation({
    mutationFn: deleteInvestmentPlanPause,
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan pause deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete plan pause", "error");
    },
  });

  const planAmountChangeMutation = useMutation({
    mutationFn: async (event: { planId: string; payload: Record<string, unknown> }) =>
      createInvestmentPlanAmountChange(event.planId, event.payload),
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan amount change saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save plan amount change", "error");
    },
  });

  const deletePlanAmountChangeMutation = useMutation({
    mutationFn: deleteInvestmentPlanAmountChange,
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan amount change deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete plan amount change", "error");
    },
  });

  const planOneOffContributionMutation = useMutation({
    mutationFn: async (event: { planId: string; payload: Record<string, unknown> }) =>
      createInvestmentPlanOneOffContribution(event.planId, event.payload),
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan one-off contribution saved.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to save plan one-off contribution", "error");
    },
  });

  const deletePlanOneOffContributionMutation = useMutation({
    mutationFn: deleteInvestmentPlanOneOffContribution,
    onSuccess: async () => {
      await invalidateWorkspace();
      pushToast("Plan one-off contribution deleted.", "success");
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to delete plan one-off contribution", "error");
    },
  });

  const queuePlanChartsMutation = useMutation({
    mutationFn: async (plan: { id: string; name: string; tickers: string[] }) => {
      const uniqueTickers = Array.from(new Set(plan.tickers));
      const results = await Promise.allSettled(
        uniqueTickers.map((ticker) => queueBrowserChartCapture(DEFAULT_BROWSER_CAPTURE_PROVIDER, ticker))
      );
      const queued = results.filter((result) => result.status === "fulfilled").length;
      const failed = results
        .map((result, index) =>
          result.status === "rejected" ? formatTicker(uniqueTickers[index] ?? "") : null
        )
        .filter((value): value is string => Boolean(value));
      return {
        plan,
        queued,
        failed,
      };
    },
    onSuccess: async ({ plan, queued, failed }) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.browserCaptureStatuses(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.browserCaptureAvailability(DEFAULT_BROWSER_CAPTURE_PROVIDER, tickers),
        }),
      ]);
      pushToast(
        failed.length > 0
          ? `Queued ${queued} chart captures for ${plan.name}. Failed: ${failed.join(", ")}`
          : `Queued ${queued} chart captures for ${plan.name}.`,
        failed.length > 0 ? "error" : "success"
      );
    },
    onError: (error) => {
      pushToast(error instanceof Error ? error.message : "Failed to queue plan chart captures", "error");
    },
  });

  useEffect(() => {
    if (plans.length > 0 && !planTargetForm.plan_id) {
      setPlanTargetForm((current) => ({ ...current, plan_id: plans[0]?.id ?? "" }));
    }
  }, [plans, planTargetForm.plan_id]);

  const journalDrift = useMemo(() => detectJournalPositionDrift(trades, positions), [trades, positions]);
  const syncSignature = useMemo(
    () => `${journalDrift.tradeSignature}|${journalDrift.positionSignature}`,
    [journalDrift.positionSignature, journalDrift.tradeSignature]
  );

  useEffect(() => {
    if (tradesQuery.isLoading || positionsQuery.isLoading || syncPositionsMutation.isPending) {
      return;
    }
    if (trades.length === 0) {
      lastAutoSyncSignatureRef.current = "";
      return;
    }
    if (!journalDrift.hasMismatch) {
      lastAutoSyncSignatureRef.current = syncSignature;
      return;
    }
    if (lastAutoSyncSignatureRef.current === syncSignature) {
      return;
    }
    lastAutoSyncSignatureRef.current = syncSignature;
    syncPositionsMutation.mutate();
  }, [
    journalDrift.hasMismatch,
    positionsQuery.isLoading,
    syncPositionsMutation,
    syncSignature,
    trades.length,
    tradesQuery.isLoading,
  ]);

  useEffect(() => {
    const refreshTask = quoteRefreshStatusQuery.data;
    if (!refreshTask) {
      return;
    }
    const eventKey = `${refreshTask.task_id}:${refreshTask.status}:${refreshTask.stored_count}:${refreshTask.failed_symbols.join(",")}`;
    if (lastHandledQuoteRefreshRef.current === eventKey) {
      return;
    }
    if (refreshTask.status === "completed") {
      lastHandledQuoteRefreshRef.current = eventKey;
      pushToast(
        refreshTask.failed_symbols.length > 0
          ? `Stored ${refreshTask.stored_count} Yahoo quotes. Failed: ${refreshTask.failed_symbols.join(", ")}`
          : `Stored ${refreshTask.stored_count} Yahoo quotes for held positions.`,
        refreshTask.failed_symbols.length > 0 ? "error" : "success"
      );
      return;
    }
    if (refreshTask.status === "failed") {
      lastHandledQuoteRefreshRef.current = eventKey;
      pushToast(refreshTask.error ?? "Held quote refresh failed", "error");
    }
  }, [pushToast, queryClient, quoteRefreshStatusQuery.data]);

  useEffect(() => {
    const statuses = browserStatusesQuery.data?.statuses ?? {};
    for (const [symbol, status] of Object.entries(statuses)) {
      if (!status || status.status !== "failed") {
        continue;
      }
      const failureKey = [
        status.task_id,
        status.error ?? "",
        status.error_stage ?? "",
        status.error_code ?? "",
        status.error_details?.time_range ?? "",
      ].join(":");
      if (lastHandledBrowserCaptureFailuresRef.current[symbol] === failureKey) {
        continue;
      }
      const updatedAtMs = status.updated_at ? Date.parse(status.updated_at) : Number.NaN;
      if (Number.isFinite(updatedAtMs) && updatedAtMs <= mountedAtRef.current) {
        lastHandledBrowserCaptureFailuresRef.current[symbol] = failureKey;
        continue;
      }
      lastHandledBrowserCaptureFailuresRef.current[symbol] = failureKey;
      const detailParts = [
        status.error_stage ? `stage ${status.error_stage}` : null,
        status.error_code ? `code ${status.error_code}` : null,
        status.error_details?.time_range ? `range ${status.error_details.time_range}` : null,
        status.retryable === true ? "retryable" : null,
      ]
        .filter(Boolean)
        .join(" · ");
      pushToast(
        [`Chart fetch failed for ${formatTicker(symbol)}.`, status.error, detailParts].filter(Boolean).join(" "),
        "error"
      );
    }
  }, [browserStatusesQuery.data?.statuses]);

  const isLoading =
    plansQuery.isLoading ||
    positionsQuery.isLoading ||
    tradesQuery.isLoading ||
    snapshotsQuery.isLoading;

  return (
    <div className="stack">
      <header className="page-header">
        <span className="eyebrow">Positions & journal</span>
        <h1 className="page-title">Store the portfolio state that the later phases will evaluate</h1>
      </header>

      <PortfolioToolbar
        busyAction={resolveBusyAction({
          snapshot: snapshotMutation.isPending,
        })}
        onCreateSnapshot={() => snapshotMutation.mutate(undefined)}
      />
      <PositionsWorkspaceTabs activeTab={activeTab} onChange={setActiveTab} />

      {isLoading ? <div className="status">Loading portfolio workspace…</div> : null}

      {activeTab === "plans" ? (
        <RecurringInvestingSection
          busyAction={resolveBusyAction({
            plan: planMutation.isPending,
            "plan-target": planTargetMutation.isPending,
            [`delete-plan-${deletePlanMutation.variables ?? ""}`]: deletePlanMutation.isPending,
            [`delete-plan-target-${deletePlanTargetMutation.variables ?? ""}`]: deletePlanTargetMutation.isPending,
            [`queue-plan-${(queuePlanChartsMutation.variables as { id?: string } | undefined)?.id ?? ""}`]:
              queuePlanChartsMutation.isPending,
            [`queue-cnbc-${(queueCaptureMutation.variables as { id?: string } | undefined)?.id ?? ""}`]:
              queueCaptureMutation.isPending,
            [`plan-pause-${(planPauseMutation.variables as { planId?: string } | undefined)?.planId ?? ""}`]:
              planPauseMutation.isPending,
            [`delete-plan-pause-${deletePlanPauseMutation.variables ?? ""}`]: deletePlanPauseMutation.isPending,
            [`plan-amount-change-${(planAmountChangeMutation.variables as { planId?: string } | undefined)?.planId ?? ""}`]:
              planAmountChangeMutation.isPending,
            [`delete-plan-amount-change-${deletePlanAmountChangeMutation.variables ?? ""}`]:
              deletePlanAmountChangeMutation.isPending,
            [`plan-one-off-${(planOneOffContributionMutation.variables as { planId?: string } | undefined)?.planId ?? ""}`]:
              planOneOffContributionMutation.isPending,
            [`delete-plan-one-off-${deletePlanOneOffContributionMutation.variables ?? ""}`]:
              deletePlanOneOffContributionMutation.isPending,
          })}
          browserCaptureAvailability={browserAvailabilityQuery.data?.available ?? {}}
          browserCaptureStatuses={browserStatusesQuery.data?.statuses ?? {}}
          editingPlanId={editingPlanId}
          editingPlanTargetId={editingPlanTargetId}
          onCancelEditPlan={() => {
            setEditingPlanId(null);
            setPlanForm(createInitialPlanForm());
            pushToast("Investment plan edit cancelled.");
          }}
          onCancelEditPlanTarget={() => {
            setEditingPlanTargetId(null);
            setPlanTargetForm((current) => ({ ...initialPlanTargetForm, plan_id: current.plan_id }));
            pushToast("Investment plan target edit cancelled.");
          }}
          onDeletePlan={(planId) => deletePlanMutation.mutate(planId)}
          onDeletePlanTarget={(targetId) => deletePlanTargetMutation.mutate(targetId)}
          onCreatePlanPause={(planId, payload) => planPauseMutation.mutate({ planId, payload })}
          onDeletePlanPause={(pauseId) => deletePlanPauseMutation.mutate(pauseId)}
          onCreatePlanAmountChange={(planId, payload) => planAmountChangeMutation.mutate({ planId, payload })}
          onDeletePlanAmountChange={(changeId) => deletePlanAmountChangeMutation.mutate(changeId)}
          onCreatePlanOneOffContribution={(planId, payload) =>
            planOneOffContributionMutation.mutate({ planId, payload })
          }
          onDeletePlanOneOffContribution={(contributionId) =>
            deletePlanOneOffContributionMutation.mutate(contributionId)
          }
          onQueuePlanCharts={(plan) =>
            queuePlanChartsMutation.mutate({
              id: plan.id,
              name: plan.name,
              tickers: plan.targets.map((target) => target.ticker),
            })
          }
          onQueuePlanChart={(target) =>
            queueCaptureMutation.mutate({ id: target.id, ticker: target.ticker })
          }
          onPlanSubmit={(event) => {
            event.preventDefault();
            planMutation.mutate({
              editingId: editingPlanId,
              payload: {
                account_type: planForm.account_type,
                name: planForm.name,
                broker: planForm.broker,
                currency: planForm.currency,
                monthly_amount: Number(planForm.monthly_amount),
                contribution_day: Number(planForm.contribution_day),
                start_date: planForm.start_date,
                notes: planForm.notes || null,
              },
            });
          }}
          onPlanTargetSubmit={(event) => {
            event.preventDefault();
            if (!planTargetForm.plan_id) {
              pushToast("Create an investment plan first, then add an ETF target.", "error");
              return;
            }
            planTargetMutation.mutate({
              editingId: editingPlanTargetId,
              planId: planTargetForm.plan_id,
              payload: {
                ticker: planTargetForm.ticker.toUpperCase(),
                currency: planTargetForm.currency,
                weight_pct: Number(planTargetForm.weight_pct),
                sector: planTargetForm.sector,
                composition_sectors: planTargetForm.composition_sectors,
                notes: planTargetForm.notes || null,
              },
            });
          }}
          onStartEditPlan={(plan) => {
            setEditingPlanTargetId(null);
            setEditingPlanId(plan.id);
            setPlanForm({
              account_type: plan.account_type,
              name: plan.name,
              broker: plan.broker,
              currency: plan.currency,
              monthly_amount: String(plan.monthly_amount),
              contribution_day: String(plan.contribution_day),
              start_date: plan.start_date,
              notes: plan.notes ?? "",
            });
            pushToast(`Editing investment plan ${plan.name}`);
          }}
          onStartEditPlanTarget={(planId, target) => {
            setEditingPlanId(null);
            setEditingPlanTargetId(target.id);
            setPlanTargetForm({
              plan_id: planId,
              ticker: target.ticker,
              currency: target.currency,
              weight_pct: String(target.weight_pct),
              sector: target.sector ?? "other",
              composition_sectors: target.composition_sectors ?? [],
              notes: target.notes ?? "",
            });
            pushToast(`Editing ${formatTicker(target.ticker)} target`);
          }}
          onAppendCompositionSector={() => {
            const nextSector = planTargetForm.sector;
            setPlanTargetForm((current) => {
              if (current.composition_sectors.includes(nextSector)) {
                return current;
              }
              return {
                ...current,
                composition_sectors: [...current.composition_sectors, nextSector],
              };
            });
          }}
          onRemoveCompositionSector={(sector) => {
            setPlanTargetForm((current) => ({
              ...current,
              composition_sectors: current.composition_sectors.filter((item) => item !== sector),
            }));
          }}
          planForm={planForm}
          planTargetForm={planTargetForm}
          plans={plans}
          selectedPlan={selectedPlan}
          setPlanForm={setPlanForm}
          setPlanTargetForm={setPlanTargetForm}
        />
      ) : null}

      {activeTab === "positions" ? (
        <div className="stack">
          <PositionsSection
            browserCaptureAvailability={browserAvailabilityQuery.data?.available ?? {}}
            latestCaptures={latestCaptureQuery.data ?? {}}
            browserCaptureStatuses={browserStatusesQuery.data?.statuses ?? {}}
            busyAction={resolveBusyAction({
              [`queue-cnbc-${(queueCaptureMutation.variables as { id?: string } | undefined)?.id ?? ""}`]:
                queueCaptureMutation.isPending,
            })}
            onQueueCnbcCapture={(position) => queueCaptureMutation.mutate({ id: position.id, ticker: position.ticker })}
            plans={plans}
            positions={positions}
          />
          <QuoteRefreshSection
            refreshTask={quoteRefreshStatusQuery.data ?? null}
            onRefreshHeldQuotes={() => queueRefreshQuotesMutation.mutate()}
          />
          {snapshots.length == 0 ? (
            <></>
          ) : <SnapshotsSection
            busyAction={resolveBusyAction({
              [`delete-snapshot-${deleteSnapshotMutation.variables ?? ""}`]: deleteSnapshotMutation.isPending,
            })}
            onDeleteSnapshot={(snapshotId) => deleteSnapshotMutation.mutate(snapshotId)}
            snapshots={snapshots}
          />
          }
        </div>
      ) : null}

      {activeTab === "trades" ? (
        <div className="stack">
          <TradeEntrySection
            busyAction={resolveBusyAction({
              trade: tradeMutation.isPending,
            })}
            editingTradeId={editingTradeId}
            onCancelEditTrade={() => {
              setEditingTradeId(null);
              setTradeForm(initialTradeForm);
              pushToast("Trade edit cancelled.");
            }}
            onTradeSubmit={(event) => {
              event.preventDefault();
              tradeMutation.mutate({
                editingId: editingTradeId,
                payload: {
                  account_type: tradeForm.account_type,
                  ticker: tradeForm.ticker.toUpperCase(),
                  action: tradeForm.action,
                  quantity: Number(tradeForm.quantity),
                  price: Number(tradeForm.price),
                  broker: tradeForm.broker,
                  currency: tradeForm.currency,
                  fees: Number(tradeForm.fees),
                  sector: tradeForm.sector,
                  thesis: tradeForm.thesis || null,
                  notes: tradeForm.notes || null,
                  executed_at: tradeForm.executed_at || null,
                  review_date: tradeForm.review_date || null,
                },
              });
            }}
            setTradeForm={setTradeForm}
            tradeForm={tradeForm}
          />
          <TradesSection
            busyAction={resolveBusyAction({
              [`delete-trade-${deleteTradeMutation.variables ?? ""}`]: deleteTradeMutation.isPending,
            })}
            onDeleteTrade={(tradeId) => deleteTradeMutation.mutate(tradeId)}
            onStartEditTrade={(trade) => {
              setEditingTradeId(trade.id);
              setTradeForm({
                account_type: trade.account_type,
                ticker: trade.ticker,
                action: trade.action,
                quantity: String(trade.quantity),
                price: String(trade.price),
                broker: trade.broker,
                currency: trade.currency,
                fees: String(trade.fees),
                sector: trade.sector ?? "other",
                thesis: trade.thesis ?? "",
                notes: trade.notes ?? "",
                executed_at: toInputDateTime(trade.executed_at),
                review_date: toInputDateTime(trade.review_date),
              });
              pushToast(`Editing ${trade.action} ${formatTicker(trade.ticker)}`);
            }}
            trades={trades}
          />
        </div>
      ) : null}

      <ToastViewport onDismiss={dismissToast} toasts={toasts} />
    </div>
  );
}

function toInputDateTime(value: string | null): string {
  if (!value) return "";
  return value.slice(0, 16);
}

function resolveBusyAction(map: Record<string, boolean>): string | null {
  const match = Object.entries(map).find(([, active]) => active);
  return match ? match[0] : null;
}

function buildTradeSignature(trades: ManualTrade[]): string {
  return trades
    .map((trade) =>
      [
        trade.id,
        trade.ticker,
        trade.action,
        trade.quantity,
        trade.price,
        trade.fees,
        trade.broker,
        trade.currency,
        trade.executed_at,
        trade.review_date ?? "",
        trade.notes ?? "",
        trade.thesis ?? "",
      ].join(":")
    )
    .join("|");
}

function detectJournalPositionDrift(trades: ManualTrade[], positions: { ticker: string; broker: string; currency: string; quantity: number; average_price: number; opened_at: string | null }[]) {
  const expected = buildExpectedPositionsFromTrades(trades);
  const actual = positions
    .map((position) =>
      [
        position.ticker,
        position.broker,
        position.currency,
        Number(position.quantity).toFixed(8),
        Number(position.average_price).toFixed(8),
        position.opened_at ?? "",
      ].join("|")
    )
    .sort()
    .join(";");

  const expectedDigest = expected
    .map((position) =>
      [
        position.ticker,
        position.broker,
        position.currency,
        position.quantity.toFixed(8),
        position.averagePrice.toFixed(8),
        position.openedAt ?? "",
      ].join("|")
    )
    .sort()
    .join(";");

  return {
    hasMismatch: actual !== expectedDigest,
    tradeSignature: buildTradeSignature(trades),
    positionSignature: positions.map((position) => `${position.ticker}:${position.quantity}:${position.average_price}:${position.opened_at ?? ""}`).join("|"),
  };
}

function buildExpectedPositionsFromTrades(trades: ManualTrade[]) {
  const sorted = [...trades].sort(
    (left, right) => new Date(left.executed_at).getTime() - new Date(right.executed_at).getTime()
  );
  const running = new Map<
    string,
    {
      ticker: string;
      broker: string;
      currency: string;
      openedAt: string | null;
      lots: Array<{ quantity: number; unitPrice: number; fees: number }>;
    }
  >();

  for (const trade of sorted) {
    const key = [trade.account_type, trade.ticker, trade.broker, trade.currency].join("|");
    const state =
      running.get(key) ??
      {
        ticker: trade.ticker,
        broker: trade.broker,
        currency: trade.currency,
        openedAt: trade.executed_at,
        lots: [],
      };
    if (trade.action === "BUY") {
      const quantity = Number(trade.quantity);
      const fees = Number(trade.fees);
      const investedAmount = Math.max(Number(trade.price) - fees, 0);
      state.lots.push({
        quantity,
        unitPrice: quantity > 0 ? investedAmount / quantity : 0,
        fees,
      });
      state.openedAt = state.openedAt ?? trade.executed_at;
    } else {
      let remaining = Number(trade.quantity);
      while (remaining > 0 && state.lots.length > 0) {
        const lot = state.lots[0];
        if (lot.quantity <= remaining) {
          remaining -= lot.quantity;
          state.lots.shift();
        } else {
          lot.quantity -= remaining;
          remaining = 0;
        }
      }
    }
    running.set(key, state);
  }

  return Array.from(running.values())
    .filter((state) => state.lots.length > 0)
    .map((state) => {
      const quantity = state.lots.reduce((sum, lot) => sum + lot.quantity, 0);
      const totalCost = state.lots.reduce((sum, lot) => sum + lot.quantity * lot.unitPrice, 0);
      return {
        ticker: state.ticker,
        broker: state.broker,
        currency: state.currency,
        openedAt: state.openedAt,
        quantity,
        averagePrice: quantity > 0 ? totalCost / quantity : 0,
      };
    });
}
