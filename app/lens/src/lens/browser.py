"""EchoLens browser research service.

EchoLens captures contextual market research when structured APIs are insufficient.
It is NOT an execution data source.

EchoLens must not:
- bypass paywalls or CAPTCHAs
- use stolen cookies or scrape private sessions
- ignore robots.txt or website terms
- scrape aggressively
- act as primary source for execution-grade prices
- execute trades
- modify portfolio data directly
- send unverified information directly to EchoBot
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import json
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

CNBC_CAPTURE_TIME_RANGES = ["1D", "5D", "1M", "3M", "6M", "YTD", "1Y", "5Y", "ALL"]
ARTIFACTS_DIR = Path("app/lens/artifacts/playwright")
REALISTIC_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
REALISTIC_ACCEPT_LANGUAGE = "en-US,en;q=0.9,pl;q=0.8"
STEALTH_INIT_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'pl'] });
Object.defineProperty(navigator, 'platform', { get: () => 'Linux x86_64' });
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'Chrome PDF Plugin' },
    { name: 'Chrome PDF Viewer' },
    { name: 'Native Client' }
  ]
});
window.chrome = window.chrome || {
  runtime: {},
  app: {},
  csi: () => ({}),
  loadTimes: () => ({})
};
"""
CNBC_TIME_RANGE_SELECTORS = {
    "1D": ".range-1today",
    "5D": ".range-5day",
    "1M": ".range-1month",
    "3M": ".range-3month",
    "6M": ".range-6month",
    "YTD": ".range-1ytd",
    "1Y": ".range-1year",
    "5Y": ".range-5year",
    "ALL": ".range-1all",
}


@dataclass
class LensObservation:
    label: str
    value: str
    confidence: str = "low"


@dataclass
class LensResult:
    source: str
    url: str
    symbol: str
    data_type: str
    page_title: str | None = None
    document: dict[str, object] | None = None
    raw_text: str | None = None
    observations: list[LensObservation] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=lambda: [
        "Visible price may be delayed.",
        "This data must not be used as execution-grade market data.",
    ])


class LensCaptureError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        stage: str,
        code: str,
        retryable: bool,
        details: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.code = code
        self.retryable = retryable
        self.details = details or {}


def _slugify_symbol(symbol: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in symbol).strip("-")


def _build_artifact_paths(symbol: str) -> tuple[Path, Path, Path]:
    run_dir = ARTIFACTS_DIR / _slugify_symbol(symbol)
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir, run_dir / "trace.zip", run_dir / "failure.png"


async def take_snapshot(url: str, symbol: str) -> LensResult:
    """Navigate to a URL and extract visible market data.

    TODO: Use Playwright to open page, extract text, capture screenshot.
    """
    return LensResult(
        source="",
        url=url,
        symbol=symbol,
        data_type="market_page_snapshot",
    )


async def extract_chart(url: str, symbol: str) -> LensResult:
    """Capture a chart screenshot from a financial page.

    TODO: Use Playwright to navigate, wait for chart render, screenshot.
    """
    return LensResult(
        source="",
        url=url,
        symbol=symbol,
        data_type="chart_screenshot",
    )


async def extract_table(url: str, symbol: str) -> LensResult:
    """Extract visible table data from a financial page.

    TODO: Use Playwright to extract table elements as structured data.
    """
    return LensResult(
        source="",
        url=url,
        symbol=symbol,
        data_type="table_extraction",
    )


async def search_ticker(symbol: str, sites: list[str] | None = None) -> list[LensResult]:
    """Search multiple configured sites for a ticker.

    TODO: Iterate configured sites, extract summaries.
    """
    return []


def _extract_chart_data(payload: dict[str, object]) -> dict[str, object] | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    chart_data = data.get("chartData")
    return chart_data if isinstance(chart_data, dict) else None


def _extract_chart_time_range(payload: dict[str, object]) -> str | None:
    chart_data = _extract_chart_data(payload)
    if chart_data is None:
        return None
    time_range = chart_data.get("timeRange")
    return str(time_range).upper() if isinstance(time_range, str) and time_range else None


def _build_chart_observations(chart_document: dict[str, object]) -> list[LensObservation]:
    symbol = str(chart_document.get("symbol", ""))
    ranges = chart_document.get("ranges")
    if not isinstance(ranges, dict):
        return [LensObservation(label="symbol", value=symbol, confidence="medium")]

    observations = [LensObservation(label="symbol", value=symbol, confidence="medium")]
    for time_range, payload in ranges.items():
        if not isinstance(payload, dict):
            continue
        chart_data = _extract_chart_data(payload)
        if chart_data is None:
            continue
        price_bars = chart_data.get("priceBars")
        bar_count = len(price_bars) if isinstance(price_bars, list) else 0
        observations.append(
            LensObservation(
                label=f"{time_range.lower()}_price_bar_count",
                value=str(bar_count),
                confidence="medium",
            )
        )
    return observations


def _is_chart_response(
    response_url: str,
    *,
    time_range: str | None = None,
    symbol: str | None = None,
) -> bool:
    decoded_url = unquote(response_url)
    matches = (
        "webql-redesign.cnbcfm.com/graphql" in decoded_url
        and "operationName=getQuoteChartData" in decoded_url
    )
    if not matches:
        return False
    if time_range is not None and f'"timeRange":"{time_range}"' not in decoded_url:
        return False
    if symbol is not None and f'"symbol":"{symbol}"' not in decoded_url:
        return False
    return True


def _extract_chart_query_value(response_url: str, field: str) -> str | None:
    decoded_url = unquote(response_url)
    variables = parse_qs(urlparse(decoded_url).query).get("variables", [])
    if not variables:
        return None
    try:
        payload = json.loads(variables[0])
    except json.JSONDecodeError:
        return None
    value = payload.get(field)
    return str(value).upper() if isinstance(value, str) and value else None


async def _read_chart_payload(response, *, page, symbol: str, time_range: str | None) -> dict[str, object]:
    try:
        await response.finished()
        payload = await response.json()
    except PlaywrightError as exc:
        raise LensCaptureError(
            f"Could not read CNBC chart response body for {symbol}",
            stage="response_body",
            code="chart_response_body_unavailable",
            retryable=True,
            details={
                "symbol": symbol,
                "time_range": time_range or "initial",
                "page_url": page.url,
                "response_url": response.url,
                "response_status": str(response.status),
            },
        ) from exc
    if not isinstance(payload, dict):
        raise LensCaptureError(
            f"Unexpected CNBC chart payload type for {symbol}",
            stage="payload_parse",
            code="chart_payload_invalid",
            retryable=False,
            details={
                "symbol": symbol,
                "time_range": time_range or "initial",
                "page_url": page.url,
                "response_url": response.url,
                "response_status": str(response.status),
            },
        )
    return payload


class CNBCChartResponseCollector:
    def __init__(self, page, *, symbol: str) -> None:
        self.page = page
        self.symbol = symbol
        self._payloads: dict[str, dict[str, object]] = {}
        self._range_waiters: dict[str, list[asyncio.Future[dict[str, object]]]] = {}
        self._any_waiters: list[asyncio.Future[dict[str, object]]] = []
        self._tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        self.page.on("response", self._handle_response)

    async def stop(self) -> None:
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

    def _handle_response(self, response) -> None:
        if not _is_chart_response(response.url, symbol=self.symbol):
            return
        task = asyncio.create_task(self._capture_response(response))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _capture_response(self, response) -> None:
        requested_time_range = _extract_chart_query_value(response.url, "timeRange")
        try:
            payload = await _read_chart_payload(
                response,
                page=self.page,
                symbol=self.symbol,
                time_range=requested_time_range,
            )
        except LensCaptureError as exc:
            if requested_time_range is not None:
                self._resolve_range_exception(requested_time_range, exc)
            self._resolve_any_exception(exc)
            return

        chart_data = _extract_chart_data(payload)
        if chart_data is None:
            exc = LensCaptureError(
                f"CNBC chartData payload missing for {self.symbol}",
                stage="payload_parse",
                code="chart_payload_missing",
                retryable=False,
                details={
                    "symbol": self.symbol,
                    "time_range": requested_time_range or "initial",
                    "page_url": self.page.url,
                    "response_url": response.url,
                    "response_status": str(response.status),
                },
            )
            if requested_time_range is not None:
                self._resolve_range_exception(requested_time_range, exc)
            self._resolve_any_exception(exc)
            return

        actual_time_range = _extract_chart_time_range(payload) or requested_time_range or "INITIAL"
        self._payloads[actual_time_range] = payload
        self._resolve_range_payload(actual_time_range, payload)
        if requested_time_range is not None and requested_time_range != actual_time_range:
            self._resolve_range_payload(requested_time_range, payload)
        self._resolve_any_payload(payload)

    def _resolve_range_payload(self, time_range: str, payload: dict[str, object]) -> None:
        for future in self._range_waiters.pop(time_range, []):
            if not future.done():
                future.set_result(payload)

    def _resolve_range_exception(self, time_range: str, exc: Exception) -> None:
        for future in self._range_waiters.pop(time_range, []):
            if not future.done():
                future.set_exception(exc)

    def _resolve_any_payload(self, payload: dict[str, object]) -> None:
        while self._any_waiters:
            future = self._any_waiters.pop(0)
            if not future.done():
                future.set_result(payload)

    def _resolve_any_exception(self, exc: Exception) -> None:
        while self._any_waiters:
            future = self._any_waiters.pop(0)
            if not future.done():
                future.set_exception(exc)

    async def wait_for_any(self, trigger, *, timeout_ms: int) -> dict[str, object]:
        if self._payloads:
            return next(iter(self._payloads.values()))
        future: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
        self._any_waiters.append(future)
        await trigger()
        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError as exc:
            if not future.done():
                future.cancel()
            raise LensCaptureError(
                f"Timed out waiting for any CNBC chart data for {self.symbol}",
                stage="response_wait",
                code="chart_response_timeout",
                retryable=True,
                details={
                    "symbol": self.symbol,
                    "page_url": self.page.url,
                },
            ) from exc

    async def wait_for_range(self, trigger, time_range: str, *, timeout_ms: int) -> dict[str, object]:
        if time_range in self._payloads:
            return self._payloads[time_range]
        future: asyncio.Future[dict[str, object]] = asyncio.get_running_loop().create_future()
        self._range_waiters.setdefault(time_range, []).append(future)
        await trigger()
        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError as exc:
            waiters = self._range_waiters.get(time_range, [])
            self._range_waiters[time_range] = [item for item in waiters if item is not future]
            if not self._range_waiters[time_range]:
                self._range_waiters.pop(time_range, None)
            if not future.done():
                future.cancel()
            raise LensCaptureError(
                f"Timed out waiting for CNBC {time_range} chart data",
                stage="response_wait",
                code="chart_response_timeout",
                retryable=True,
                details={
                    "time_range": time_range,
                    "page_url": self.page.url,
                },
            ) from exc


async def _dismiss_consent_overlay(page) -> None:
    accept_targets = [
        page.locator("#onetrust-accept-btn-handler"),
        page.locator("#accept-recommended-btn-handler"),
        page.get_by_role("button", name="Accept").first,
        page.get_by_role("button", name="I Accept").first,
    ]
    for target in accept_targets:
        try:
            if await target.count() > 0 and await target.first.is_visible():
                await target.first.click(timeout=5_000)
                return
        except PlaywrightTimeoutError:
            continue

    overlay = page.locator("#onetrust-consent-sdk")
    try:
        if await overlay.count() > 0 and await overlay.first.is_visible():
            await page.evaluate(
                """
                const overlay = document.getElementById("onetrust-consent-sdk");
                if (overlay) {
                  overlay.remove();
                }
                """
            )
    except PlaywrightTimeoutError:
        return


async def _wait_for_chart_shell(page) -> None:
    await page.wait_for_load_state("load")
    try:
        await page.wait_for_load_state("networkidle", timeout=5_000)
    except PlaywrightTimeoutError:
        pass

    chart_shell_targets = [
        page.locator(".ShowRange-showRange").first,
        page.locator("cq-show-range").first,
        page.locator(".range-1today").first,
        page.locator(".range-5day").first,
    ]
    for target in chart_shell_targets:
        try:
            await target.wait_for(state="visible", timeout=10_000)
            return
        except PlaywrightTimeoutError:
            continue

    raise LensCaptureError(
        "CNBC chart controls did not become visible",
        stage="page_ready",
        code="chart_controls_not_visible",
        retryable=True,
        details={
            "page_url": page.url,
        },
    )


async def _click_time_range(page, time_range: str) -> None:
    selector = CNBC_TIME_RANGE_SELECTORS.get(time_range.upper())
    if selector:
        target = page.locator(selector).first
        if await target.count() > 0:
            try:
                await target.click()
            except PlaywrightTimeoutError:
                await _dismiss_consent_overlay(page)
                await target.click(force=True)
            return

    button = page.get_by_role("button", name=time_range).first
    if await button.count() > 0:
        try:
            await button.click()
        except PlaywrightTimeoutError:
            await _dismiss_consent_overlay(page)
            await button.click(force=True)
        return
    text_target = page.get_by_text(time_range, exact=True).first
    if await text_target.count() > 0:
        try:
            await text_target.click()
        except PlaywrightTimeoutError:
            await _dismiss_consent_overlay(page)
            await text_target.click(force=True)
        return
    raise LensCaptureError(
        f"Could not find CNBC time range control {time_range}",
        stage="time_range_select",
        code="time_range_control_missing",
        retryable=False,
        details={
            "time_range": time_range,
            "page_url": page.url,
        },
    )


async def capture_cnbc_chart_data(symbol: str) -> LensResult:
    normalized_symbol = symbol.strip().upper()
    url = f"https://www.cnbc.com/quotes/{normalized_symbol}"
    artifact_dir, trace_path, failure_screenshot_path = _build_artifact_paths(normalized_symbol)

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        context = await browser.new_context(
            user_agent=REALISTIC_USER_AGENT,
            locale="en-US",
            timezone_id="Europe/Warsaw",
            color_scheme="dark",
            viewport={"width": 1440, "height": 900},
            screen={"width": 1440, "height": 900},
            device_scale_factor=1,
            extra_http_headers={
                "Accept-Language": REALISTIC_ACCEPT_LANGUAGE,
            },
        )
        await context.add_init_script(STEALTH_INIT_SCRIPT)
        await context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = await context.new_page()
        collector = CNBCChartResponseCollector(page, symbol=normalized_symbol)
        collector.start()
        try:
            chart_ranges: dict[str, dict[str, object]] = {}
            initial_payload = await collector.wait_for_any(
                lambda: page.goto(url, wait_until="load"),
                timeout_ms=20000,
            )
            initial_time_range = _extract_chart_time_range(initial_payload) or "INITIAL"
            chart_ranges[initial_time_range] = initial_payload
            await _dismiss_consent_overlay(page)
            await _wait_for_chart_shell(page)
            for time_range in CNBC_CAPTURE_TIME_RANGES:
                if time_range in chart_ranges:
                    continue
                chart_ranges[time_range] = await collector.wait_for_range(
                    lambda current=time_range: _click_time_range(page, current),
                    time_range,
                    timeout_ms=15000,
                )
            page_title = await page.title()
        except LensCaptureError as exc:
            try:
                await page.screenshot(path=str(failure_screenshot_path), full_page=True)
                exc.details["failure_screenshot_path"] = str(failure_screenshot_path)
            except Exception:
                pass
            exc.details["trace_path"] = str(trace_path)
            exc.details["artifact_dir"] = str(artifact_dir)
            raise
        except PlaywrightTimeoutError as exc:
            lens_error = LensCaptureError(
                f"Timed out waiting for CNBC chart data interception for {normalized_symbol}",
                stage="page_navigation",
                code="page_timeout",
                retryable=True,
                details={
                    "symbol": normalized_symbol,
                    "page_url": page.url,
                },
            )
            try:
                await page.screenshot(path=str(failure_screenshot_path), full_page=True)
                lens_error.details["failure_screenshot_path"] = str(failure_screenshot_path)
            except Exception:
                pass
            lens_error.details["trace_path"] = str(trace_path)
            lens_error.details["artifact_dir"] = str(artifact_dir)
            raise lens_error from exc
        finally:
            await collector.stop()
            await context.tracing.stop(path=str(trace_path))
            await context.close()
            await browser.close()

    document = {
        "symbol": normalized_symbol,
        "source": "cnbc",
        "url": url,
        "page_title": page_title,
        "ranges": chart_ranges,
    }
    return LensResult(
        source="cnbc",
        url=url,
        symbol=normalized_symbol,
        data_type="quote_chart_data_multi_range",
        page_title=page_title,
        document=document,
        raw_text=json.dumps(document),
        observations=_build_chart_observations(document),
        screenshots=[str(trace_path)],
        warnings=[
            "Browser-intercepted chart data may be delayed.",
            "This data must not be used as execution-grade market data.",
            f"Playwright trace saved at {trace_path}",
        ],
    )
