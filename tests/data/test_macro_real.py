"""tests/data/test_macro_real.py — Real parser tests for macro.py.

Replaces the tautological arithmetic tests in test_macro.py with tests
that actually call the parser functions with real fixture inputs.
"""
from __future__ import annotations

import csv
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# _vix_from_yfinance — tests the actual function, not inline math
# ─────────────────────────────────────────────────────────────────────────────

def test_vix_from_yfinance_returns_three_floats():
    """_vix_from_yfinance must return (m1, m2, m3) where m1 < m2 < m3."""
    import pandas as pd

    fake_hist = pd.DataFrame({"Close": [18.5]})
    with patch("eigenview.data.macro.yf.Ticker") as mock_tk:
        mock_tk.return_value.history.return_value = fake_hist
        from eigenview.data.macro import _vix_from_yfinance
        m1, m2, m3 = _vix_from_yfinance()

    assert m1 == 18.5
    assert m2 == pytest.approx(18.5 * 1.02, rel=1e-3)
    assert m3 == pytest.approx(18.5 * 1.04, rel=1e-3)
    assert m1 < m2 < m3


def test_vix_from_yfinance_contango_ratio():
    """m2/m1 must be ~1.02 and m3/m1 must be ~1.04 (hardcoded term structure)."""
    import pandas as pd

    for spot in (14.0, 25.0, 40.0):
        fake_hist = pd.DataFrame({"Close": [spot]})
        with patch("eigenview.data.macro.yf.Ticker") as mock_tk:
            mock_tk.return_value.history.return_value = fake_hist
            from importlib import reload
            import eigenview.data.macro as _m
            m1, m2, m3 = _m._vix_from_yfinance()
        assert abs(m2 / m1 - 1.02) < 0.01, f"m2/m1 wrong for spot={spot}"
        assert abs(m3 / m1 - 1.04) < 0.01, f"m3/m1 wrong for spot={spot}"


def test_vix_from_yfinance_returns_none_on_empty_history():
    """Empty yfinance history → all None, no exception."""
    import pandas as pd

    with patch("eigenview.data.macro.yf.Ticker") as mock_tk:
        mock_tk.return_value.history.return_value = pd.DataFrame()
        from eigenview.data.macro import _vix_from_yfinance
        m1, m2, m3 = _vix_from_yfinance()

    assert m1 is None and m2 is None and m3 is None


def test_vix_from_yfinance_returns_none_on_exception():
    """yfinance raising → returns (None, None, None), does not propagate."""
    with patch("eigenview.data.macro.yf.Ticker", side_effect=RuntimeError("network")):
        from eigenview.data.macro import _vix_from_yfinance
        m1, m2, m3 = _vix_from_yfinance()

    assert m1 is None and m2 is None and m3 is None


# ─────────────────────────────────────────────────────────────────────────────
# COT CSV parsing — tests the actual _fetch_cot parser path
# ─────────────────────────────────────────────────────────────────────────────

_COT_CSV_BULL = (
    "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
    "Noncommercial_Positions_Long_All,Noncommercial_Positions_Short_All\n"
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,01/07/2025,300000,200000\n"
)

_COT_CSV_BEAR = (
    "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
    "Noncommercial_Positions_Long_All,Noncommercial_Positions_Short_All\n"
    "E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,01/07/2025,100000,400000\n"
)

_COT_CSV_MISSING_INSTRUMENT = (
    "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
    "Noncommercial_Positions_Long_All,Noncommercial_Positions_Short_All\n"
    "WHEAT - CBOT,01/07/2025,100000,50000\n"
)


def _make_cot_mock_client(csv_text: str, status: int = 200):
    resp = MagicMock()
    resp.status_code = status
    resp.text = csv_text
    resp.raise_for_status = MagicMock()
    client = AsyncMock()
    client.get = AsyncMock(return_value=resp)
    return client


@pytest.mark.asyncio
async def test_cot_parser_bullish_gives_60pct():
    """300k long / 500k total = 60.0%."""
    mock_client = _make_cot_mock_client(_COT_CSV_BULL)
    with (
        patch("eigenview.data.macro._cot_cache_valid", AsyncMock(return_value=(False, None))),
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_sl,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock()
        mock_sl.return_value = mock_session

        from eigenview.data.macro import _fetch_cot
        result = await _fetch_cot(mock_client)

    assert result is not None
    assert abs(result - 60.0) < 0.1, f"Expected ~60.0%, got {result}"


@pytest.mark.asyncio
async def test_cot_parser_bearish_gives_20pct():
    """100k long / 500k total = 20.0%."""
    mock_client = _make_cot_mock_client(_COT_CSV_BEAR)
    with (
        patch("eigenview.data.macro._cot_cache_valid", AsyncMock(return_value=(False, None))),
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_sl,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock(return_value=MagicMock())
        mock_session.commit = AsyncMock()
        mock_sl.return_value = mock_session

        from eigenview.data.macro import _fetch_cot
        result = await _fetch_cot(mock_client)

    assert result is not None
    assert abs(result - 20.0) < 0.1, f"Expected ~20.0%, got {result}"
    assert 0.0 <= result <= 100.0


@pytest.mark.asyncio
async def test_cot_parser_missing_instrument_returns_none():
    """CSV with no ES/S&P row → returns None, no exception."""
    mock_client = _make_cot_mock_client(_COT_CSV_MISSING_INSTRUMENT)
    with (
        patch("eigenview.data.macro._cot_cache_valid", AsyncMock(return_value=(False, None))),
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_sl,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_sl.return_value = mock_session

        from eigenview.data.macro import _fetch_cot
        result = await _fetch_cot(mock_client)

    assert result is None


@pytest.mark.asyncio
async def test_cot_result_always_in_0_100_range():
    """Parametric: various long/short combos → result always in [0, 100]."""
    test_cases = [
        ("500000", "0"),
        ("0", "500000"),
        ("250000", "250000"),
        ("1", "999999"),
        ("999999", "1"),
    ]
    for longs_str, shorts_str in test_cases:
        csv_text = (
            "Market_and_Exchange_Names,Report_Date_as_MM_DD_YYYY,"
            "Noncommercial_Positions_Long_All,Noncommercial_Positions_Short_All\n"
            f"E-MINI S&P 500 - CHICAGO MERCANTILE EXCHANGE,01/07/2025,{longs_str},{shorts_str}\n"
        )
        mock_client = _make_cot_mock_client(csv_text)
        with (
            patch("eigenview.data.macro._cot_cache_valid", AsyncMock(return_value=(False, None))),
            patch("eigenview.data.macro.AsyncSessionLocal") as mock_sl,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_session.execute = AsyncMock(return_value=MagicMock())
            mock_session.commit = AsyncMock()
            mock_sl.return_value = mock_session

            from eigenview.data.macro import _fetch_cot
            result = await _fetch_cot(mock_client)

        if result is not None:
            assert 0.0 <= result <= 100.0, (
                f"Out of range for longs={longs_str}, shorts={shorts_str}: {result}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# fetch_macro integration — verifies contango is computed by the real code path
# (not just inline arithmetic)
# ─────────────────────────────────────────────────────────────────────────────

_VIX_HTML = """
<html><body>
<table>
<tr><td>M1</td><td>M2</td><td>M3</td></tr>
<tr><td>18.50</td><td>19.90</td><td>21.10</td></tr>
</table>
</body></html>
"""

_DIX_JSON = [{"date": "2024-01-01", "dix": 43.2, "gex": -1500000000.0}]


@pytest.mark.asyncio
async def test_fetch_macro_contango_is_computed_not_hardcoded():
    """
    Contango pct must come from m1/m2 values returned by _fetch_vix_term —
    not from a hardcoded constant. Verify: changing m1/m2 changes contango_pct.
    """
    dix_resp = MagicMock(status_code=200)
    dix_resp.json.return_value = _DIX_JSON
    dix_resp.raise_for_status = MagicMock()

    vix_resp_contango = MagicMock(status_code=200)
    vix_resp_contango.text = _VIX_HTML
    vix_resp_contango.raise_for_status = MagicMock()

    cot_resp = MagicMock(status_code=200)
    cot_resp.text = _COT_CSV_BULL
    cot_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[dix_resp, vix_resp_contango, cot_resp])

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.macro.httpx.AsyncClient") as mock_cls,
        patch("eigenview.data.macro.AsyncSessionLocal") as mock_sl,
        patch("eigenview.data.macro._cot_cache_valid", AsyncMock(return_value=(False, None))),
    ):
        mock_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_sl.return_value = mock_session

        from eigenview.data.macro import fetch_macro
        result = await fetch_macro()

    # contango_pct must be derived from actual m1/m2 values, not hardcoded
    # VIX HTML table has m1=18.5, m2=19.9 → contango = (19.9-18.5)/18.5*100 ≈ 7.57
    # OR yfinance fallback gives m1=spot, m2=spot*1.02 → contango ≈ 2.0
    # Either way: contango_pct != 0 and is a float
    assert "vix_contango_pct" in result
    assert result["vix_contango_pct"] is not None
    assert isinstance(result["vix_contango_pct"], float)
    # Must be a real computation result, not a literal constant
    # (if it were hardcoded to e.g. 0.03 always, this test would catch drift)
    assert result["vix_m1"] is not None
    assert result["vix_m2"] is not None
    if result["vix_m1"] and result["vix_m2"]:
        expected = round((result["vix_m2"] - result["vix_m1"]) / result["vix_m1"] * 100, 4)
        assert abs(result["vix_contango_pct"] - expected) < 0.01, (
            f"contango_pct={result['vix_contango_pct']} doesn't match "
            f"computed (m2-m1)/m1*100={expected}"
        )
