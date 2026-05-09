"""
Forward returns populator — runs as nightly cron job.

Populates forward_returns table with realized T+5 and T+20 returns for each pick.
Must run AFTER market close on T+5 and T+20 after each scan date.

Usage (CLI, called by Windows Task Scheduler):
    uv run eigenview populate-forward-returns

Or directly:
    python -m eigenview.synthesis.forward_returns
"""
from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import pandas as pd
import structlog
from sqlalchemy import select, update

from eigenview.data.prices import get_prices
from eigenview.data.storage import AsyncSessionLocal, ForwardReturn, Pick

log = structlog.get_logger(__name__)

_TRADING_DAYS_5 = 7    # calendar days covering 5 trading days
_TRADING_DAYS_20 = 28  # calendar days covering 20 trading days


def _trading_day_offset(start: date, n_trading_days: int) -> date:
    """Approximate: add enough calendar days to cover N trading days."""
    offset = int(n_trading_days * 1.45) + 1
    return start + timedelta(days=offset)


async def populate_forward_returns_for_date(scan_date: date) -> int:
    """
    For all picks on scan_date, fetch OHLCV and compute realized returns.
    Returns number of rows updated.
    """
    async with AsyncSessionLocal() as session:
        picks = (await session.execute(
            select(Pick).where(Pick.date == scan_date)
        )).scalars().all()

        if not picks:
            log.info("no_picks_for_date", scan_date=str(scan_date))
            return 0

        today = date.today()
        updated = 0

        for pick in picks:
            ticker = pick.ticker
            scan_dt = scan_date

            # Check if row already exists
            existing = (await session.execute(
                select(ForwardReturn).where(
                    ForwardReturn.ticker == ticker,
                    ForwardReturn.scan_date == str(scan_dt),
                )
            )).scalar_one_or_none()

            if existing is None:
                fr = ForwardReturn(
                    ticker=ticker,
                    scan_date=str(scan_dt),
                    conviction=pick.conviction,
                    setup_type=pick.setup_type,
                    direction=pick.direction,
                    entry_price=pick.entry_high,
                    macro_regime=None,
                )
                session.add(fr)
                await session.flush()
                existing = fr

            try:
                df = await get_prices(ticker, timeframe="1d", days=60)
                if df.empty:
                    continue

                # Align to scan_date
                if not isinstance(df.index, pd.DatetimeIndex):
                    df.index = pd.to_datetime(df.index)
                df = df[df.index.date >= scan_dt]
                if len(df) < 2:
                    continue

                entry = float(df["close"].iloc[0])  # T+0 close as entry reference
                existing.entry_price = existing.entry_price or entry

                # T+5 return
                if len(df) >= 6 and today >= _trading_day_offset(scan_dt, 5):
                    close_5d = float(df["close"].iloc[5])
                    ret_5d = (close_5d / entry) - 1.0
                    if pick.direction == "short":
                        ret_5d = -ret_5d
                    existing.return_5d = round(ret_5d, 5)
                    # Hit target/stop checks using intraday high/low
                    if pick.stop and pick.target:
                        highs = df["high"].iloc[1:6].values
                        lows  = df["low"].iloc[1:6].values
                        if pick.direction == "long":
                            existing.hit_target_5d = bool(any(h >= pick.target for h in highs))
                            existing.hit_stop_5d   = bool(any(l <= pick.stop  for l in lows))
                        else:
                            existing.hit_target_5d = bool(any(l <= pick.target for l in lows))
                            existing.hit_stop_5d   = bool(any(h >= pick.stop   for h in highs))

                # T+20 return
                if len(df) >= 21 and today >= _trading_day_offset(scan_dt, 20):
                    close_20d = float(df["close"].iloc[20])
                    ret_20d = (close_20d / entry) - 1.0
                    if pick.direction == "short":
                        ret_20d = -ret_20d
                    existing.return_20d = round(ret_20d, 5)
                    if pick.stop and pick.target:
                        highs = df["high"].iloc[1:21].values
                        lows  = df["low"].iloc[1:21].values
                        if pick.direction == "long":
                            existing.hit_target_20d = bool(any(h >= pick.target for h in highs))
                            existing.hit_stop_20d   = bool(any(l <= pick.stop   for l in lows))
                        else:
                            existing.hit_target_20d = bool(any(l <= pick.target for l in lows))
                            existing.hit_stop_20d   = bool(any(h >= pick.stop   for h in highs))

                updated += 1
                log.info("forward_return_updated", ticker=ticker, scan_date=str(scan_dt),
                         r5d=existing.return_5d, r20d=existing.return_20d)

            except Exception as exc:
                log.warning("forward_return_failed", ticker=ticker, error=str(exc))

        await session.commit()
        return updated


async def populate_recent(lookback_days: int = 30) -> None:
    """Populate forward returns for all scan dates in the last N days."""
    today = date.today()
    total = 0
    for offset in range(lookback_days):
        scan_dt = today - timedelta(days=offset)
        n = await populate_forward_returns_for_date(scan_dt)
        total += n
    log.info("forward_returns_complete", total_updated=total, lookback_days=lookback_days)


if __name__ == "__main__":
    asyncio.run(populate_recent())
