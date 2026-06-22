const configuredApiBaseUrl =
  typeof import.meta.env.VITE_API_BASE_URL === "string"
    ? import.meta.env.VITE_API_BASE_URL.trim().replace(/\/+$/, "")
    : "";

export const API_BASE_URL = configuredApiBaseUrl || "http://localhost:8000";

export const CURRENCIES = ["PLN", "USD", "EUR", "GBP"] as const;
export const BROKERS = ["XTB", "Revolut"] as const;
export const BROWSER_CAPTURE_PROVIDERS = ["cnbc"] as const;
export const SECTORS = [
  "semis",
  "ai_infra",
  "software",
  "real_estate",
  "metals",
  "defense",
  "broad_market",
  "etfs",
  "industrials",
  "healthcare",
  "energy",
  "financials",
  "consumer",
  "other",
] as const;

export type Currency = (typeof CURRENCIES)[number];
export type Broker = (typeof BROKERS)[number];
export type BrowserCaptureProvider = (typeof BROWSER_CAPTURE_PROVIDERS)[number];
export type Sector = (typeof SECTORS)[number];
export type UserRole = "owner" | "invited_viewer";
export type InviteDeliveryState = "link_only" | "sent" | "failed";

export type InvestmentPlanTarget = {
  id: string;
  plan_id: string;
  ticker: string;
  currency: Currency;
  weight_pct: number;
  sector: Sector | null;
  composition_sectors: string[];
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type InvestmentPlanPause = {
  id: string;
  plan_id: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  created_at: string;
};

export type InvestmentPlanAmountChange = {
  id: string;
  plan_id: string;
  effective_date: string;
  monthly_amount: number;
  note: string | null;
  created_at: string;
};

export type InvestmentPlanOneOffContribution = {
  id: string;
  plan_id: string;
  contribution_date: string;
  amount: number;
  note: string | null;
  created_at: string;
};

export type InvestmentPlan = {
  id: string;
  account_type: string;
  name: string;
  broker: Broker;
  currency: Currency;
  monthly_amount: number;
  contribution_day: number;
  start_date: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
  next_run_on: string | null;
  scheduled_contributions: number;
  expected_contributions_total: number;
  target_allocation_total: number;
  targets: InvestmentPlanTarget[];
  pauses: InvestmentPlanPause[];
  amount_changes: InvestmentPlanAmountChange[];
  one_off_contributions: InvestmentPlanOneOffContribution[];
};

export type Position = {
  id: string;
  account_type: string;
  ticker: string;
  quantity: number;
  average_price: number;
  broker: Broker;
  currency: Currency;
  sector: Sector | null;
  thesis: string | null;
  opened_at: string | null;
  created_at: string;
  updated_at: string;
};

export type ManualTrade = {
  id: string;
  account_type: string;
  ticker: string;
  action: "BUY" | "SELL";
  quantity: number;
  price: number;
  broker: Broker;
  currency: Currency;
  fees: number;
  sector: Sector | null;
  thesis: string | null;
  notes: string | null;
  review_date: string | null;
  executed_at: string;
  created_at: string;
};

export type MarketQuote = {
  symbol: string;
  price: number;
  currency: Currency;
  source: string;
  source_timestamp: string | null;
  received_at: string;
  delay_seconds: number | null;
  confidence: string | null;
  warnings: string[] | null;
};

export type AuthStatus = {
  has_users: boolean;
  authenticated: boolean;
};

export type AuthUser = {
  id: string;
  email: string;
  display_name: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
};

export type Invite = {
  id: string;
  email: string | null;
  role: UserRole;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  invite_url: string | null;
  delivery_state: InviteDeliveryState | null;
  delivery_error: string | null;
};

export type MarketHistoryBar = {
  symbol: string;
  resolution: string;
  bar_time: string;
  open_price: number;
  high_price: number;
  low_price: number;
  close_price: number;
  volume: number | null;
  source: string;
  captured_at: string;
};

export type MarketHistoryCaptureResult = {
  symbol: string;
  resolution: string;
  started_at: string;
  ended_at: string;
  bars_written: number;
  bars: MarketHistoryBar[];
  source: string;
  warnings: string[];
};

export type PortfolioRisk = {
  total_value: number;
  currency: string;
  ticker_allocation: Record<string, number>;
  sector_allocation: Record<string, number>;
  warnings: string[];
};

export type PortfolioPositionBreakdown = {
  ticker: string;
  quantity: number;
  average_price: number;
  current_price: number;
  currency: Currency;
  reporting_currency: Currency;
  market_value: number;
  market_value_native: number;
  cost_basis_native: number;
  cost_basis: number;
  pnl_native: number;
  pnl: number;
  sector: string | null;
  price_source: string | null;
  fx_rate_to_reporting: number;
};

export type PortfolioOverview = {
  total_value: number;
  currency: Currency;
  positions: PortfolioPositionBreakdown[];
  risk: PortfolioRisk;
};

export type PortfolioSnapshot = {
  id: string;
  created_at: string;
  account_type: string;
  total_value: number;
  currency: Currency;
  positions: Record<string, Record<string, string | number | null>>;
  allocation: Record<string, number> | null;
  risk_summary: Record<string, unknown> | null;
};

export type WeeklyReviewPositionInsight = {
  ticker: string;
  market_value: number;
  pnl: number;
  allocation_pct: number;
  allocation_change_pct: number | null;
  sector: string | null;
};

export type WeeklyReview = {
  id: string;
  created_at: string;
  account_type: string;
  period_start: string;
  period_end: string;
  reporting_currency: Currency;
  total_value: number;
  total_value_change: number | null;
  trade_count: number;
  buy_count: number;
  sell_count: number;
  top_winners: WeeklyReviewPositionInsight[];
  top_losers: WeeklyReviewPositionInsight[];
  concentration_changes: Record<string, number>;
  due_review_tickers: string[];
  warnings: string[];
  summary: string;
  insights: string[];
};

export type OpportunityCandidate = {
  ticker: string;
  sector: string | null;
  currency: Currency | null;
  source: string;
  held: boolean;
  has_fresh_quote: boolean;
  has_chart: boolean;
  latest_price: number | null;
  market_value: number | null;
  target_weight_pct: number | null;
  thesis_due: boolean;
  score: number;
  notes: string[];
};

export type OpportunityScan = {
  id: string;
  created_at: string;
  account_type: string;
  cadence: string;
  plan_id: string | null;
  candidate_count: number;
  summary: string;
  warnings: string[];
  tickers: string[];
  candidates: OpportunityCandidate[];
};

type RefreshHeldQuotesResponse = {
  requested_symbols: string[];
  stored_quotes: MarketQuote[];
  provider: string;
  failed_symbols: string[];
};

export type QuoteRefreshTask = {
  task_id: string;
  provider: string;
  requested_symbols: string[];
  status: string;
  stored_count: number;
  failed_symbols: string[];
  error: string | null;
  updated_at: string | null;
};

type MarketHistoryResponse = {
  symbol: string;
  resolution: string;
  data: MarketHistoryBar[];
};

export type BrowserCaptureTask = {
  task_id: string;
  symbol: string;
  provider: BrowserCaptureProvider;
  status: string;
  time_ranges: string[];
  document_id: string | null;
  error: string | null;
  error_stage: string | null;
  error_code: string | null;
  retryable: boolean | null;
  error_details: Record<string, string> | null;
  updated_at: string | null;
};

type BrowserCaptureStatusResponse = {
  statuses: Record<string, BrowserCaptureTask | null>;
  time_ranges: string[];
  provider: BrowserCaptureProvider;
};

type BrowserCaptureAvailabilityResponse = {
  provider: BrowserCaptureProvider;
  available: Record<string, boolean>;
};

export type BrowserCaptureDocument = {
  provider: BrowserCaptureProvider;
  symbol: string;
  document_id: string;
  captured_at: string | null;
  document: Record<string, unknown>;
};

export type SavedQueryKind = "browser_chart";

export type SavedQuery = {
  id: string;
  kind: SavedQueryKind;
  name: string;
  payload: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function getPositions(): Promise<Position[]> {
  return request<Position[]>("/positions");
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/auth/status");
}

export function getCurrentUser(): Promise<AuthUser> {
  return request<AuthUser>("/auth/me");
}

export function login(payload: { email: string; password: string }): Promise<AuthUser> {
  return request<AuthUser>("/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logout(): Promise<void> {
  return request<void>("/auth/logout", {
    method: "POST",
  });
}

export function getInvites(): Promise<Invite[]> {
  return request<Invite[]>("/auth/invites");
}

export function createInvite(payload: {
  email?: string | null;
  role?: UserRole;
  expires_in_hours?: number;
}): Promise<Invite> {
  return request<Invite>("/auth/invites", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function revokeInvite(inviteId: string): Promise<Invite> {
  return request<Invite>(`/auth/invites/${inviteId}/revoke`, {
    method: "POST",
  });
}

export function acceptInvite(payload: {
  token: string;
  email: string;
  password: string;
  display_name?: string | null;
}): Promise<AuthUser> {
  return request<AuthUser>("/auth/invites/accept", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getPortfolioOverview(reportingCurrency?: string): Promise<PortfolioOverview> {
  const params = reportingCurrency ? `?reporting_currency=${encodeURIComponent(reportingCurrency)}` : "";
  return request<PortfolioOverview>(`/portfolio/overview${params}`);
}

export function getInvestmentPlans(): Promise<InvestmentPlan[]> {
  return request<InvestmentPlan[]>("/investment-plans");
}

export function createInvestmentPlan(payload: Record<string, unknown>): Promise<InvestmentPlan> {
  return request<InvestmentPlan>("/investment-plans", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateInvestmentPlan(planId: string, payload: Record<string, unknown>): Promise<InvestmentPlan> {
  return request<InvestmentPlan>(`/investment-plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteInvestmentPlan(planId: string): Promise<void> {
  return request<void>(`/investment-plans/${planId}`, {
    method: "DELETE",
  });
}

export function createInvestmentPlanTarget(
  planId: string,
  payload: Record<string, unknown>,
): Promise<InvestmentPlanTarget> {
  return request<InvestmentPlanTarget>(`/investment-plans/${planId}/targets`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateInvestmentPlanTarget(
  targetId: string,
  payload: Record<string, unknown>,
): Promise<InvestmentPlanTarget> {
  return request<InvestmentPlanTarget>(`/investment-plans/targets/${targetId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteInvestmentPlanTarget(targetId: string): Promise<void> {
  return request<void>(`/investment-plans/targets/${targetId}`, {
    method: "DELETE",
  });
}

export function createInvestmentPlanPause(
  planId: string,
  payload: Record<string, unknown>,
): Promise<InvestmentPlanPause> {
  return request<InvestmentPlanPause>(`/investment-plans/${planId}/pauses`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteInvestmentPlanPause(pauseId: string): Promise<void> {
  return request<void>(`/investment-plans/pauses/${pauseId}`, {
    method: "DELETE",
  });
}

export function createInvestmentPlanAmountChange(
  planId: string,
  payload: Record<string, unknown>,
): Promise<InvestmentPlanAmountChange> {
  return request<InvestmentPlanAmountChange>(`/investment-plans/${planId}/amount-changes`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteInvestmentPlanAmountChange(changeId: string): Promise<void> {
  return request<void>(`/investment-plans/amount-changes/${changeId}`, {
    method: "DELETE",
  });
}

export function createInvestmentPlanOneOffContribution(
  planId: string,
  payload: Record<string, unknown>,
): Promise<InvestmentPlanOneOffContribution> {
  return request<InvestmentPlanOneOffContribution>(`/investment-plans/${planId}/one-off-contributions`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteInvestmentPlanOneOffContribution(contributionId: string): Promise<void> {
  return request<void>(`/investment-plans/one-off-contributions/${contributionId}`, {
    method: "DELETE",
  });
}

export function createPosition(payload: Record<string, unknown>): Promise<Position> {
  return request<Position>("/positions", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updatePosition(positionId: string, payload: Record<string, unknown>): Promise<Position> {
  return request<Position>(`/positions/${positionId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deletePosition(positionId: string): Promise<void> {
  return request<void>(`/positions/${positionId}`, {
    method: "DELETE",
  });
}

export function syncPositionsFromTrades(): Promise<Position[]> {
  return request<Position[]>("/positions/sync-from-trades", {
    method: "POST",
  });
}

export function getTrades(): Promise<ManualTrade[]> {
  return request<ManualTrade[]>("/trades");
}

export function createTrade(payload: Record<string, unknown>): Promise<ManualTrade> {
  return request<ManualTrade>("/trades", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTrade(tradeId: string, payload: Record<string, unknown>): Promise<ManualTrade> {
  return request<ManualTrade>(`/trades/${tradeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTrade(tradeId: string): Promise<void> {
  return request<void>(`/trades/${tradeId}`, {
    method: "DELETE",
  });
}

export function getRisk(reportingCurrency?: Currency): Promise<PortfolioRisk> {
  const searchParams = new URLSearchParams();
  if (reportingCurrency) {
    searchParams.set("reporting_currency", reportingCurrency);
  }
  return request<PortfolioRisk>(`/portfolio/risk${searchParams.size ? `?${searchParams.toString()}` : ""}`);
}

export function getSnapshots(): Promise<PortfolioSnapshot[]> {
  return request<PortfolioSnapshot[]>("/portfolio/snapshot");
}

export function createSnapshot(reportingCurrency?: Currency): Promise<PortfolioSnapshot> {
  const searchParams = new URLSearchParams();
  if (reportingCurrency) {
    searchParams.set("reporting_currency", reportingCurrency);
  }
  return request<PortfolioSnapshot>(`/portfolio/snapshot${searchParams.size ? `?${searchParams.toString()}` : ""}`, { method: "POST" });
}

export function deleteSnapshot(snapshotId: string): Promise<void> {
  return request<void>(`/portfolio/snapshot/${snapshotId}`, { method: "DELETE" });
}

export function getWeeklyReviews(): Promise<WeeklyReview[]> {
  return request<WeeklyReview[]>("/reviews/weekly");
}

export function runWeeklyReview(payload: {
  account_type?: string;
  reporting_currency?: Currency;
  period_days?: number;
}): Promise<WeeklyReview> {
  return request<WeeklyReview>("/reviews/weekly/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getOpportunityScans(): Promise<OpportunityScan[]> {
  return request<OpportunityScan[]>("/reviews/opportunity-scans");
}

export function runOpportunityScan(payload: {
  account_type?: string;
  plan_id?: string | null;
  tickers?: string[];
  cadence?: string;
  limit?: number;
}): Promise<OpportunityScan> {
  return request<OpportunityScan>("/reviews/opportunity-scans/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function refreshHeldQuotes(): Promise<RefreshHeldQuotesResponse> {
  return request<RefreshHeldQuotesResponse>("/market/quotes/refresh-held", {
    method: "POST",
  });
}

export function queueRefreshHeldQuotes(): Promise<QuoteRefreshTask> {
  return request<QuoteRefreshTask>("/market/quotes/refresh-held/queue", {
    method: "POST",
  });
}

export function getRefreshHeldQuotesStatus(): Promise<QuoteRefreshTask | null> {
  return request<QuoteRefreshTask | null>("/market/quotes/refresh-held/status");
}

export function captureWeeklyHistory(symbol: string): Promise<MarketHistoryCaptureResult> {
  return request<MarketHistoryCaptureResult>(`/market/history/capture/${encodeURIComponent(symbol)}`, {
    method: "POST",
  });
}

export function getStoredHistory(symbol: string, resolution = "W"): Promise<MarketHistoryResponse> {
  const searchParams = new URLSearchParams({ symbol, resolution });
  return request<MarketHistoryResponse>(`/market/history?${searchParams.toString()}`);
}

export function queueBrowserChartCapture(
  provider: BrowserCaptureProvider,
  ticker: string,
): Promise<BrowserCaptureTask> {
  return request<BrowserCaptureTask>(
    `/market/browser/capture/${encodeURIComponent(provider)}/${encodeURIComponent(ticker)}`,
    {
      method: "POST",
    }
  );
}

export function getBrowserChartCaptureStatuses(
  provider: BrowserCaptureProvider,
  symbols: string[],
): Promise<BrowserCaptureStatusResponse> {
  const searchParams = new URLSearchParams({ symbols: symbols.join(",") });
  return request<BrowserCaptureStatusResponse>(
    `/market/browser/capture/${encodeURIComponent(provider)}/status?${searchParams.toString()}`
  );
}

export function getBrowserChartCaptureAvailability(
  provider: BrowserCaptureProvider,
  symbols: string[],
): Promise<BrowserCaptureAvailabilityResponse> {
  const searchParams = new URLSearchParams({ symbols: symbols.join(",") });
  return request<BrowserCaptureAvailabilityResponse>(
    `/market/browser/capture/${encodeURIComponent(provider)}/availability?${searchParams.toString()}`
  );
}

export function getLatestBrowserChartCapture(
  provider: BrowserCaptureProvider,
  ticker: string,
): Promise<BrowserCaptureDocument> {
  return request<BrowserCaptureDocument>(
    `/market/browser/capture/${encodeURIComponent(provider)}/${encodeURIComponent(ticker)}/latest`
  );
}

export function getSavedQueries(kind: SavedQueryKind): Promise<SavedQuery[]> {
  const searchParams = new URLSearchParams({ kind });
  return request<SavedQuery[]>(`/market/saved-queries?${searchParams.toString()}`);
}

export function createSavedQuery(payload: {
  kind: SavedQueryKind;
  name: string;
  payload: Record<string, unknown>;
}): Promise<SavedQuery> {
  return request<SavedQuery>("/market/saved-queries", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteSavedQuery(savedQueryId: string): Promise<void> {
  return request<void>(`/market/saved-queries/${encodeURIComponent(savedQueryId)}`, {
    method: "DELETE",
  });
}
