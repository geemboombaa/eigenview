"""tests/data/test_storage.py — ORM model and session tests using in-memory SQLite."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import (
    Catalyst,
    Chain,
    DormantBet,
    MacroDaily,
    NewsItem,
    Pick,
    Price,
    SignalBench,
)


# ---------------------------------------------------------------------------
# Price table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_price_insert_and_query(db_session: AsyncSession) -> None:
    row = Price(ticker="NVDA", date=date.today(), open=100.0, high=105.0,
                low=95.0, close=102.0, volume=1_000_000, timeframe="1d")
    db_session.add(row)
    await db_session.commit()

    result = await db_session.execute(select(Price).where(Price.ticker == "NVDA"))
    fetched = result.scalars().all()
    assert len(fetched) == 1
    assert fetched[0].close == 102.0
    assert fetched[0].timeframe == "1d"


@pytest.mark.asyncio
async def test_price_unique_constraint(db_session: AsyncSession) -> None:
    """Duplicate (ticker, date, timeframe) must not insert a second row."""
    from sqlalchemy.exc import IntegrityError

    today = date.today()
    row1 = Price(ticker="AAPL", date=today, open=150.0, high=155.0,
                 low=148.0, close=152.0, volume=5_000_000, timeframe="1d")
    row2 = Price(ticker="AAPL", date=today, open=151.0, high=156.0,
                 low=149.0, close=153.0, volume=6_000_000, timeframe="1d")
    db_session.add(row1)
    await db_session.commit()

    db_session.add(row2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


# ---------------------------------------------------------------------------
# MacroDaily table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_macro_daily_insert(db_session: AsyncSession) -> None:
    row = MacroDaily(
        date=date.today(), dix=0.47, gex_index=1.2e9,
        vix_m1=14.5, vix_m2=16.0, vix_contango_pct=0.03,
    )
    db_session.add(row)
    await db_session.commit()

    result = await db_session.execute(
        select(MacroDaily).order_by(MacroDaily.date.desc()).limit(1)
    )
    fetched = result.scalar_one_or_none()
    assert fetched is not None
    assert fetched.dix == pytest.approx(0.47)
    assert fetched.vix_m1 == pytest.approx(14.5)


@pytest.mark.asyncio
async def test_macro_daily_nullable_fields(db_session: AsyncSession) -> None:
    row = MacroDaily(date=date.today(), dix=None, gex_index=None)
    db_session.add(row)
    await db_session.commit()

    result = await db_session.execute(select(MacroDaily))
    fetched = result.scalar_one()
    assert fetched.dix is None
    assert fetched.gex_index is None


# ---------------------------------------------------------------------------
# NewsItem table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_news_item_insert(db_session: AsyncSession) -> None:
    import hashlib
    url_hash = hashlib.sha256(b"http://example.com/news/1").hexdigest()[:64]
    item = NewsItem(
        ticker="NVDA",
        headline="NVDA beats earnings",
        url_hash=url_hash,
        source="reuters",
        timestamp=datetime.utcnow(),
    )
    db_session.add(item)
    await db_session.commit()

    result = await db_session.execute(select(NewsItem).where(NewsItem.ticker == "NVDA"))
    fetched = result.scalars().all()
    assert len(fetched) == 1
    assert fetched[0].headline == "NVDA beats earnings"


# ---------------------------------------------------------------------------
# Catalyst table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_catalyst_insert_and_query(db_session: AsyncSession) -> None:
    ev_date = date.today() + timedelta(days=30)
    cat = Catalyst(
        ticker="AAPL",
        event_type="earnings",
        event_date=ev_date,
        days_from_now=30,
    )
    db_session.add(cat)
    await db_session.commit()

    result = await db_session.execute(
        select(Catalyst).where(Catalyst.ticker == "AAPL")
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.event_type == "earnings"
    assert fetched.days_from_now == 30


# ---------------------------------------------------------------------------
# Pick table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pick_insert(db_session: AsyncSession) -> None:
    pick = Pick(
        date=date.today(), ticker="NVDA",
        score=0.85, setup_type="pullback", direction="long",
        entry_low=420.0, entry_high=435.0, stop=410.0, conviction=4,
        thesis="Strong pullback setup.",
    )
    db_session.add(pick)
    await db_session.commit()

    result = await db_session.execute(select(Pick).where(Pick.ticker == "NVDA"))
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.conviction == 4
    assert fetched.entry_low == pytest.approx(420.0)


# ---------------------------------------------------------------------------
# DormantBet table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_dormant_bet_insert(db_session: AsyncSession) -> None:
    today = date.today()
    bet = DormantBet(
        ticker="NVDA",
        contract="NVDA_650C_2025-09",
        original_date=today,
        strike=650.0,
        expiry=today + timedelta(days=120),
        call_put="C",
        original_premium=1_200_000.0,
        original_oi=1000,
        current_oi=1150,
    )
    db_session.add(bet)
    await db_session.commit()

    result = await db_session.execute(
        select(DormantBet).where(DormantBet.ticker == "NVDA")
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.original_premium == pytest.approx(1_200_000.0)
    assert fetched.call_put == "C"


# ---------------------------------------------------------------------------
# Chain table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_chain_insert(db_session: AsyncSession) -> None:
    row = Chain(
        ticker="TSLA",
        snapshot_date=date.today(),
        strike=200.0,
        expiry=date.today() + timedelta(days=30),
        call_put="C",
        bid=2.5, ask=3.0,
        volume=500, oi=2000,
        iv=0.45, delta=0.4, gamma=0.002,
    )
    db_session.add(row)
    await db_session.commit()

    result = await db_session.execute(
        select(Chain).where(Chain.ticker == "TSLA")
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.iv == pytest.approx(0.45)
    assert fetched.gamma == pytest.approx(0.002)


# ---------------------------------------------------------------------------
# SignalBench table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_signal_bench_insert(db_session: AsyncSession) -> None:
    bench = SignalBench(
        date=date.today(), ticker="META",
        soft_factors_firing=2, tier="B",
        direction="long", setup_type="pullback",
        conviction=2, entry_low=490.0, entry_high=505.0, stop=480.0,
    )
    db_session.add(bench)
    await db_session.commit()

    result = await db_session.execute(
        select(SignalBench).where(SignalBench.ticker == "META")
    )
    fetched = result.scalars().first()
    assert fetched is not None
    assert fetched.tier == "B"
    assert fetched.soft_factors_firing == 2
