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

_is_sqlite = settings.database_url.startswith("sqlite")

if _is_sqlite and "///" in settings.database_url:
    # data/ is gitignored, so the dir is absent on fresh CI runners — create it
    # before connect or sqlite raises "unable to open database file".
    from pathlib import Path

    _db_file = settings.database_url.split("///", 1)[1]
    if _db_file and _db_file != ":memory:":
        Path(_db_file).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

_engine_kwargs: dict = {} if _is_sqlite else {
    "pool_size": 5,
    "max_overflow": 10,
    "pool_pre_ping": True,
}

engine = create_async_engine(settings.database_url, **_engine_kwargs)

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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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


class ContractHistory(Base):
    """Daily per-contract series (OI / volume / close / IV) for watched dormant bets.

    Keyed by OSI symbol so the activation engine can diff day-over-day from real
    Databento history (no need to wait for snapshots to accumulate).
    """
    __tablename__ = "contract_history"
    __table_args__ = (UniqueConstraint("osi_symbol", "date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    osi_symbol: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    oi: Mapped[int | None] = mapped_column(Integer)
    volume: Mapped[int | None] = mapped_column(Integer)
    close: Mapped[float | None] = mapped_column(Float)
    iv: Mapped[float | None] = mapped_column(Float)


class NewsItem(Base):
    __tablename__ = "news"
    __table_args__ = (UniqueConstraint("url_hash"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50))
    event_date: Mapped[date] = mapped_column(Date)
    days_from_now: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MacroDaily(Base):
    __tablename__ = "macro_daily"
    __table_args__ = (UniqueConstraint("date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    week_ending: Mapped[date] = mapped_column(Date, nullable=False)
    instrument: Mapped[str] = mapped_column(String(20), nullable=False)
    net_long_pct: Mapped[float | None] = mapped_column(Float)
    net_long_contracts: Mapped[int | None] = mapped_column(Integer)


class Pick(Base):
    __tablename__ = "picks"
    __table_args__ = (UniqueConstraint("date", "ticker"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    spec_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LlmLog(Base):
    __tablename__ = "llm_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    call_type: Mapped[str] = mapped_column(String(50))
    ticker: Mapped[str | None] = mapped_column(String(20))
    prompt: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(50))


class SignalTrigger(Base):
    """Fired signal events — one row per ticker per scan per setup pattern."""
    __tablename__ = "signal_triggers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scan_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    setup_type: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "long" or "short"
    entry_low: Mapped[float | None] = mapped_column(Float)
    entry_high: Mapped[float | None] = mapped_column(Float)
    stop: Mapped[float | None] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    rr_ratio: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    fired_at: Mapped[str | None] = mapped_column(String(30))   # ISO datetime
    valid_until: Mapped[str | None] = mapped_column(String(30))  # ISO datetime or None


async def write_signal_trigger(
    session: AsyncSession,
    ticker: str,
    scan_date: str,
    setup_type: str,
    direction: str,
    entry_low: float | None,
    entry_high: float | None,
    stop: float | None,
    target: float | None,
    confidence: float | None,
) -> SignalTrigger:
    rr: float | None = None
    if stop and target and entry_high and entry_high != stop:
        rr = (target - entry_high) / (entry_high - stop)
    trigger = SignalTrigger(
        ticker=ticker,
        scan_date=scan_date,
        setup_type=setup_type,
        direction=direction,
        entry_low=entry_low,
        entry_high=entry_high,
        stop=stop,
        target=target,
        rr_ratio=rr,
        confidence=confidence,
        fired_at=datetime.utcnow().isoformat(),
        valid_until=None,
    )
    session.add(trigger)
    await session.flush()
    return trigger


class ForwardReturn(Base):
    """Realized returns for each pick — populated T+5 and T+20 by forward_returns.py cron."""
    __tablename__ = "forward_returns"
    __table_args__ = (UniqueConstraint("ticker", "scan_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scan_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    conviction: Mapped[int | None] = mapped_column(Integer)
    setup_type: Mapped[str | None] = mapped_column(String(50))
    direction: Mapped[str | None] = mapped_column(String(10))
    entry_price: Mapped[float | None] = mapped_column(Float)
    macro_regime: Mapped[str | None] = mapped_column(String(10))
    # Populated T+5
    return_5d: Mapped[float | None] = mapped_column(Float)
    hit_target_5d: Mapped[bool | None] = mapped_column(Boolean)
    hit_stop_5d: Mapped[bool | None] = mapped_column(Boolean)
    # Populated T+20
    return_20d: Mapped[float | None] = mapped_column(Float)
    hit_target_20d: Mapped[bool | None] = mapped_column(Boolean)
    hit_stop_20d: Mapped[bool | None] = mapped_column(Boolean)
    # IC tracking snapshot
    indicator_state: Mapped[str | None] = mapped_column(Text)  # JSON
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


async def create_tables() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
