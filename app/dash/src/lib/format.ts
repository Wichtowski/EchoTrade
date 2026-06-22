export function formatMoney(value: number, currency: string): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

export function formatPlanAllocationPercent(value: number): string {
  if (value >= 99.5 && value < 100.5) {
    return "100%";
  }
  return formatPercent(value);
}

export function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

export function formatTicker(value: string): string {
  return value.replace(/-/g, ".");
}

export function normalizeTickerSymbol(value: string): string {
  return value.replace(/\./g, "-").toUpperCase();
}

export function normalizeTickerInput(value: string): string {
  return normalizeTickerSymbol(value);
}
