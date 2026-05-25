from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import structlog
from sqlalchemy import func, select

from eigenview.data.storage import AsyncSessionLocal, Chain

log = structlog.get_logger(__name__)

_EMPTY_DF = pd.DataFrame(
    columns=["strike", "expiry", "bid", "ask", "volume", "oi", "iv", "delta", "gamma"]
)


def _compute_iv_rank(calls_df: pd.DataFrame) -> float:
    """Rough IV rank from current chain median IV vs a simple range."""
    if calls_df.empty or "iv" not in calls_df.columns:
        return 0.0
    ivs = calls_df["iv"].dropna()
    if ivs.empty:
        return 0.0
    current_iv = float(ivs.median())
    return float(np.clip(current_iv, 0.0, 1.0))


def _rows_to_df(rows: list[Chain]) -> pd.DataFrame:
    if not rows:
        return _EMPTY_DF.copy()
    return pd.DataFrame([
        {
            "strike": r.strike, "expiry": r.expiry,
            "bid": r.bid, "ask": r.ask, "volume": r.volume,
            "oi": r.oi, "iv": r.iv, "delta": r.delta, "gamma": r.gamma,
        }
        for r in rows
    ])


async def fetch_chain(ticker: str) -> dict[str, pd.DataFrame | float]:
    """Read options chain from DB — latest available snapshot.

    Data is loaded externally via scripts/databento_load.py.
    Returns empty DataFrames (not an error) if no snapshot found.
    """
    async with AsyncSessionLocal() as session:
        latest_row = await session.execute(
            select(func.max(Chain.snapshot_date)).where(Chain.ticker == ticker.upper())
        )
        snap_date = latest_row.scalar()

        if snap_date is None:
            log.warning("fetch_chain.no_snapshot", ticker=ticker)
            return {"calls": _EMPTY_DF.copy(), "puts": _EMPTY_DF.copy(), "iv_rank": 0.0}

        result = await session.execute(
            select(Chain).where(
                Chain.ticker == ticker.upper(),
                Chain.snapshot_date == snap_date,
            )
        )
        rows = result.scalars().all()

    calls_rows = [r for r in rows if r.call_put == "c"]
    puts_rows = [r for r in rows if r.call_put == "p"]
    calls = _rows_to_df(calls_rows)
    puts = _rows_to_df(puts_rows)
    iv_rank = _compute_iv_rank(calls)

    log.info("fetch_chain.db_hit", ticker=ticker, snap=str(snap_date),
             calls=len(calls), puts=len(puts))
    return {"calls": calls, "puts": puts, "iv_rank": iv_rank}


async def get_chain(
    ticker: str,
    snapshot_date: date | None = None,
) -> dict[str, pd.DataFrame | float]:
    """Read chain from DB. snapshot_date=None uses the latest available snapshot."""
    if snapshot_date is None:
        return await fetch_chain(ticker)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chain).where(
                Chain.ticker == ticker.upper(),
                Chain.snapshot_date == snapshot_date,
            )
        )
        rows = result.scalars().all()

    if not rows:
        log.warning("get_chain.no_snapshot_for_date", ticker=ticker, date=str(snapshot_date))
        return {"calls": _EMPTY_DF.copy(), "puts": _EMPTY_DF.copy(), "iv_rank": 0.0}

    calls_rows = [r for r in rows if r.call_put == "c"]
    puts_rows = [r for r in rows if r.call_put == "p"]
    calls = _rows_to_df(calls_rows)
    puts = _rows_to_df(puts_rows)
    iv_rank = _compute_iv_rank(calls)
    log.info("get_chain.db_hit", ticker=ticker, date=str(snapshot_date),
             calls=len(calls), puts=len(puts))
    return {"calls": calls, "puts": puts, "iv_rank": iv_rank}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _float_or_none(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _int_or_none(val: Any) -> int | None:
    if val is None:
        return None
    try:
        f = float(val)
        if math.isnan(f):
            return None
        return int(f)
    except (TypeError, ValueError):
        return None
