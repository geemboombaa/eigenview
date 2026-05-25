"""Real tests for the TA-scan scoring path (no network).

_score_one is pure given a price DataFrame — it calls score_technical. Driven
with real CSV fixtures (NVDA/SPY). The batch download / options paths need
yfinance and are exercised by the nightly integration run, not here.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eigenview.api.routes.ta_scan import TaScanRequest, _score_one

FIXTURES = Path(__file__).parent.parent / "fixtures"


def _load(name: str) -> pd.DataFrame:
    df = pd.read_csv(FIXTURES / name, index_col=0, parse_dates=True)
    df.index = df.index.tz_localize(None)
    return df


@pytest.fixture(scope="module")
def nvda():
    return _load("nvda_daily_2022_2024.csv")


def test_score_one_returns_full_row(nvda):
    row = _score_one("NVDA", nvda, lookback_bars=10, spy_ret=0.02)
    assert row["ticker"] == "NVDA"
    assert row["spot"] is not None
    assert isinstance(row["firing"], bool)
    for key in ("pattern", "confidence", "direction", "weekly_state", "trend", "rs_vs_spy"):
        assert key in row


def test_score_one_without_spy_ret_has_null_rs(nvda):
    row = _score_one("NVDA", nvda, lookback_bars=5, spy_ret=None)
    assert row["rs_vs_spy"] is None


def test_score_one_empty_df_hits_error_branch():
    row = _score_one("NVDA", pd.DataFrame(), lookback_bars=10, spy_ret=None)
    assert row["pattern"] == "ERROR"
    assert row["firing"] is False


def test_ta_scan_request_defaults():
    req = TaScanRequest()
    assert req.min_volume_m == 1.0
    assert req.fetch_options is True
    assert req.lookback_bars == 10
    assert req.tickers is None


def test_ta_scan_request_with_tickers():
    req = TaScanRequest(tickers=["NVDA", "AMD"], fetch_options=False)
    assert req.tickers == ["NVDA", "AMD"]
    assert req.fetch_options is False
