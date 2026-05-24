from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pandas as pd
import structlog
import yfinance as yf
from sqlalchemy import select, text
from sqlalchemy.dialects.sqlite import insert as upsert
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from eigenview.data.exceptions import DataNotFoundError
from eigenview.data.storage import AsyncSessionLocal, Price

log = structlog.get_logger(__name__)

_sem = asyncio.Semaphore(10)

_INTERVAL_MAP = {
    "1d": "1d",
    "1h": "1h",
    "4h": "1h",  # yfinance has no 4h; caller must resample if needed
    "1wk": "1wk",
}


def _download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    """Blocking yfinance download — run in executor."""
    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    return df


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_not_exception_type(DataNotFoundError),
)
async def fetch_prices(
    ticker: str,
    timeframe: str = "1d",
    days: int = 90,
) -> pd.DataFrame:
    """Download OHLCV from yfinance, upsert to DB, return DataFrame.

    Returns a DataFrame indexed by date with columns: open, high, low, close, volume.
    Sets df.attrs["stale"] = True when the newest row is more than 24 hours old.
    Raises DataNotFoundError when yfinance returns an empty result.
    """
    interval = _INTERVAL_MAP.get(timeframe, timeframe)
    period = f"{days}d"

    log.info("fetch_prices.start", ticker=ticker, timeframe=timeframe, days=days)

    async with _sem:
        loop = asyncio.get_event_loop()
        raw: pd.DataFrame = await loop.run_in_executor(
            None, _download, ticker, period, interval
        )

    if raw.empty:
        raise DataNotFoundError(f"No price data returned for {ticker!r}")

    # Flatten multi-level columns that yfinance sometimes produces
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [col[0].lower() for col in raw.columns]
    else:
        raw.columns = [c.lower() for c in raw.columns]

    raw.index.name = "date"
    raw.index = pd.to_datetime(raw.index).normalize()

    df = raw[["open", "high", "low", "close", "volume"]].copy()
    df = df.dropna(subset=["close"])

    rows = [
        {
            "ticker": ticker.upper(),
            "date": idx.date(),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": int(row["volume"]),
            "timeframe": timeframe,
        }
        for idx, row in df.iterrows()
    ]

    if rows:
        async with AsyncSessionLocal() as session:
            stmt = (
                upsert(Price)
                .values(rows)
                .on_conflict_do_nothing()
            )
            await session.execute(stmt)
            await session.commit()
        log.info("fetch_prices.upserted", ticker=ticker, rows=len(rows))

    newest_dt = df.index.max()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    # Normalise to UTC regardless of whether the index is tz-aware or tz-naive
    ts = pd.Timestamp(newest_dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    if ts < pd.Timestamp(cutoff):
        df.attrs["stale"] = True
        log.warning("fetch_prices.stale", ticker=ticker, newest=str(newest_dt))
    else:
        df.attrs["stale"] = False

    return df


async def get_prices(
    ticker: str,
    timeframe: str = "1d",
    days: int = 90,
) -> pd.DataFrame:
    """Return prices from DB; fall back to fetch_prices if missing.

    Raises DataNotFoundError when no data exists and fetch also returns empty.
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
        log.info("get_prices.cache_miss", ticker=ticker)
        return await fetch_prices(ticker, timeframe=timeframe, days=days)

    df = pd.DataFrame(
        [
            {
                "date": r.date,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
    )
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")

    newest_dt = df.index.max()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=24)
    ts = pd.Timestamp(newest_dt)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    if ts < pd.Timestamp(cutoff):
        df.attrs["stale"] = True
    else:
        df.attrs["stale"] = False

    log.info("get_prices.cache_hit", ticker=ticker, rows=len(df))
    return df
