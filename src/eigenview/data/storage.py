from __future__ import annotations

import sys
from collections.abc import AsyncGenerator
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from eigenview.config import settings

# Windows asyncio fix — asyncpg requires SelectorEventLoop
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine, expire_on_commit=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


class Base(DeclarativeBase):
    pass


class Price(Base):
    __tablename__ = "prices"
    __table_args__ = (UniqueConstraint("ticker", "date", "timeframe"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(BigInteger)
    timeframe: Mapped[str] = mapped_column(String(10), default="1d")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Chain(Base):
    __tablename__ = "chains"
    __table_args__ = (UniqueConstraint("ticker", "snapshot_date", "strike", "expiry", "call_put"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    strike: Mapped[float] = mapped_column(Float, nullable=False)
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    call_put: Mapped[str] = mapped_column(String(1), nullable=False)
    bid: Mapped[float | None] = mapped_column(Float)
    ask: Mapped[float | None] = mapped_column(Float)
    volume: Mapped[int | None] = mapped_column(Integer)
    oi: Mapped[int | None] = mapped_column(Integer)
    iv: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)
    gamma: Mapped[float | None] = mapped_column(Float)


class NewsItem(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("url_hash"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    headline: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    timestamp: Mapped[datetime | None] = mapped_column(DateTime)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Catalyst(Base):
    __tablename__ = "catalysts"
    __table_args__ = (UniqueConstraint("ticker", "event_type", "event_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    event_date: Mapped[date] = mapped_column(Date)
    days_from_now: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MacroDaily(Base):
    __tablename__ = "macro_daily"
    __table_args__ = (UniqueConstraint("date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    dix: Mapped[float | None] = mapped_column(Float)
    gex_index: Mapped[float | None] = mapped_column(Float)
    vix_m1: Mapped[float | None] = mapped_column(Float)
    vix_m2: Mapped[float | None] = mapped_column(Float)
    vix_m3: Mapped[float | None] = mapped_column(Float)
    vix_contango_pct: Mapped[float | None] = mapped_column(Float)
    spx_breadth_pct: Mapped[float | None] = mapped_column(Float)   # % stocks above 50dma
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CotWeekly(Base):
    __tablename__ = "cot_weekly"
    __table_args__ = (UniqueConstraint("week_ending", "instrument"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    week_ending: Mapped[date] = mapped_column(Date, nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    net_long_pct: Mapped[float | None] = mapped_column(Float)
    net_long_contracts: Mapped[int | None] = mapped_column(Integer)


class Pick(Base):
    __tablename__ = "picks"
    __table_args__ = (UniqueConstraint("date", "ticker"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    score: Mapped[float | None] = mapped_column(Float)
    setup_type: Mapped[str | None] = mapped_column(String(50))
    direction: Mapped[str | None] = mapped_column(String(20))
    entry_low: Mapped[float | None] = mapped_column(Float)
    entry_high: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    conviction: Mapped[int | None] = mapped_column(Integer)
    thesis: Mapped[str | None] = mapped_column(Text)
    factors_json: Mapped[str | None] = mapped_column(Text)
    signal_fired_at: Mapped[datetime | None] = mapped_column(DateTime)  # when pattern first fired
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DormantBet(Base):
    __tablename__ = "dormant_bets"
    __table_args__ = (UniqueConstraint("ticker", "contract", "original_date"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    contract: Mapped[str] = mapped_column(String(50), nullable=False)
    original_date: Mapped[date] = mapped_column(Date, nullable=False)
    strike: Mapped[float] = mapped_column(Float)
    expiry: Mapped[date] = mapped_column(Date)
    call_put: Mapped[str] = mapped_column(String(1))
    original_premium: Mapped[float | None] = mapped_column(Float)
    current_oi: Mapped[int | None] = mapped_column(Integer)
    original_oi: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SignalBench(Base):
    """Near-miss and partial-signal tickers — tiered B/C/D."""
    __tablename__ = "signal_bench"
    __table_args__ = (UniqueConstraint("date", "ticker"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    soft_factors_firing: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str | None] = mapped_column(Text)
    # Tier: B=near miss (TA+GEX+1soft), C=one hard gate+1soft, D=strong single signal
    tier: Mapped[str] = mapped_column(String(2), default='B')
    factors_json: Mapped[str | None] = mapped_column(Text)
    direction: Mapped[str | None] = mapped_column(String(10))
    setup_type: Mapped[str | None] = mapped_column(String(50))
    conviction: Mapped[int] = mapped_column(Integer, default=1)
    entry_low: Mapped[float | None] = mapped_column(Float)
    entry_high: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)


class FactorScore(Base):
    """Per-ticker per-day raw factor scores for all scanned tickers (heat map source)."""
    __tablename__ = "factor_scores"
    __table_args__ = (UniqueConstraint("date", "ticker"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    ta_strength: Mapped[float | None] = mapped_column(Float)
    ta_label: Mapped[str | None] = mapped_column(String(50))
    gex_strength: Mapped[float | None] = mapped_column(Float)
    gex_label: Mapped[str | None] = mapped_column(String(50))
    flow_strength: Mapped[float | None] = mapped_column(Float)
    flow_label: Mapped[str | None] = mapped_column(String(50))
    dormant_strength: Mapped[float | None] = mapped_column(Float)
    dormant_label: Mapped[str | None] = mapped_column(String(50))
    sentiment_strength: Mapped[float | None] = mapped_column(Float)
    sentiment_label: Mapped[str | None] = mapped_column(String(50))
    macro_score: Mapped[int | None] = mapped_column(Integer)
    spot_price: Mapped[float | None] = mapped_column(Float)
    factors_firing: Mapped[int | None] = mapped_column(Integer)  # count of factors firing
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SpecNote(Base):
    """Notes attached to spec entries (e.g. pullback_in_trend)."""
    __tablename__ = "spec_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    spec_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LlmLog(Base):
    __tablename__ = "llm_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    call_type: Mapped[str] = mapped_column(String(50))
    ticker: Mapped[str | None] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(50))


async def create_tables() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
