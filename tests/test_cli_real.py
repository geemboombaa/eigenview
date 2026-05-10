"""tests/test_cli_real.py — Real subprocess CLI tests. No mocks. Real DB.

Supplements the mocked tests in test_cli.py with real execution proof.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

_ROOT = pathlib.Path(__file__).parents[1]
_EXE = str(_ROOT / ".venv" / "Scripts" / "eigenview.exe")


def _run(*args, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        [_EXE, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(_ROOT),
    )


# ─────────────────────────────────────────────────────────────────────────────
# status — fast, no network, real DB
# ─────────────────────────────────────────────────────────────────────────────

def test_status_exits_zero():
    r = _run("status")
    assert r.returncode == 0, f"stderr: {r.stderr[:500]}"


def test_status_lists_all_expected_tables():
    r = _run("status")
    for table in ("prices", "chains", "news", "catalysts", "picks"):
        assert table in r.stdout, f"Table '{table}' missing from status output"


def test_status_prices_row_count_nonzero():
    """DB has real OHLCV — prices must have actual rows."""
    r = _run("status")
    for line in r.stdout.splitlines():
        if "prices" in line:
            nums = re.findall(r"\d+", line)
            assert nums and int(nums[0]) > 0, (
                f"prices row count zero or missing. Line: {line}"
            )
            return
    pytest.fail("No 'prices' line found in status output")


def test_status_chains_row_count_nonzero():
    r = _run("status")
    for line in r.stdout.splitlines():
        if "chains" in line:
            nums = re.findall(r"\d+", line)
            assert nums and int(nums[0]) > 0, (
                f"chains row count zero or missing. Line: {line}"
            )
            return
    pytest.fail("No 'chains' line found in status output")


# ─────────────────────────────────────────────────────────────────────────────
# daily-scan — real network + real DB
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.data_dependent
def test_daily_scan_exits_zero():
    r = _run("daily-scan", "--tickers", "NVDA,AAPL,TSLA,META,AMD", timeout=240)
    assert r.returncode == 0, f"daily-scan failed:\nstdout: {r.stdout[:500]}\nstderr: {r.stderr[:500]}"


@pytest.mark.data_dependent
def test_daily_scan_produces_picks():
    r = _run("daily-scan", "--tickers", "NVDA,AAPL,TSLA,META,AMD", timeout=240)
    out = r.stdout
    assert re.search(r"\d+ pick", out, re.IGNORECASE) or "conviction" in out.lower(), (
        f"No picks found in output.\nstdout: {out[:800]}"
    )


@pytest.mark.data_dependent
def test_daily_scan_conviction_in_valid_range():
    """All conviction values in output must be 1–5."""
    r = _run("daily-scan", "--tickers", "NVDA,AAPL,TSLA,META,AMD", timeout=240)
    convictions = re.findall(r"conviction\s+(\d)/5", r.stdout, re.IGNORECASE)
    assert convictions, f"No conviction/5 pattern found.\nstdout: {r.stdout[:500]}"
    for val in convictions:
        assert 1 <= int(val) <= 5, f"conviction={val} out of range 1-5"


@pytest.mark.data_dependent
def test_daily_scan_entry_stop_relationship():
    """Each pick must have entry_low < entry_high and stop < entry_low."""
    r = _run("daily-scan", "--tickers", "NVDA,AAPL,TSLA,META,AMD", timeout=240)
    entries = re.findall(r"Entry:\s*\$([\d.]+)–\$([\d.]+)", r.stdout)
    stops = re.findall(r"Stop:\s*\$([\d.]+)", r.stdout)
    assert entries, "No Entry: lines found in output"
    for i, (lo, hi) in enumerate(entries):
        assert float(lo) < float(hi), f"entry_low >= entry_high: {lo} >= {hi}"
        if i < len(stops):
            assert float(stops[i]) < float(lo), (
                f"stop {stops[i]} >= entry_low {lo}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# populate-forward-returns — data_dependent
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.data_dependent
def test_populate_forward_returns_exits_zero():
    r = _run("populate-forward-returns", "--lookback-days", "7", timeout=60)
    assert r.returncode == 0, f"stderr: {r.stderr[:500]}"


@pytest.mark.data_dependent
def test_populate_forward_returns_reports_completion():
    r = _run("populate-forward-returns", "--lookback-days", "7", timeout=60)
    assert "Done" in r.stdout, f"'Done' not in output.\nstdout: {r.stdout}"
