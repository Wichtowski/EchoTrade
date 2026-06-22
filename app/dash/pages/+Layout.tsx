import type { ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";

import "./global.css";
import { CURRENCIES, type Currency } from "../src/lib/api";
import { AuthGate, AuthProvider, useAuth } from "../src/lib/auth";
import { queryClient } from "../src/lib/query";
import {
  ReportingCurrencyProvider,
  useReportingCurrency,
} from "../src/lib/reportingCurrency";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ReportingCurrencyProvider>
          <AuthGate>
            <AppShell>{children}</AppShell>
          </AuthGate>
        </ReportingCurrencyProvider>
      </AuthProvider>
    </QueryClientProvider>
  );
}

function AppShell({ children }: { children: ReactNode }) {
  const { logoutCurrentUser, user } = useAuth();
  const { reportingCurrency, setReportingCurrency } = useReportingCurrency();

  return (
    <div className="shell">
      <nav className="topbar">
        <div className="brand">
          <span className="brand-mark">EchoDash</span>
          <span className="brand-copy">Portfolio intelligence before automation</span>
        </div>
        <div className="nav">
          <a className="nav-link" href="/">
            Overview
          </a>
          <a className="nav-link" href="/positions">
            Positions & Journal
          </a>
          <a className="nav-link" href="/reviews">
            Reviews & Scans
          </a>
          {user?.role === "owner" ? (
            <a className="nav-link" href="/access">
              Access
            </a>
          ) : null}
          <label className="nav-currency-switcher">
            <select
              onChange={(event) => setReportingCurrency(event.target.value as Currency)}
              value={reportingCurrency}
            >
              {CURRENCIES.map((currency) => (
                <option key={currency} value={currency}>
                  {currency}
                </option>
              ))}
            </select>
          </label>
          <span className="pill">{user?.display_name || user?.email || "Private user"}</span>
          <button className="button button-small secondary" onClick={() => void logoutCurrentUser()} type="button">
            Sign out
          </button>
        </div>
      </nav>
      <main className="page">{children}</main>
    </div>
  );
}
