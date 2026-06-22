import { QueryClient } from "@tanstack/react-query";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const queryKeys = {
  plans: ["plans"] as const,
  positions: ["positions"] as const,
  trades: ["trades"] as const,
  invites: ["invites"] as const,
  weeklyReviews: ["weekly-reviews"] as const,
  opportunityScans: ["opportunity-scans"] as const,
  quoteRefreshStatus: ["quote-refresh-status"] as const,
  snapshots: ["snapshots"] as const,
  risk: (reportingCurrency: string) => ["risk", reportingCurrency] as const,
  browserCaptureStatuses: (provider: string, symbols: string[]) =>
    ["browser-capture-statuses", provider, ...symbols] as const,
  browserCaptureAvailability: (provider: string, symbols: string[]) =>
    ["browser-capture-availability", provider, ...symbols] as const,
  browserCaptureLatest: (provider: string, symbols: string[]) =>
    ["browser-capture-latest", provider, ...symbols] as const,
} as const;
