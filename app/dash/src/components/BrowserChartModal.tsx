import { useEffect, useMemo, useState } from "react";
import { FiBarChart2, FiBookmark, FiTrash2, FiX } from "react-icons/fi";
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
  BROWSER_CAPTURE_PROVIDERS,
  getLatestBrowserChartCapture,
  getTrades,
  type BrowserCaptureDocument,
  type BrowserCaptureProvider,
  type ManualTrade,
} from "../lib/api";
import {
  buildChartData,
  buildTradeMarkers,
  extractPriceBars,
  extractRanges,
  formatCompactPrice,
  formatXAxisTick,
  type ChartPoint,
  type PriceBar,
  type TradeMarker,
} from "../lib/browserCharts";
import { formatDateTime, formatMoney, formatTicker } from "../lib/format";

const DEFAULT_PROVIDER: BrowserCaptureProvider = BROWSER_CAPTURE_PROVIDERS[0];
const DEFAULT_RANGE = "1D";
const SAVED_BROWSER_CHARTS_KEY = "echoTrade.browserChartPresets";

type SavedBrowserChartPreset = {
  id: string;
  ticker: string;
  provider: BrowserCaptureProvider;
  preferredRange: string;
  name: string;
  createdAt: string;
  updatedAt: string;
};

export function BrowserChartButton({
  ticker,
  className = "chart-icon-button",
  hasChart = true,
}: {
  ticker: string;
  className?: string;
  hasChart?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const displayTicker = formatTicker(ticker);
  const unavailableMessage = `No chart available for ${displayTicker}`;
  return (
    <>
      <button
        aria-label={hasChart ? `Open chart for ${displayTicker}` : unavailableMessage}
        className={`${className}${hasChart ? "" : " chart-icon-button-disabled"}`}
        disabled={!hasChart}
        onClick={() => setOpen(true)}
        title={hasChart ? `Open chart for ${displayTicker}` : unavailableMessage}
        type="button"
      >
        <FiBarChart2 />
      </button>
      {open ? <BrowserChartModal ticker={ticker} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function BrowserChartModal({
  ticker,
  onClose,
}: {
  ticker: string;
  onClose: () => void;
}) {
  const [documentState, setDocumentState] = useState<BrowserCaptureDocument | null>(null);
  const [savedCharts, setSavedCharts] = useState<SavedBrowserChartPreset[]>([]);
  const [trades, setTrades] = useState<ManualTrade[]>([]);
  const [selectedRange, setSelectedRange] = useState(DEFAULT_RANGE);
  const [loading, setLoading] = useState(true);
  const [savingPreset, setSavingPreset] = useState(false);
  const [presetBusyId, setPresetBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const displayTicker = formatTicker(ticker);

  useEffect(() => {
    void Promise.all([loadDocument(), loadSavedCharts(), loadTrades()]);
  }, [ticker]);

  async function loadDocument() {
    setLoading(true);
    setError(null);
    try {
      const document = await getLatestBrowserChartCapture(DEFAULT_PROVIDER, ticker);
      setDocumentState(document);
      const firstRange = Object.keys(extractRanges(document.document))[0];
      setSelectedRange(firstRange ?? DEFAULT_RANGE);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load chart document");
    } finally {
      setLoading(false);
    }
  }

  async function loadSavedCharts() {
    setSavedCharts(readSavedBrowserChartPresets());
  }

  async function loadTrades() {
    try {
      const allTrades = await getTrades();
      setTrades(allTrades.filter((trade) => trade.ticker.toUpperCase() === ticker.toUpperCase()));
    } catch {
      setTrades([]);
    }
  }

  async function handleRememberChart() {
    setSavingPreset(true);
    try {
      const nextPreset = {
        id: `${DEFAULT_PROVIDER}:${ticker}`.toLowerCase(),
        ticker,
        provider: DEFAULT_PROVIDER,
        preferredRange: selectedRange,
        name: `${formatTicker(ticker)} · ${selectedRange}`,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      } satisfies SavedBrowserChartPreset;
      upsertSavedBrowserChartPreset(nextPreset);
      await loadSavedCharts();
    } finally {
      setSavingPreset(false);
    }
  }

  async function handleDeleteSavedChart(presetId: string) {
    setPresetBusyId(presetId);
    try {
      deleteSavedBrowserChartPreset(presetId);
      await loadSavedCharts();
    } finally {
      setPresetBusyId(null);
    }
  }

  const ranges = useMemo(() => extractRanges(documentState?.document ?? {}), [documentState]);
  const bars = useMemo(() => extractPriceBars(ranges[selectedRange]), [ranges, selectedRange]);
  const chartData = useMemo(() => buildChartData(bars), [bars]);
  const tradeMarkers = useMemo(() => buildTradeMarkers(chartData, trades), [chartData, trades]);
  const currency = inferCurrencyFromTicker(ticker);
  const latestClose = chartData.length > 0 ? chartData[chartData.length - 1].close : null;
  const rememberedCharts = savedCharts.filter((preset) => preset.ticker.toUpperCase() === ticker.toUpperCase());

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-shell" onClick={(event) => event.stopPropagation()}>
        <div className="panel-head">
          <div>
            <p className="panel-kicker">Stored browser capture</p>
            <h2 className="panel-title">{displayTicker} chart</h2>
            <p className="panel-copy">
              {documentState?.captured_at ? `Captured ${formatDateTime(documentState.captured_at)}` : "Latest saved browser payload"}
            </p>
          </div>
          <button aria-label="Close chart modal" className="chart-icon-button" onClick={onClose} type="button">
            <FiX />
          </button>
        </div>

        {loading ? <div className="status">Loading chart…</div> : null}
        {error ? <div className="status error">{error}</div> : null}

        {!loading && !error && documentState ? (
          <div className="stack">
            <div className="chart-actions">
              <div className="range-tabs">
                {Object.keys(ranges).map((range) => (
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
              <button
                className="button secondary button-small"
                disabled={savingPreset}
                onClick={() => void handleRememberChart()}
                type="button"
              >
                <FiBookmark />
                {savingPreset ? "Remembering…" : "Remember this chart"}
              </button>
            </div>

            <div className="chart-summary">
              <strong>{latestClose === null ? "—" : formatMoney(latestClose, currency)}</strong>
              <span>{chartData.length} price bars</span>
            </div>

            <div className="chart-frame chart-frame-pro">
              {chartData.length > 0 ? (
                <ResponsiveContainer height={360} width="100%">
                  <LineChart data={chartData} margin={{ top: 12, right: 16, left: -16, bottom: 4 }}>
                    <defs>
                      <linearGradient id="chartStroke" x1="0%" x2="0%" y1="0%" y2="100%">
                        <stop offset="0%" stopColor="#67d7c4" stopOpacity={1} />
                        <stop offset="100%" stopColor="#2d7a85" stopOpacity={0.45} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(151, 170, 198, 0.12)" vertical={false} />
                    <XAxis
                      dataKey="index"
                      domain={["dataMin", "dataMax"]}
                      minTickGap={24}
                      stroke="#9db0ca"
                      tickFormatter={(value) => formatXAxisTick(Number(value), chartData)}
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
                      formatter={(value) => formatMoney(Number(value ?? 0), currency)}
                      labelFormatter={(label, payload) =>
                        payload?.[0]?.payload?.time ? formatDateTime(String(payload[0].payload.time)) : String(label ?? "")
                      }
                    />
                    <Line
                      activeDot={{ fill: "#67d7c4", r: 4, stroke: "#07111f", strokeWidth: 2 }}
                      dataKey="close"
                      dot={false}
                      isAnimationActive={false}
                      stroke="url(#chartStroke)"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2.5}
                      type="monotone"
                    />
                    {tradeMarkers.map((marker) => (
                      <ReferenceDot
                        fill={marker.action === "BUY" ? "#67d7c4" : "#ff8f8f"}
                        key={marker.id}
                        label={{
                          fill: marker.action === "BUY" ? "#67d7c4" : "#ff8f8f",
                          fontSize: 11,
                          position: "top",
                          value: marker.action,
                        }}
                        r={5}
                        stroke="#07111f"
                        strokeWidth={2}
                        x={marker.index}
                        y={marker.close}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state">No price bars stored for this range yet.</div>
              )}
            </div>

            <div className="panel chart-query-panel">
              <div className="panel-head">
                <div>
                  <p className="panel-kicker">Browser remembered charts</p>
                  <h3 className="panel-title">Remembered chart presets for {displayTicker}</h3>
                </div>
                <span className="pill">{rememberedCharts.length} saved</span>
              </div>
              {rememberedCharts.length === 0 ? (
                <div className="empty-state">No remembered chart presets for this ticker on this browser yet.</div>
              ) : (
                <div className="saved-query-list">
                  {rememberedCharts.map((preset) => {
                    return (
                      <div className="saved-query-row" key={preset.id}>
                        <div>
                          <strong>{preset.name}</strong>
                          <div className="list-meta">
                            Preferred range {preset.preferredRange} · Saved {formatDateTime(preset.updatedAt)}
                          </div>
                        </div>
                        <div className="actions-inline">
                          <button
                            className="button secondary button-small"
                            onClick={() => setSelectedRange(preset.preferredRange)}
                            type="button"
                          >
                            Apply
                          </button>
                          <button
                            className="button secondary button-small"
                            disabled={presetBusyId === preset.id}
                            onClick={() => void handleDeleteSavedChart(preset.id)}
                            type="button"
                          >
                            <FiTrash2 />
                            {presetBusyId === preset.id ? "Deleting…" : "Delete"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}

function inferCurrencyFromTicker(ticker: string): string {
  return ticker.includes(".DE") || ticker.includes("-DE") ? "EUR" : "USD";
}

function readSavedBrowserChartPresets(): SavedBrowserChartPreset[] {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(SAVED_BROWSER_CHARTS_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(isSavedBrowserChartPreset);
  } catch {
    return [];
  }
}

function writeSavedBrowserChartPresets(presets: SavedBrowserChartPreset[]) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SAVED_BROWSER_CHARTS_KEY, JSON.stringify(presets));
}

function upsertSavedBrowserChartPreset(preset: SavedBrowserChartPreset) {
  const current = readSavedBrowserChartPresets();
  const existing = current.find((item) => item.id === preset.id);
  const next = [
    preset,
    ...current.filter((item) => item.id !== preset.id),
  ].map((item) =>
    item.id === preset.id && existing
      ? {
          ...item,
          createdAt: existing.createdAt,
        }
      : item
  );
  writeSavedBrowserChartPresets(next);
}

function deleteSavedBrowserChartPreset(presetId: string) {
  writeSavedBrowserChartPresets(readSavedBrowserChartPresets().filter((preset) => preset.id !== presetId));
}

function isSavedBrowserChartPreset(value: unknown): value is SavedBrowserChartPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const preset = value as Record<string, unknown>;
  return (
    typeof preset.id === "string" &&
    typeof preset.ticker === "string" &&
    typeof preset.provider === "string" &&
    typeof preset.preferredRange === "string" &&
    typeof preset.name === "string" &&
    typeof preset.createdAt === "string" &&
    typeof preset.updatedAt === "string"
  );
}
