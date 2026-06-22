import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

import { CURRENCIES, type Currency } from "./api";

const STORAGE_KEY = "echodash.reportingCurrency";

type ReportingCurrencyContextValue = {
  reportingCurrency: Currency;
  setReportingCurrency: (currency: Currency) => void;
};

const ReportingCurrencyContext = createContext<ReportingCurrencyContextValue | null>(null);

export function ReportingCurrencyProvider({ children }: { children: ReactNode }) {
  const [reportingCurrency, setReportingCurrencyState] = useState<Currency>("USD");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && CURRENCIES.includes(stored as Currency)) {
      setReportingCurrencyState(stored as Currency);
    }
  }, []);

  const value = useMemo<ReportingCurrencyContextValue>(
    () => ({
      reportingCurrency,
      setReportingCurrency: (currency) => {
        setReportingCurrencyState(currency);
        if (typeof window !== "undefined") {
          window.localStorage.setItem(STORAGE_KEY, currency);
        }
      },
    }),
    [reportingCurrency]
  );

  return (
    <ReportingCurrencyContext.Provider value={value}>
      {children}
    </ReportingCurrencyContext.Provider>
  );
}

export function useReportingCurrency() {
  const context = useContext(ReportingCurrencyContext);
  if (!context) {
    throw new Error("useReportingCurrency must be used within ReportingCurrencyProvider");
  }
  return context;
}
