import type { BrowserCaptureDocument } from "./api";

export type PriceBar = {
  close: string;
  tradeTime?: string;
  tradeTimeinMills?: string;
};

export type ChartPoint = {
  index: number;
  close: number;
  tickLabel: string;
  time: string | null;
  timeMs: number | null;
};

export type TradeMarker = {
  id: string;
  index: number;
  close: number;
  action: "BUY" | "SELL";
  tradeTime: string;
  tradePrice: number;
};

export type ChartTradeLike = {
  id: string;
  action: "BUY" | "SELL";
  executed_at: string;
  price: number;
};

export function extractRanges(document: Record<string, unknown>): Record<string, Record<string, unknown>> {
  const ranges = document.ranges;
  if (!ranges || typeof ranges !== "object") {
    return {};
  }
  return ranges as Record<string, Record<string, unknown>>;
}

export function extractPriceBars(payload: Record<string, unknown> | undefined): PriceBar[] {
  const data = payload?.data;
  if (!data || typeof data !== "object") {
    return [];
  }
  const chartData = (data as Record<string, unknown>).chartData;
  if (!chartData || typeof chartData !== "object") {
    return [];
  }
  const priceBars = (chartData as Record<string, unknown>).priceBars;
  return Array.isArray(priceBars) ? (priceBars as PriceBar[]) : [];
}

export function buildChartData(bars: PriceBar[]): ChartPoint[] {
  return bars
    .map((bar, index) => {
      const close = Number.parseFloat(bar.close);
      if (!Number.isFinite(close)) {
        return null;
      }
      const time = extractTimestamp(bar);
      return {
        index,
        close,
        tickLabel: buildAxisLabel(time, index, bars.length),
        time,
        timeMs: time ? new Date(time).getTime() : null,
      };
    })
    .filter((point): point is ChartPoint => point !== null);
}

export function buildTradeMarkers(points: ChartPoint[], trades: ChartTradeLike[]): TradeMarker[] {
  if (points.length === 0) {
    return [];
  }
  const pointsWithTime = points.filter((point) => point.timeMs !== null);
  if (pointsWithTime.length === 0) {
    return [];
  }
  return trades
    .map((trade) => {
      const tradeMs = new Date(trade.executed_at).getTime();
      if (Number.isNaN(tradeMs)) {
        return null;
      }
      let nearest = pointsWithTime[0];
      let nearestDistance = Math.abs((nearest.timeMs ?? tradeMs) - tradeMs);
      for (const point of pointsWithTime) {
        const distance = Math.abs((point.timeMs ?? tradeMs) - tradeMs);
        if (distance < nearestDistance) {
          nearest = point;
          nearestDistance = distance;
        }
      }
      return {
        id: trade.id,
        index: nearest.index,
        close: nearest.close,
        action: trade.action,
        tradeTime: trade.executed_at,
        tradePrice: trade.price,
      };
    })
    .filter((marker): marker is TradeMarker => marker !== null);
}

export function extractLatestClose(document: BrowserCaptureDocument | null): number | null {
  if (!document || !document.document || typeof document.document !== "object") {
    return null;
  }
  const ranges = (document.document as Record<string, unknown>).ranges;
  if (!ranges || typeof ranges !== "object") {
    return null;
  }

  const orderedRanges = ["1D", "5D", "1M", "3M", "6M"];
  for (const rangeKey of orderedRanges) {
    const latest = extractLatestCloseFromRange((ranges as Record<string, unknown>)[rangeKey]);
    if (latest !== null) {
      return latest;
    }
  }

  for (const range of Object.values(ranges as Record<string, unknown>)) {
    const latest = extractLatestCloseFromRange(range);
    if (latest !== null) {
      return latest;
    }
  }

  return null;
}

export function formatXAxisTick(value: number, points: ChartPoint[]): string {
  if (!Number.isFinite(value) || points.length === 0) {
    return "";
  }
  const point = points[Math.max(0, Math.min(points.length - 1, Math.round(value)))];
  return point?.tickLabel ?? "";
}

export function formatCompactPrice(value: number): string {
  if (!Number.isFinite(value)) {
    return "—";
  }
  if (Math.abs(value) >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return value.toFixed(value >= 100 ? 0 : 2);
}

function extractLatestCloseFromRange(range: unknown): number | null {
  if (!range || typeof range !== "object") {
    return null;
  }
  const bars = extractPriceBars(range as Record<string, unknown>);
  for (let index = bars.length - 1; index >= 0; index -= 1) {
    const close = Number.parseFloat(String((bars[index] as Record<string, unknown>).close ?? ""));
    if (Number.isFinite(close)) {
      return close;
    }
  }
  return null;
}

function extractTimestamp(bar: PriceBar): string | null {
  if (bar.tradeTime) {
    const parsed = new Date(bar.tradeTime);
    if (!Number.isNaN(parsed.getTime())) {
      return parsed.toISOString();
    }
  }
  if (bar.tradeTimeinMills) {
    const parsed = Number.parseInt(bar.tradeTimeinMills, 10);
    if (Number.isFinite(parsed)) {
      const normalized = parsed < 10_000_000_000 ? parsed * 1000 : parsed;
      const timestamp = new Date(normalized);
      if (!Number.isNaN(timestamp.getTime())) {
        return timestamp.toISOString();
      }
    }
  }
  return null;
}

function buildAxisLabel(time: string | null, index: number, total: number): string {
  if (!time) {
    return String(index + 1);
  }
  const date = new Date(time);
  if (Number.isNaN(date.getTime())) {
    return String(index + 1);
  }
  if (total <= 12) {
    return date.toLocaleDateString("en-GB", { month: "short", day: "numeric" });
  }
  return date.toLocaleDateString("en-GB", { month: "short", day: "numeric" });
}
