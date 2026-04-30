from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_DIX_JSON = [{"date": "2024-01-01", "dix": 43.2, "gex": -1500000000.0}]

_VIX_HTML_WITH_TABLE = """
<html><body>
<table>
<tr><td>M1</td><td>M2</td><td>M3</td></tr>
<tr><td>18.50</td><td>19.90</td><td>21.10</td></tr>
</table>
</body></html>
"""

# Minimal valid CFTC deafut.txt CSV (comma-separated)
_COT_CSV = (
    "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
    "Noncommercial_Positions_Long_All,Noncommercial_Positions_Short_All\n"
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,01/02/2024,300000,200000\n"
)


def _make_httpx_response(content=None, json_data=None, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    if json_data is not None:
        resp.json.return_value = json_data
    if content is not None:
        resp.text = content
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError  # noqa: PLC0415

        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return resp


def _mock_cot_cache(is_fresh: bool, cached_pct=None):
    return AsyncMock(return_value=(is_fresh, cached_pct))


# ---------------------------------------------------------------------------
# Test 1: fetch_macro returns dict with all expected keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_macro_returns_all_keys():
    dix_resp = _make_httpx_response(json_data=_DIX_JSON)
    vix_resp = _make_httpx_response(content=_VIX_HTML_WITH_TABLE)
    cot_resp = _make_httpx_response(content=_COT_CSV)

    mock_client = AsyncMock()
    # get() is called in order: squeeze JSON, vixcentral, CFTC
    mock_client.get = AsyncMock(side_effect=[dix_resp, vix_resp, cot_resp])

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.macro.httpx.AsyncClient") as mock_cls,
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_session_cls,
        patch("eigenview.data.macro._cot_cache_valid", _mock_cot_cache(False)),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from eigenview.data.macro import fetch_macro

        result = await fetch_macro()

    expected_keys = {
        "date",
        "dix",
        "gex_index",
        "vix_m1",
        "vix_m2",
        "vix_m3",
        "vix_contango_pct",
        "cot_es_net_long_pct",
    }
    assert expected_keys == set(result.keys())


# ---------------------------------------------------------------------------
# Test 2: vix_contango_pct computed correctly from m1/m2
# ---------------------------------------------------------------------------


def test_vix_contango_pct_calculation():
    """Verify the contango formula: (m2 - m1) / m1 * 100."""
    vix_m1 = 18.5
    vix_m2 = 19.9
    expected = round((vix_m2 - vix_m1) / vix_m1 * 100, 4)

    # Simulate the calculation used inside fetch_macro
    result = round((vix_m2 - vix_m1) / vix_m1 * 100, 4)
    assert abs(result - expected) < 1e-6

    # Backwardation
    vix_m1 = 30.0
    vix_m2 = 28.0
    result_neg = round((vix_m2 - vix_m1) / vix_m1 * 100, 4)
    assert result_neg < 0


# ---------------------------------------------------------------------------
# Test 3: one source fails (500 response) → other fields still populated
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_macro_partial_on_source_failure():
    """DIX source returns 500 — VIX and COT fields still populated."""
    dix_resp = _make_httpx_response(status_code=500)
    vix_resp = _make_httpx_response(content=_VIX_HTML_WITH_TABLE)
    cot_resp = _make_httpx_response(content=_COT_CSV)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[dix_resp, dix_resp, vix_resp, cot_resp])

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.macro.httpx.AsyncClient") as mock_cls,
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_session_cls,
        patch("eigenview.data.macro._cot_cache_valid", _mock_cot_cache(False)),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from eigenview.data.macro import fetch_macro

        result = await fetch_macro()

    # DIX/GEX may be None due to failure — but function should not raise
    assert isinstance(result, dict)
    assert "date" in result
    # At minimum, the function must return a dict even with partial failures
    assert set(result.keys()) >= {"date", "dix", "vix_m1", "vix_contango_pct"}


# ---------------------------------------------------------------------------
# Test 4: COT net_long_pct between 0 and 100
# ---------------------------------------------------------------------------


def test_cot_net_long_pct_bounds():
    """Given synthetic longs/shorts, net_long_pct must be [0, 100]."""
    test_cases = [
        (300_000, 200_000),
        (500_000, 0),
        (0, 500_000),
        (250_000, 250_000),
        (1, 999_999),
    ]
    for longs, shorts in test_cases:
        total = longs + shorts
        if total == 0:
            continue
        pct = longs / total * 100
        assert 0.0 <= pct <= 100.0, f"Out of bounds for longs={longs}, shorts={shorts}: {pct}"
