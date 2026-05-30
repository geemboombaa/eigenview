"""Pure-function tests for the activation engine (forward + lookback modes).

score_activation is a pure transform over a daily series; these exercise each
branch with explicit computed inputs (same pattern as test_dormant_scoring).
"""
from __future__ import annotations

from datetime import date, timedelta

from eigenview.factors.activation import score_activation
from eigenview.factors.dormant import _group_chain_snapshots, _merge_series


def _h(d: date, oi: int, vol: int, iv: float = 0.30) -> dict:
    return {"date": d, "oi": oi, "volume": vol, "close": None, "iv": iv}


def _series(start: date, points: list[tuple[int, int]]) -> list[dict]:
    return [_h(start + timedelta(days=i), oi, vol) for i, (oi, vol) in enumerate(points)]


def test_forward_mode_fires_on_oi_and_volume_spike():
    # 3 points: flat baseline then an OI jump (+40%, +4000) and a volume burst.
    start = date(2026, 5, 1)
    hist = _series(start, [(10_000, 40), (10_000, 50), (14_000, 2_000)])
    res = score_activation(hist, [], "C", start + timedelta(days=2))
    assert res.fired is True
    assert res.detail.get("mode") == "forward"
    assert "oi_jump" in res.triggers and "volume_surge" in res.triggers


def test_single_point_cannot_score():
    start = date(2026, 5, 1)
    res = score_activation([_h(start, 10_000, 40)], [], "C", start)
    assert res.fired is False
    assert res.detail.get("reason") == "insufficient_history"


def test_flat_series_does_not_fire():
    start = date(2026, 5, 1)
    hist = _series(start, [(10_000, 40), (10_050, 42), (10_020, 41)])
    res = score_activation(hist, [], "C", start + timedelta(days=2))
    assert res.fired is False


def test_long_series_uses_lookback_mode():
    start = date(2026, 4, 1)
    # 40 flat baseline days, then a recent OI + volume spike.
    pts = [(10_000, 40) for _ in range(35)] + [(15_000, 3_000) for _ in range(5)]
    hist = _series(start, pts)
    res = score_activation(hist, [], "C", start + timedelta(days=len(pts) - 1))
    assert res.detail.get("mode") == "lookback"
    assert res.fired is True


def test_merge_series_history_wins_unions_and_sorts():
    snap = [
        {"date": date(2026, 5, 1), "oi": 100, "volume": 1, "close": None, "iv": 0.2},
        {"date": date(2026, 5, 3), "oi": 300, "volume": 3, "close": None, "iv": 0.2},
    ]
    hist = [
        {"date": date(2026, 5, 1), "oi": 999, "volume": 9, "close": 1.0, "iv": 0.3},
        {"date": date(2026, 5, 2), "oi": 200, "volume": 2, "close": 1.0, "iv": 0.3},
    ]
    out = _merge_series(hist, snap)
    assert [r["date"].day for r in out] == [1, 2, 3]   # union, sorted
    assert out[0]["oi"] == 999                          # contract_history wins on 5/1


def test_group_chain_snapshots_keys_normalizes_and_sorts():
    exp = date(2026, 8, 21)
    rows = [
        (date(2026, 5, 3), 110.0, exp, "C", 300, 3, 0.2),
        (date(2026, 5, 1), 110.0, exp, "c", 100, 1, 0.2),  # same contract, lowercase cp
        (date(2026, 5, 1), 90.0, exp, "P", 50, 5, 0.4),
    ]
    g = _group_chain_snapshots(rows)
    k = (110.0, exp, "C")
    assert len(g[k]) == 2                                  # c and C collapse to one contract
    assert [r["date"].day for r in g[k]] == [1, 3]         # sorted by date
    assert (90.0, exp, "P") in g
