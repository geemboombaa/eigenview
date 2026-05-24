"""Integration test for the activation engine against real Databento history.

Real SQLite DB + real `contract_history` / `prices` rows (loaded by
scripts/run_activation.py from Databento OPRA). No mocks, no synthetic series.
Skips when no history is loaded (e.g. a fresh CI checkout — data/ is gitignored).
"""
from __future__ import annotations

import datetime as dt
import sqlite3
import statistics
from pathlib import Path

import pytest

from eigenview.config import settings
from eigenview.data.databento_history import osi_symbol
from eigenview.factors.activation import ActivationResult, score_activation

_DB = (
    Path(settings.database_url.split("///", 1)[1])
    if settings.database_url.startswith("sqlite") and "///" in settings.database_url
    else None
)


def _history_rows() -> int:
    if not _DB or not _DB.exists():
        return 0
    con = sqlite3.connect(_DB)
    try:
        return con.execute("SELECT COUNT(*) FROM contract_history").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        con.close()


pytestmark = pytest.mark.skipif(
    _history_rows() == 0, reason="contract_history not loaded (no Databento data)"
)


def _series(con: sqlite3.Connection, osi: str) -> list[dict]:
    rows = con.execute(
        "SELECT date, oi, volume, close, iv FROM contract_history "
        "WHERE osi_symbol=? ORDER BY date", (osi,)
    ).fetchall()
    return [
        {"date": dt.date.fromisoformat(d), "oi": oi, "volume": v, "close": c, "iv": iv}
        for d, oi, v, c, iv in rows
    ]


def test_osi_symbol_format():
    """OSI is deterministic string formatting (real computed value, no I/O)."""
    assert osi_symbol("AAPL", dt.date(2027, 1, 15), "C", 300) == "AAPL  270115C00300000"
    assert osi_symbol("MU", dt.date(2026, 11, 20), "P", 910) == "MU    261120P00910000"


def test_activation_returns_valid_result_on_real_series():
    con = sqlite3.connect(_DB)
    try:
        osi = con.execute("SELECT osi_symbol FROM contract_history LIMIT 1").fetchone()[0]
        series = _series(con, osi)
    finally:
        con.close()
    target = max(r["date"] for r in series)
    res = score_activation(series, [], osi[12], target)
    assert isinstance(res, ActivationResult)
    assert isinstance(res.triggers, list)
    assert 0.0 <= res.strength <= 1.0


def test_real_oi_ramp_fires_oi_jump():
    """A contract whose OI genuinely ramped (current >> dormant baseline) must trip oi_jump."""
    con = sqlite3.connect(_DB)
    try:
        osis = [r[0] for r in con.execute(
            "SELECT osi_symbol FROM contract_history GROUP BY osi_symbol "
            "HAVING COUNT(*) > 30 AND MAX(oi) > 2000"
        ).fetchall()]
        fired = False
        for osi in osis:
            series = _series(con, osi)
            ois = [r["oi"] for r in series if r["oi"]]
            if len(ois) < 30:
                continue
            base = statistics.median(ois[: int(len(ois) * 0.8)])
            if base and ois[-1] >= 2 * base and ois[-1] - base >= 1000:
                res = score_activation(series, [], osi[12], max(r["date"] for r in series))
                if "oi_jump" in res.triggers:
                    fired = True
                    break
    finally:
        con.close()
    assert fired, "expected >=1 real OI-ramp contract to fire oi_jump"
