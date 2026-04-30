from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pytest

from eigenview.factors.gex import score_gex


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


SPOT = 600.0


def _make_call(strike: float, gamma: float, oi: int = 1000) -> MockChain:
    return MockChain(strike=strike, call_put="C", volume=100, oi=oi, iv=0.3, delta=0.5, gamma=gamma, bid=5.0, ask=5.2)


def _make_put(strike: float, gamma: float, oi: int = 1000) -> MockChain:
    return MockChain(strike=strike, call_put="P", volume=100, oi=oi, iv=0.3, delta=-0.5, gamma=gamma, bid=5.0, ask=5.2)


def test_short_gamma_fires():
    # puts far below spot, calls far above → gamma flip ~796, far from spot 600
    chains = [
        _make_call(800, gamma=0.001, oi=500),
        _make_put(400, gamma=0.01, oi=5000),
    ]
    result = score_gex(chains, SPOT)
    assert result.firing is True
    assert result.label == "short_gamma"
    assert result.detail["net_gex"] < 0


def test_long_gamma_no_fire():
    # calls far above, puts far below → gamma flip ~404, far from spot 600
    chains = [
        _make_call(800, gamma=0.01, oi=5000),
        _make_put(400, gamma=0.001, oi=500),
    ]
    result = score_gex(chains, SPOT)
    assert result.firing is False
    assert result.label == "long_gamma"
    assert result.detail["net_gex"] > 0


def test_call_wall_put_wall_detected():
    chains = [
        _make_call(620, gamma=0.005, oi=2000),
        _make_call(650, gamma=0.005, oi=5000),   # highest call OI above spot → call wall
        _make_put(580, gamma=0.005, oi=3000),     # highest put OI below spot → put wall
        _make_put(550, gamma=0.005, oi=1000),
    ]
    result = score_gex(chains, SPOT)
    assert result.detail["call_wall"] == 650.0
    assert result.detail["put_wall"] == 580.0


def test_no_data():
    result = score_gex([], SPOT)
    assert result.firing is False
    assert result.label == "NO DATA"
    assert result.factor_id == "gex"


def test_flip_zone():
    # Build chains where gamma flip ends up very close to spot (within 5%)
    # net_gex is slightly positive for strikes below spot and negative above
    # so gamma_flip ≈ spot
    chains = [
        # call at spot-5 with large positive contribution
        _make_call(595, gamma=0.005, oi=4000),
        # put at spot+5 with large negative contribution so flip is right near spot
        _make_put(605, gamma=0.005, oi=4000),
    ]
    result = score_gex(chains, SPOT)
    assert result.firing is True
    assert result.label in ("flip_zone", "short_gamma")
