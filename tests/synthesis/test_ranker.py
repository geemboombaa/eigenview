from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import Pick
from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.ranker import rank_picks, write_picks


def _real_tickers(n: int = 3) -> list[str]:
    import asyncio
    from eigenview.data.universe import get_universe
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return ["AAPL", "MSFT", "NVDA"][:n]
        tickers = loop.run_until_complete(get_universe("ndx100"))
        if tickers and len(tickers) >= n:
            return tickers[:n]
        return tickers or ["AAPL", "MSFT", "NVDA"]
    except Exception:
        return ["AAPL", "MSFT", "NVDA"]


def make_scorecard(
    ticker: str = "AAPL",
    ta: bool = True,
    gex: bool = True,
    flow: bool = True,
    dormant: bool = True,
    sentiment: bool = True,
    strength: float = 0.7,
) -> TickerScorecard:
    return TickerScorecard(
        ticker=ticker,
        macro=FactorResult(factor_id="macro_regime", firing=True, strength=0.8, label="GREEN"),
        technical=FactorResult(factor_id="technical", firing=ta, strength=strength, label="breakout"),
        gex=FactorResult(factor_id="gex", firing=gex, strength=strength, label="short_gamma"),
        flow=FactorResult(factor_id="flow", firing=flow, strength=strength, label="calls"),
        dormant=FactorResult(factor_id="dormant", firing=dormant, strength=strength, label="ACTIVE"),
        sentiment=FactorResult(factor_id="sentiment", firing=sentiment, strength=strength, label="bullish"),
        spot_price=500.0,
    )


def test_rank_sorts_by_conviction() -> None:
    tickers = _real_tickers(3)
    low = make_scorecard(tickers[2], strength=0.3)
    mid = make_scorecard(tickers[1], strength=0.6)
    high = make_scorecard(tickers[0], strength=0.9)

    ranked = rank_picks([low, mid, high], macro_score=8)
    assert ranked[0].ticker == tickers[0]
    assert ranked[-1].ticker == tickers[2]


def test_rank_filters_unqualified() -> None:
    tickers = _real_tickers(2)
    qualified = make_scorecard(tickers[0])
    unqualified = make_scorecard(tickers[1], gex=False)

    ranked = rank_picks([qualified, unqualified], macro_score=8)
    result_tickers = [s.ticker for s in ranked]
    assert tickers[0] in result_tickers
    assert tickers[1] not in result_tickers


@pytest.mark.asyncio
async def test_write_picks_inserts_rows(db_session: AsyncSession) -> None:
    tickers = _real_tickers(2)
    sc1 = make_scorecard(tickers[0])
    sc2 = make_scorecard(tickers[1])

    await write_picks([sc1, sc2], macro_score=8, session=db_session)
    await db_session.flush()

    result = await db_session.execute(select(Pick))
    rows = result.scalars().all()
    row_tickers = {r.ticker for r in rows}
    assert tickers[0] in row_tickers
    assert tickers[1] in row_tickers
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_write_picks_updates_existing(db_session: AsyncSession) -> None:
    tickers = _real_tickers(1)
    ticker = tickers[0]
    sc = make_scorecard(ticker, strength=0.5)
    await write_picks([sc], macro_score=8, session=db_session)
    await db_session.flush()

    sc_updated = make_scorecard(ticker, strength=0.9)
    await write_picks([sc_updated], macro_score=8, session=db_session)
    await db_session.flush()

    result = await db_session.execute(select(Pick).where(Pick.ticker == ticker))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].conviction is not None
