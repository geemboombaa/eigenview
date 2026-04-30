from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import Pick
from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.ranker import rank_picks, write_picks


def fr(factor_id: str, firing: bool, strength: float = 0.5, label: str = "ok") -> FactorResult:
    return FactorResult(factor_id=factor_id, firing=firing, strength=strength, label=label)


def make_scorecard(
    ticker: str = "NVDA",
    ta: bool = True,
    gex: bool = True,
    flow: bool = True,
    dormant: bool = True,
    sentiment: bool = True,
    strength: float = 0.7,
) -> TickerScorecard:
    return TickerScorecard(
        ticker=ticker,
        macro=fr("macro_regime", True, 0.8, "GREEN"),
        technical=fr("technical", ta, strength, "breakout"),
        gex=fr("gex", gex, strength, "short_gamma"),
        flow=fr("flow", flow, strength, "calls"),
        dormant=fr("dormant", dormant, strength, "ACTIVE"),
        sentiment=fr("sentiment", sentiment, strength, "bullish"),
        spot_price=500.0,
    )


def test_rank_sorts_by_conviction() -> None:
    low = make_scorecard("AAPL", strength=0.3)
    mid = make_scorecard("TSLA", strength=0.6)
    high = make_scorecard("NVDA", strength=0.9)

    ranked = rank_picks([low, mid, high], macro_score=8)
    assert ranked[0].ticker == "NVDA"
    assert ranked[-1].ticker == "AAPL"


def test_rank_filters_unqualified() -> None:
    qualified = make_scorecard("NVDA")
    # GEX not firing → fails Gate 2 → unqualified
    unqualified = make_scorecard("AAPL", gex=False)

    ranked = rank_picks([qualified, unqualified], macro_score=8)
    tickers = [s.ticker for s in ranked]
    assert "NVDA" in tickers
    assert "AAPL" not in tickers


@pytest.mark.asyncio
async def test_write_picks_inserts_rows(db_session: AsyncSession) -> None:
    sc1 = make_scorecard("NVDA")
    sc2 = make_scorecard("AAPL")

    await write_picks([sc1, sc2], macro_score=8, session=db_session)
    await db_session.flush()

    result = await db_session.execute(select(Pick))
    rows = result.scalars().all()
    tickers = {r.ticker for r in rows}
    assert "NVDA" in tickers
    assert "AAPL" in tickers
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_write_picks_updates_existing(db_session: AsyncSession) -> None:
    sc = make_scorecard("NVDA", strength=0.5)
    await write_picks([sc], macro_score=8, session=db_session)
    await db_session.flush()

    # Call again with higher strength — should update, not insert a second row
    sc_updated = make_scorecard("NVDA", strength=0.9)
    await write_picks([sc_updated], macro_score=8, session=db_session)
    await db_session.flush()

    result = await db_session.execute(select(Pick).where(Pick.ticker == "NVDA"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].conviction is not None
