from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import structlog
from sqlalchemy import select

from eigenview.data.exceptions import DataNotFoundError
from eigenview.data.storage import AsyncSessionLocal, Price

log = structlog.get_logger(__name__)


async def fetch_prices(
    ticker: str,
    timeframe: str = "1d",
    days: int = 90,
) -> pd.DataFrame:
    """Read OHLCV from DB (Databento-loaded). Raises DataNotFoundError if empty.

    Data is loaded externally via scripts/databento_load.py — no live download here.
    """
    cutoff_date = (datetime.utcnow() - timedelta(days=days)).date()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Price)
            .where(
                Price.ticker == ticker.upper(),
                Price.timeframe == timeframe,
                Price.date >= cutoff_date,
            )
            .order_by(Price.date.asc())
        )
        rows = result.scalars().all()

    if not rows:
        raise DataNotFoundError(f"No price data in DB for {ticker!r} ({timeframe}, {days}d). Run databento_load.py first.")

    df = pd.DataFrame([
        {"date": r.date, "open": r.open, "high": r.high,
         "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    df = df.dropna(subset=["close"])

    newest_dt = df.index.max()
    from datetime import timezone
    cutoff_ts = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    ts = pd.Timestamp(newest_dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    df.attrs["stale"] = ts < pd.Timestamp(cutoff_ts)
    if df.attrs["stale"]:
        log.warning("fetch_prices.stale", ticker=ticker, newest=str(newest_dt))

    log.info("fetch_prices.db_hit", ticker=ticker, timeframe=timeframe, rows=len(df))
    return df


async def get_prices(
    ticker: str,
    timeframe: str = "1d",
    days: int = 90,
) -> pd.DataFrame:
    """Alias for fetch_prices — reads from DB."""
    return await fetch_prices(ticker, timeframe=timeframe, days=days)
