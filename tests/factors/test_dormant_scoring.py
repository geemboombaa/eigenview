"""Pure-function tests for dormant scoring (percentile-relative design).

dwoi / percentile_rank / percentile_value / candidate filter / bet_confidence
are pure transforms; these exercise each branch with explicit computed inputs.
bet_confidence is now a SOFT annotation only: static vertical/calendar "spread"
detection was removed (it fired on liquidity, not real spreads, from one EOD
snapshot). Only the whole-chain delta-balance flag remains, and its penalty stays
above the keep-floor — it never drops a contract, just marks dealer-style books.
"""
from __future__ import annotations

from datetime import date, timedelta
from datetime import date as _date

from eigenview.factors.dormant import (
    _ChainRow,
    bet_confidence,
    candidate_dwoi_floor,
    dwoi,
    is_dormant_candidate,
    percentile_rank,
    percentile_value,
)


def _row(strike, cp, oi, delta=None, iv=None, expiry=None, volume=None):
    return _ChainRow(strike=strike, call_put=cp, oi=oi, delta=delta, iv=iv,
                     expiry=expiry, volume=volume)


class TestPercentileRank:
    def test_top_value(self):
        assert percentile_rank(100, [1, 2, 3, 99]) == 1.0

    def test_bottom_value(self):
        assert percentile_rank(0, [1, 2, 3]) == 0.0

    def test_middle(self):
        assert percentile_rank(2, [1, 2, 3, 4]) == 0.25

    def test_empty(self):
        assert percentile_rank(5, []) == 0.0


class TestDwoi:
    def test_formula(self):
        assert dwoi(0.5, 1000, 100.0) == 0.5 * 1000 * 100 * 100.0

    def test_none_delta_zero(self):
        assert dwoi(None, 1000, 100.0) == 0.0


class TestBetConfidence:
    _E = _date.today() + timedelta(days=120)
    _E2 = _date.today() + timedelta(days=210)

    def test_isolated_naked_call_full_confidence(self):
        # One dominant call, small fillers, single expiry → directional book → no penalty.
        cand = _row(110.0, "C", 200_000, delta=0.35, expiry=self._E)
        chain = [cand] + [_row(100.0 + i, "C", 120, delta=0.30, expiry=self._E)
                          for i in range(40)]
        conf, d = bet_confidence(cand, chain, spot=100.0)
        assert conf == 1.0
        assert not d.get("chain_balanced")

    def test_vertical_no_longer_penalized(self):
        # A big same-side OI leg nearby is NOT a spread we can prove from one snapshot —
        # it's just a liquid call ladder. Regression guard: must stay full confidence.
        cand = _row(110.0, "C", 200_000, delta=0.35, expiry=self._E)
        chain = [cand,
                 _row(115.0, "C", 150_000, delta=0.25, expiry=self._E),
                 _row(105.0, "C", 100, delta=0.45, expiry=self._E)]
        conf, d = bet_confidence(cand, chain, spot=100.0)
        assert conf == 1.0
        assert "vertical" not in d

    def test_calendar_no_longer_penalized(self):
        # Same strike, different expiry, big OI = independent LEAP holders, not a calendar.
        cand = _row(110.0, "C", 200_000, delta=0.35, expiry=self._E)
        chain = [cand, _row(110.0, "C", 150_000, delta=0.30, expiry=self._E2)]
        conf, d = bet_confidence(cand, chain, spot=100.0)
        assert conf == 1.0
        assert "calendar" not in d

    def test_balanced_book_soft_flag_never_drops(self):
        # Candidate call mirrored by an equal-dollar-delta put → whole chain nets ~0.
        # Flagged, but penalty 0.7 stays above the 0.40 keep-floor: never dropped.
        cand = _row(100.0, "C", 50_000, delta=0.5, expiry=self._E)
        chain = [cand, _row(100.0, "P", 50_000, delta=-0.5, expiry=self._E)]
        conf, d = bet_confidence(cand, chain, spot=100.0)
        assert d["chain_balanced"] is True
        assert conf == 0.7
        assert conf >= 0.40


class TestPercentileValue:
    def test_p98(self):
        assert percentile_value(list(range(1, 101)), 0.98) == 99

    def test_empty(self):
        assert percentile_value([], 0.98) == 0.0


class TestCandidateFilter:
    def test_floor_is_at_least_tradeability(self):
        # tiny positions -> floor stays at the $25M tradeability minimum
        chain = [_row(100.0, "C", 10, delta=0.5) for _ in range(10)]
        assert candidate_dwoi_floor(chain, spot=100.0) == 25_000_000.0

    def test_floor_rises_with_big_positions(self):
        # one giant + many small -> 98th pct above the $25M floor
        chain = [_row(100.0 + i, "C", 1_000_000, delta=0.9) for i in range(10)]
        floor = candidate_dwoi_floor(chain, spot=100.0)
        assert floor > 25_000_000.0

    def test_big_long_dated_call_qualifies(self):
        c = _row(110.0, "C", 200_000, delta=0.5, expiry=_date.today() + timedelta(days=120))
        assert is_dormant_candidate(c, spot=100.0, floor=10_000_000.0, today=_date.today())

    def test_near_expiry_rejected(self):
        c = _row(110.0, "C", 200_000, delta=0.5, expiry=_date.today() + timedelta(days=5))
        assert not is_dormant_candidate(c, spot=100.0, floor=10_000_000.0, today=_date.today())

    def test_below_floor_rejected(self):
        c = _row(110.0, "C", 10, delta=0.5, expiry=_date.today() + timedelta(days=120))
        assert not is_dormant_candidate(c, spot=100.0, floor=10_000_000.0, today=_date.today())

    def test_deep_itm_rejected(self):
        c = _row(50.0, "C", 200_000, delta=0.95, expiry=_date.today() + timedelta(days=120))
        assert not is_dormant_candidate(c, spot=100.0, floor=10_000_000.0, today=_date.today())
