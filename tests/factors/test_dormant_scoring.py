"""Pure-function tests for dormant scoring (percentile-relative design).

dwoi / percentile_rank / isolation_multiplier / score_bet_v2 are pure
transforms; these exercise each branch with explicit computed inputs.
AC1 (fully hedged -> 0) and AC2 (big isolated cheap call -> max structural).
"""
from __future__ import annotations

from datetime import date, timedelta

from eigenview.data.storage import DormantBet
from datetime import date as _date

from eigenview.factors.dormant import (
    _ChainRow,
    _build_chain_index,
    candidate_dwoi_floor,
    dwoi,
    is_dormant_candidate,
    isolation_multiplier,
    percentile_rank,
    percentile_value,
    score_bet_v2,
)


def _row(strike, cp, oi, delta=None, iv=None, expiry=None):
    return _ChainRow(strike=strike, call_put=cp, oi=oi, delta=delta, iv=iv, expiry=expiry)


def _bet(strike=110.0, cp="C", oi=200_000, premium=5_000_000.0, dte=120, alive=100, expiry=None):
    b = DormantBet()
    b.ticker = "NVDA"
    b.strike = strike
    b.call_put = cp
    b.original_oi = oi
    b.original_premium = premium
    b.expiry = expiry or (date.today() + timedelta(days=dte))
    b.original_date = b.expiry - timedelta(days=alive)
    return b


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


class TestIsolationMultiplier:
    def test_naked_directional_isolated(self):
        cand = _row(110.0, "C", 200_000, delta=0.35)
        chain = [_row(110.0, "C", 200_000, delta=0.35),
                 _row(108.0, "C", 150, delta=0.40),
                 _row(112.0, "C", 120, delta=0.30)]
        mult, purity = isolation_multiplier(cand, chain, spot=100.0)
        assert purity >= 0.7 and mult == 1.0

    def test_collar_fully_hedged(self):
        cand = _row(100.0, "C", 50_000, delta=0.5)
        chain = [_row(100.0, "C", 50_000, delta=0.5), _row(100.0, "P", 50_000, delta=-0.5)]
        mult, purity = isolation_multiplier(cand, chain, spot=100.0)
        assert purity < 0.3 and mult == 0.0

    def test_partial_hedge_half(self):
        cand = _row(100.0, "C", 50_000, delta=0.5)
        chain = [_row(100.0, "C", 50_000, delta=0.5), _row(100.0, "P", 25_000, delta=-0.5)]
        mult, purity = isolation_multiplier(cand, chain, spot=100.0)
        assert 0.3 <= purity < 0.7 and mult == 0.5


def _giant_call_chain(expiry, n_filler=120):
    """Candidate 110C dominates a chain of many small same-expiry calls."""
    cand = _row(110.0, "C", 200_000, delta=0.35, iv=0.20, expiry=expiry)
    chain = [cand]
    for i in range(n_filler):
        chain.append(_row(108.0 + i * 0.25, "C", 120, delta=0.30, iv=0.42, expiry=expiry))
    return chain


class TestScoreBetV2:
    def test_ac1_fully_hedged_scores_zero(self):
        bet = _bet(strike=100.0, cp="C", oi=50_000)
        e = bet.expiry
        chain = [_row(100.0, "C", 50_000, delta=0.5, iv=0.4, expiry=e),
                 _row(100.0, "P", 50_000, delta=-0.5, iv=0.4, expiry=e)]
        score, detail = score_bet_v2(bet, chain, spot=100.0, catalyst_near=True)
        assert score == 0.0
        assert detail["isolation"] == "fully_hedged"

    def test_ac2_big_isolated_cheap_call_max_structural(self):
        bet = _bet(strike=110.0, cp="C", oi=200_000)
        chain = _giant_call_chain(bet.expiry, n_filler=120)
        score, detail = score_bet_v2(bet, chain, spot=100.0, catalyst_near=False)
        assert detail["isolation_multiplier"] == 1.0
        assert detail["size_pct"] >= 0.99   # biggest of 121 contracts
        assert detail["iv_pct"] <= 0.20      # cheapest IV
        assert detail["structural_score"] == 3  # size(2) + cheap-IV(1)
        assert score >= 3

    def test_small_position_low_size_percentile(self):
        bet = _bet(strike=110.0, cp="C", oi=120)
        # candidate is just one of many equal small calls -> not top percentile
        e = bet.expiry
        chain = [_row(108.0 + i * 0.5, "C", 120, delta=0.3, iv=0.4, expiry=e) for i in range(50)]
        chain.append(_row(110.0, "C", 120, delta=0.3, iv=0.4, expiry=e))
        score, detail = score_bet_v2(bet, chain, spot=100.0, catalyst_near=False)
        assert detail["size_pct"] < 0.90  # not a standout


class TestPercentileValue:
    def test_p80(self):
        assert percentile_value([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.80) == 9

    def test_empty(self):
        assert percentile_value([], 0.80) == 0.0


class TestCandidateFilter:
    def test_floor_is_at_least_tradeability(self):
        # tiny positions -> floor stays at the $1M tradeability minimum
        chain = [_row(100.0, "C", 10, delta=0.5) for _ in range(10)]
        assert candidate_dwoi_floor(chain, spot=100.0) == 1_000_000.0

    def test_floor_rises_with_big_positions(self):
        # one giant + many small -> 80th pct above the $1M floor
        chain = [_row(100.0 + i, "C", 100_000, delta=0.5) for i in range(10)]
        floor = candidate_dwoi_floor(chain, spot=100.0)
        assert floor > 1_000_000.0

    def test_big_long_dated_call_qualifies(self):
        c = _row(110.0, "C", 200_000, delta=0.5, expiry=_date.today() + timedelta(days=120))
        assert is_dormant_candidate(c, spot=100.0, floor=1_000_000.0, today=_date.today())

    def test_near_expiry_rejected(self):
        c = _row(110.0, "C", 200_000, delta=0.5, expiry=_date.today() + timedelta(days=5))
        assert not is_dormant_candidate(c, spot=100.0, floor=1_000_000.0, today=_date.today())

    def test_below_floor_rejected(self):
        c = _row(110.0, "C", 10, delta=0.5, expiry=_date.today() + timedelta(days=120))
        assert not is_dormant_candidate(c, spot=100.0, floor=1_000_000.0, today=_date.today())

    def test_deep_itm_rejected(self):
        c = _row(50.0, "C", 200_000, delta=0.95, expiry=_date.today() + timedelta(days=120))
        assert not is_dormant_candidate(c, spot=100.0, floor=1_000_000.0, today=_date.today())
