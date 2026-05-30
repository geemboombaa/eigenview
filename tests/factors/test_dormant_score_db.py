"""Real-DB orchestration test for the LIVE dormant path (score_dormant_from_history).

Uses a temporary real SQLite engine (real inserts, no mocks). The old static path
(score_dormant/score_bet_v2) was removed — the live scanner uses the activation
engine only, and hedged contracts are filtered at watchlist-write by bet_confidence.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eigenview.data.storage import Base, DormantBet
from eigenview.factors.dormant import _ChainRow, score_dormant_from_history

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
async def test_no_bets_accumulating(temp_session):
    r = await score_dormant_from_history("NVDA", temp_session, 100.0, [])
    assert r.firing is False
    assert r.label == "ACCUMULATING"


@pytest.mark.asyncio
async def test_no_contract_history_does_not_fire(temp_session):
    """Static structure alone must NOT fire. A real bet exists but there is neither
    contract_history nor a second chain snapshot, so there is no baseline to compare.
    The result must be a non-firing ACCUMULATING candidate, not a fire."""
    await _add_bet(temp_session, 110.0, "C", 200_000)
    chain = [
        _row(110.0, "C", 200_000, delta=0.35, iv=0.33),
        _row(100.0, "C", 300, delta=0.55, iv=0.42),
    ]
    r = await score_dormant_from_history("NVDA", temp_session, 100.0, chain)
    assert r.firing is False
    assert r.label == "ACCUMULATING"
    assert r.detail.get("reason") == "awaiting_baseline"
