"""Real tests for ranker.rank_picks + write_picks against a temp real SQLite DB.

Uses constructed scorecards (pure domain objects) + a real (temporary) SQLite
engine. No mocks; write_picks performs real inserts into a throwaway DB so the
project DB is untouched.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eigenview.data.storage import Base, Pick, SignalBench
from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.ranker import rank_picks, write_picks


def _fr(fid, firing, strength=0.8, label="breakout", detail=None):
    return FactorResult(fid, firing, strength, label, detail or {}, f"{fid} narrative")


def _qualified_sc(ticker="QUAL"):
    return TickerScorecard(
        ticker=ticker,
        macro=_fr("macro", True, 0.8, "GREEN"),
        technical=_fr("technical", True, 0.85, "breakout",
                      {"swing_low": 95.0, "swing_high": 105.0, "direction": "long"}),
        gex=_fr("gex", True, 0.75, "long_gamma"),
        flow=_fr("flow", True, 0.7, "calls"),
        dormant=_fr("dormant", True, 0.6, "ACTIVE"),
        sentiment=_fr("sentiment", True, 0.6, "bullish"),
        spot_price=100.0,
    )


def _bench_sc(ticker="BENCH"):
    # TA fires, GEX off, 1 soft -> tier C (near-miss, written to bench)
    return TickerScorecard(
        ticker=ticker,
        macro=_fr("macro", True, 0.8, "GREEN"),
        technical=_fr("technical", True, 0.6, "breakout",
                      {"swing_low": 95.0, "swing_high": 105.0, "direction": "long"}),
        gex=_fr("gex", False, 0.0, "flip_zone"),
        flow=_fr("flow", True, 0.7, "calls"),
        dormant=_fr("dormant", False, 0.0, "DORMANT"),
        sentiment=_fr("sentiment", False, 0.0, "NO DATA"),
        spot_price=100.0,
    )


@pytest_asyncio.fixture
async def temp_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 't.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


def test_rank_picks_keeps_qualified():
    sc = _qualified_sc()
    assert sc in rank_picks([sc], macro_score=8)


def test_rank_picks_drops_unqualified():
    assert rank_picks([_bench_sc()], macro_score=8) == []


def test_rank_picks_red_macro_does_not_block_long():
    # Macro never gates direction (user-locked 2026-05-29): a fully-gated long
    # pick still ranks under RED macro.
    sc = _qualified_sc()
    assert sc in rank_picks([sc], macro_score=1)


@pytest.mark.asyncio
async def test_write_picks_persists_pick_and_bench(temp_session):
    qual = _qualified_sc("QUAL")
    bench = _bench_sc("BENCH")
    picks = await write_picks(
        [qual], macro_score=8, session=temp_session, all_scorecards=[qual, bench]
    )
    assert len(picks) == 1
    assert picks[0].ticker == "QUAL"
    assert 1 <= picks[0].conviction <= 5

    pick_count = (await temp_session.execute(select(func.count()).select_from(Pick))).scalar_one()
    assert pick_count == 1
    bench_count = (await temp_session.execute(select(func.count()).select_from(SignalBench))).scalar_one()
    assert bench_count == 1  # BENCH written, QUAL (tier A) skipped


@pytest.mark.asyncio
async def test_write_picks_idempotent_update(temp_session):
    qual = _qualified_sc("QUAL")
    await write_picks([qual], 8, temp_session, all_scorecards=[qual])
    await write_picks([qual], 8, temp_session, all_scorecards=[qual])
    pick_count = (await temp_session.execute(select(func.count()).select_from(Pick))).scalar_one()
    assert pick_count == 1  # same date+ticker updates, not duplicates
