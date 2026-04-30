from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pytest

from eigenview.factors.flow import score_flow


@dataclass
class MockChain:
    strike: float
    call_put: str
    volume: int
    oi: int
    iv: float
    delta: float
    gamma: float
    bid: float
    ask: float
    snapshot_date: date = field(default_factory=date.today)
    expiry: date = field(default_factory=date.today)


def _call(bid: float, ask: float, volume: int, oi: int, strike: float = 600.0) -> MockChain:
    return MockChain(strike=strike, call_put="C", volume=volume, oi=oi, iv=0.3, delta=0.5, gamma=0.001, bid=bid, ask=ask)


def _put(bid: float, ask: float, volume: int, oi: int, strike: float = 580.0) -> MockChain:
    return MockChain(strike=strike, call_put="P", volume=volume, oi=oi, iv=0.3, delta=-0.5, gamma=0.001, bid=bid, ask=ask)


def test_large_call_sweep_fires():
    # mid=5.0, volume=1600, oi=400 → premium=5*1600*100=800_000, voi=4.0
    chain = _call(bid=4.9, ask=5.1, volume=1600, oi=400)
    result = score_flow([chain])
    assert result.firing is True
    assert result.detail["dominant_side"] == "calls"
    assert result.detail["total_qualified"] == 1


def test_put_sweep_fires():
    # mid=5.0, volume=1200, oi=240 → premium=600_000, voi=5.0
    chain = _put(bid=4.9, ask=5.1, volume=1200, oi=240)
    result = score_flow([chain])
    assert result.firing is True
    assert result.detail["dominant_side"] == "puts"


def test_below_threshold_no_fire():
    # mid=2.0, volume=500, oi=100 → premium=100_000 < 500_000
    chain = _call(bid=1.9, ask=2.1, volume=500, oi=100)
    result = score_flow([chain])
    assert result.firing is False


def test_low_voi_no_fire():
    # mid=10.0, volume=500, oi=1000 → premium=500_000 but voi=0.5 < 3.0
    chain = _call(bid=9.9, ask=10.1, volume=500, oi=1000)
    result = score_flow([chain])
    assert result.firing is False


def test_no_data():
    result = score_flow([])
    assert result.firing is False
    assert result.label == "NO DATA"
    assert result.factor_id == "flow"
