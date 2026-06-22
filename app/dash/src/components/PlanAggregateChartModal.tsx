import { useMemo, useState } from "react";
import { FiBarChart2, FiX } from "react-icons/fi";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceDot,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  buildChartData,
  extractPriceBars,
  extractRanges,
  formatCompactPrice,
} from "../lib/browserCharts";
import { buildPlanProjection, summarizePlanProjectionByTicker, type PlanProjection } from "../lib/planAnalytics";
import { BrowserChartButton } from "./BrowserChartModal";
import { formatDateTime, formatMoney, formatTicker } from "../lib/format";
import type { BrowserCaptureDocument, InvestmentPlan } from "../lib/api";

const PLAN_LINE_COLORS = ["#67d7c4", "#7aa6ff", "#ffb86b", "#ff8f8f", "#9d8cff", "#8fe3a2", "#f7d66b", "#86d4ff", "#f19cff"];

export function PlanAggregateChartButton({
  plan,
  latestCaptures,
}: {
  plan: InvestmentPlan;
  latestCaptures: Record<string, BrowserCaptureDocument | null>;
}) {
  const [open, setOpen] = useState(false);
  const projection = useMemo(() => buildPlanProjection(plan, latestCaptures), [latestCaptures, plan]);
  const hasChart = Boolean(
    projection?.hasFullAllocation &&
      Object.values(projection.documents).some(
        (document) => document?.document && Object.keys(extractRanges(document.document)).length > 0
      )
  );
  const unavailableMessage = `No ETF charts available for ${plan.name}`;

  return (
    <>
      <button
        aria-label={hasChart ? `Open aggregate chart for ${plan.name}` : unavailableMessage}
        className={`chart-icon-button${hasChart ? "" : " chart-icon-button-disabled"}`}
        disabled={!hasChart}
        onClick={() => setOpen(true)}
        title={hasChart ? `Open aggregate chart for ${plan.name}` : unavailableMessage}
        type="button"
      >
        <FiBarChart2 />
      </button>
      {open && projection ? <PlanAggregateChartModal onClose={() => setOpen(false)} projection={projection} /> : null}
    </>
  );
}

function PlanAggregateChartModal({
  projection,
  onClose,
}: {
  projection: PlanProjection;
  onClose: () => void;
}) {
  const availableRanges = useMemo(() => {
    const documents = Object.values(projection.documents);
    if (documents.length === 0) {
      return [];
    }
    const rangeSets = documents.map((document) => new Set(Object.keys(extractRanges(document?.document ?? {}))));
    const [first, ...rest] = rangeSets;
    if (!first) {
      return [];
    }
    return Array.from(first).filter((range) => rest.every((set) => set.has(range)));
  }, [projection.documents]);
  const [selectedRange, setSelectedRange] = useState(availableRanges[0] ?? "1D");
  const series = useMemo(() => buildPlanEtfSeries(projection, selectedRange), [projection, selectedRange]);
  const chartData = useMemo(() => buildPlanComparisonRows(series), [series]);
  const buyMarkers = useMemo(() => buildPlanBuyMarkers(projection, series), [projection, series]);
  const etfSummaries = useMemo(() => {
    const positionSummaries = summarizePlanProjectionByTicker(projection);
    return projection.activeTickers.map((ticker, index) => {
      const points = series[ticker] ?? [];
      const summary = positionSummaries.find((item) => item.ticker === ticker) ?? null;
      return {
        ticker,
        color: PLAN_LINE_COLORS[index % PLAN_LINE_COLORS.length],
        available: points.length > 0,
        investedAmount: summary?.investedAmount ?? 0,
        currentValue: summary?.currentValue ?? null,
        pnl: summary?.pnl ?? null,
        contributionCount: summary?.contributionCount ?? 0,
      };
    });
  }, [projection, series]);

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-shell" onClick={(event) => event.stopPropagation()}>
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Investment plan ETFs</p>
            <h2 className="panel-title">{projection.name} ETF charts</h2>
            <p className="panel-copy">
              Actual stored chart data for each ETF in the plan, shown side by side on one timeline.
            </p>
          </div>
          <button aria-label="Close plan chart modal" className="chart-icon-button" onClick={onClose} type="button">
            <FiX />
          </button>
        </div>

        <div className="stack">
          <div className="chart-actions">
            <div className="range-tabs">
              {availableRanges.map((range) => (
                <button
                  className={`range-tab${range === selectedRange ? " active" : ""}`}
                  key={range}
                  onClick={() => setSelectedRange(range)}
                  type="button"
                >
                  {range}
                </button>
              ))}
            </div>
          </div>

          <div className="chart-summary">
            <strong>{projection.targetCount} ETFs</strong>
            <span>{projection.scheduledContributions} scheduled buys · {selectedRange} range</span>
          </div>

          <div className="chart-frame chart-frame-pro">
            {chartData.length > 0 ? (
              <ResponsiveContainer height={360} width="100%">
                <LineChart data={chartData} margin={{ top: 12, right: 16, left: -16, bottom: 4 }}>
                  <CartesianGrid stroke="rgba(151, 170, 198, 0.12)" vertical={false} />
                  <XAxis
                    dataKey="index"
                    domain={["dataMin", "dataMax"]}
                    minTickGap={24}
                    stroke="#9db0ca"
                    tickFormatter={(value) => formatPlanXAxisTick(Number(value), chartData)}
                    tickLine={false}
                    type="number"
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    stroke="#9db0ca"
                    tickFormatter={(value: number) => formatCompactPrice(value)}
                    tickLine={false}
                    width={64}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(7, 17, 31, 0.96)",
                      border: "1px solid rgba(151, 170, 198, 0.18)",
                      borderRadius: "14px",
                    }}
                    cursor={{ stroke: "rgba(103, 215, 196, 0.35)", strokeWidth: 1 }}
                    formatter={(value, name) => [formatMoney(Number(value ?? 0), projection.currency), formatTicker(String(name ?? ""))]}
                    labelFormatter={(label, payload) =>
                      payload?.[0]?.payload?.time ? formatDateTime(String(payload[0].payload.time)) : String(label ?? "")
                    }
                  />
                  {projection.activeTickers.map((ticker, index) =>
                    series[ticker]?.length ? (
                      <Line
                        activeDot={{ fill: PLAN_LINE_COLORS[index % PLAN_LINE_COLORS.length], r: 4, stroke: "#07111f", strokeWidth: 2 }}
                        dataKey={ticker}
                        dot={false}
                        isAnimationActive={false}
                        key={ticker}
                        name={ticker}
                        stroke={PLAN_LINE_COLORS[index % PLAN_LINE_COLORS.length]}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2.35}
                        type="monotone"
                      />
                    ) : null
                  )}
                  {buyMarkers.map((marker) => (
                    <ReferenceDot
                      fill={marker.color}
                      key={marker.id}
                      label={{
                        fill: marker.color,
                        fontSize: 10,
                        position: "top",
                        value: "B",
                      }}
                      r={4}
                      stroke="#07111f"
                      strokeWidth={2}
                      x={marker.index}
                      y={marker.close}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state">No ETF chart data available for this range yet.</div>
            )}
          </div>

          <div className="saved-query-list">
            {etfSummaries.map((item) => (
              <div className="saved-query-row" key={item.ticker}>
                <div>
                  <strong className="ticker-inline">
                    <span
                      aria-hidden="true"
                      style={{
                        width: "0.7rem",
                        height: "0.7rem",
                        borderRadius: "999px",
                        background: item.color,
                        display: "inline-block",
                      }}
                    />
                    <BrowserChartButton hasChart={item.available} ticker={item.ticker} />
                    {formatTicker(item.ticker)}
                  </strong>
                  <div className="list-meta">
                    {item.available
                      ? `${item.contributionCount} buys · invested ${formatMoney(item.investedAmount, projection.currency)} · ${
                          item.currentValue === null ? "value pending" : formatMoney(item.currentValue, projection.currency)
                        }${
                          item.pnl === null
                            ? ""
                            : ` · ${item.pnl >= 0 ? "+" : "-"}${formatMoney(Math.abs(item.pnl), projection.currency)}`
                        }`
                      : "No stored chart data for this ETF yet."}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function buildPlanEtfSeries(projection: PlanProjection, selectedRange: string) {
  return Object.fromEntries(
    projection.activeTickers.map((ticker) => {
      const document = projection.documents[ticker] ?? null;
      const points = buildChartData(extractPriceBars(extractRanges(document?.document ?? {})[selectedRange]));
      return [ticker, points] as const;
    })
  ) as Record<string, ReturnType<typeof buildChartData>>;
}

function buildPlanComparisonRows(series: Record<string, ReturnType<typeof buildChartData>>) {
  const timestamps = Array.from(
    new Set(
      Object.values(series)
        .flatMap((points) => points.map((point) => point.timeMs))
        .filter((value): value is number => value !== null)
    )
  ).sort((left, right) => left - right);

  return timestamps.map((timeMs, index) => {
    const row: Record<string, number | string | null> = {
      index,
      time: new Date(timeMs).toISOString(),
    };
    for (const [ticker, points] of Object.entries(series)) {
      const latest = findLatestChartPoint(points, timeMs);
      row[ticker] = latest?.close ?? null;
    }
    return row;
  });
}

function findLatestChartPoint(points: ReturnType<typeof buildChartData>, targetTimeMs: number) {
  let latest: ReturnType<typeof buildChartData>[number] | null = null;
  for (const point of points) {
    if (point.timeMs === null) {
      continue;
    }
    if (point.timeMs > targetTimeMs) {
      break;
    }
    latest = point;
  }
  return latest;
}

function buildPlanBuyMarkers(
  projection: PlanProjection,
  series: Record<string, ReturnType<typeof buildChartData>>
) {
  return projection.contributions
    .map((contribution) => {
      const tickerSeries = series[contribution.ticker] ?? [];
      if (tickerSeries.length === 0) {
        return null;
      }
      const tradeMs = new Date(contribution.executed_at).getTime();
      if (Number.isNaN(tradeMs)) {
        return null;
      }
      const nearest = findNearestChartPoint(tickerSeries, tradeMs);
      if (!nearest) {
        return null;
      }
      const tickerIndex = projection.activeTickers.indexOf(contribution.ticker);
      return {
        id: contribution.id,
        index: nearest.index,
        close: nearest.close,
        color: PLAN_LINE_COLORS[Math.max(0, tickerIndex) % PLAN_LINE_COLORS.length],
      };
    })
    .filter((marker): marker is { id: string; index: number; close: number; color: string } => marker !== null);
}

function findNearestChartPoint(
  points: ReturnType<typeof buildChartData>,
  targetTimeMs: number
) {
  const pointsWithTime = points.filter((point) => point.timeMs !== null);
  if (pointsWithTime.length === 0) {
    return null;
  }
  let nearest = pointsWithTime[0];
  let nearestDistance = Math.abs((nearest.timeMs ?? targetTimeMs) - targetTimeMs);
  for (const point of pointsWithTime) {
    const distance = Math.abs((point.timeMs ?? targetTimeMs) - targetTimeMs);
    if (distance < nearestDistance) {
      nearest = point;
      nearestDistance = distance;
    }
  }
  return nearest;
}

function formatPlanXAxisTick(
  value: number,
  rows: Array<Record<string, number | string | null>>
) {
  if (!Number.isFinite(value) || rows.length === 0) {
    return "";
  }
  const row = rows[Math.max(0, Math.min(rows.length - 1, Math.round(value)))];
  const time = typeof row?.time === "string" ? row.time : null;
  if (!time) {
    return "";
  }
  return new Date(time).toLocaleDateString("en-GB", { month: "short", day: "numeric" });
}
