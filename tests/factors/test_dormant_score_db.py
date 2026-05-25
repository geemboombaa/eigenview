"""Real-DB orchestration tests for dormant.score_dormant (v2).

Uses a temporary real SQLite engine (real inserts, no mocks). Chain rows are
constructed pure-logic inputs to the scorer; the DB layer (DormantBet/Catalyst)
is real.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eigenview.data.storage import Base, DormantBet
from eigenview.factors.dormant import _ChainRow, score_dormant

_EXPIRY = date.today() + timedelta(days=120)


def _row(strike, cp, oi, delta=None, iv=None):
    return _ChainRow(strike=strike, call_put=cp, oi=oi, delta=delta, iv=iv, expiry=_EXPIRY)


@pytest_asyncio.fixture
async def temp_session(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'd.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as session:
        yield session
    await engine.dispose()


async def _add_bet(session, strike, cp, oi):
    bet = DormantBet(
        ticker="NVDA",
        contract=f"NVDA{strike}{cp}",
        original_date=_EXPIRY - timedelta(days=100),
        strike=strike,
        expiry=_EXPIRY,
        call_put=cp,
        original_premium=5_000_000.0,
        original_oi=oi,
    )
    session.add(bet)
    await session.flush()


@pytest.mark.asyncio
async def test_accumulating_under_30_days(temp_session):
    r = await score_dormant("NVDA", temp_session, 100.0, [], days_of_history=10)
    assert r.firing is False
    assert r.label == "ACCUMULATING"


@pytest.mark.asyncio
async def test_no_bets_accumulating(temp_session):
    r = await score_dormant("NVDA", temp_session, 100.0, [], days_of_history=40)
    assert r.firing is False
    assert r.label == "ACCUMULATING"


@pytest.mark.asyncio
async def test_isolated_naked_call_scores(temp_session):
    await _add_bet(temp_session, 110.0, "C", 200_000)
    chain = [
        _row(110.0, "C", 200_000, delta=0.35, iv=0.33),
        _row(100.0, "C", 300, delta=0.55, iv=0.42),
        _row(108.0, "C", 150, delta=0.40, iv=0.35),
        _row(112.0, "C", 120, delta=0.30, iv=0.32),
    ]
    r = await score_dormant("NVDA", temp_session, 100.0, chain, days_of_history=40)
    assert r.factor_id == "dormant"
    assert r.strength > 0.0
    assert r.detail["best_score"] > 0
    assert r.label in ("ACTIVE", "DORMANT")


@pytest.mark.asyncio
async def test_fully_hedged_bet_not_firing(temp_session):
    await _add_bet(temp_session, 100.0, "C", 50_000)
    chain = [
        _row(100.0, "C", 50_000, delta=0.5, iv=0.4),
        _row(100.0, "P", 50_000, delta=-0.5, iv=0.4),
    ]
    r = await score_dormant("NVDA", temp_session, 100.0, chain, days_of_history=40)
    assert r.firing is False
    assert r.detail.get("reason") == "all_candidates_hedged"
