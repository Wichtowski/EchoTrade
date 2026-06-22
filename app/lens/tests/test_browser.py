import pytest
from playwright.async_api import Error as PlaywrightError

from lens.browser import (
    CNBC_TIME_RANGE_SELECTORS,
    LensCaptureError,
    _build_chart_observations,
    _extract_chart_query_value,
    _read_chart_payload,
)


def test_build_chart_observations_counts_price_bars() -> None:
    observations = _build_chart_observations(
        {
            "symbol": "AMD",
            "ranges": {
                "1D": {"data": {"chartData": {"priceBars": [{"close": 1}, {"close": 2}, {"close": 3}]}}},
                "5D": {"data": {"chartData": {"priceBars": [{"close": 1}, {"close": 2}]}}},
            },
        }
    )

    as_dict = {item.label: item.value for item in observations}
    assert as_dict["symbol"] == "AMD"
    assert as_dict["1d_price_bar_count"] == "3"
    assert as_dict["5d_price_bar_count"] == "2"


def test_cnbc_time_range_selectors_cover_supported_capture_ranges() -> None:
    assert CNBC_TIME_RANGE_SELECTORS["1D"] == ".range-1today"
    assert CNBC_TIME_RANGE_SELECTORS["5D"] == ".range-5day"
    assert CNBC_TIME_RANGE_SELECTORS["1M"] == ".range-1month"
    assert CNBC_TIME_RANGE_SELECTORS["3M"] == ".range-3month"
    assert CNBC_TIME_RANGE_SELECTORS["6M"] == ".range-6month"


def test_extract_chart_query_value_reads_symbol_and_time_range() -> None:
    response_url = (
        'https://webql-redesign.cnbcfm.com/graphql?operationName=getQuoteChartData&'
        'variables={"symbol":"RHM-DE","timeRange":"1Y"}&'
        'extensions={"persistedQuery":{"version":1,"sha256Hash":"abc"}}'
    )

    assert _extract_chart_query_value(response_url, "symbol") == "RHM-DE"
    assert _extract_chart_query_value(response_url, "timeRange") == "1Y"


@pytest.mark.asyncio
async def test_read_chart_payload_wraps_missing_response_body() -> None:
    class FakeResponse:
        url = "https://webql-redesign.cnbcfm.com/graphql?operationName=getQuoteChartData"
        status = 200

        async def finished(self) -> None:
            return None

        async def json(self) -> dict[str, object]:
            raise PlaywrightError(
                "Response.json: Protocol error (Network.getResponseBody): "
                "No resource with given identifier found"
            )

    class FakePage:
        url = "https://www.cnbc.com/quotes/RHM-DE"

    with pytest.raises(LensCaptureError) as exc_info:
        await _read_chart_payload(
            FakeResponse(),
            page=FakePage(),
            symbol="RHM-DE",
            time_range="1D",
        )

    exc = exc_info.value
    assert exc.stage == "response_body"
    assert exc.code == "chart_response_body_unavailable"
    assert exc.retryable is True
    assert exc.details["symbol"] == "RHM-DE"
    assert exc.details["time_range"] == "1D"
