from __future__ import annotations

import asyncio
import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
import structlog
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as upsert
from tenacity import retry, stop_after_attempt, wait_exponential

from eigenview.data.storage import AsyncSessionLocal, Chain

log = structlog.get_logger(__name__)

_sem = asyncio.Semaphore(10)

_EMPTY_DF = pd.DataFrame(
    columns=["strike", "expiry", "bid", "ask", "volume", "oi", "iv", "delta", "gamma"]
)

RISK_FREE_RATE = 0.05


def _get_ticker_data(ticker: str) -> tuple[list[str], float, yf.Ticker]:
    """Blocking: fetch expiry list and spot price."""
    obj = yf.Ticker(ticker)
    expiries = list(obj.options or [])
    hist = obj.history(period="1d")
    spot = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
    return expiries, spot, obj


def _get_option_chain(ticker_obj: yf.Ticker, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    chain = ticker_obj.option_chain(expiry)
    return chain.calls, chain.puts


def _safe_greek(func: Any, flag: str, S: float, K: float, t: float, r: float, sigma: float) -> float | None:
    try:
        val = func(flag, S, K, t, r, sigma)
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return None
        return float(val)
    except Exception:
        return None


def _compute_greeks(df: pd.DataFrame, flag: str, S: float, expiry_date: date) -> pd.DataFrame:
    """Add delta and gamma columns to a calls or puts DataFrame in-place."""
    try:
        from py_vollib.black_scholes.greeks.analytical import delta as bs_delta
        from py_vollib.black_scholes.greeks.analytical import gamma as bs_gamma
    except ImportError:
        log.warning("chains.py_vollib_missing")
        df["delta"] = np.nan
        df["gamma"] = np.nan
        return df

    t = max((expiry_date - date.today()).days / 365.0, 0.001)
    deltas = []
    gammas = []
    for _, row in df.iterrows():
        K = float(row["strike"])
        sigma = float(row["iv"])
        deltas.append(_safe_greek(bs_delta, flag, S, K, t, RISK_FREE_RATE, sigma))
        gammas.append(_safe_greek(bs_gamma, flag, S, K, t, RISK_FREE_RATE, sigma))
    df["delta"] = deltas
    df["gamma"] = gammas
    return df


def _normalise_chain_df(raw: pd.DataFrame, flag: str, S: float, expiry_str: str) -> pd.DataFrame:
    """Rename yfinance columns, filter bad IV, compute Greeks."""
    col_map = {
        "strike": "strike",
        "bid": "bid",
        "ask": "ask",
        "volume": "volume",
        "openInterest": "oi",
        "impliedVolatility": "iv",
    }
    present = {k: v for k, v in col_map.items() if k in raw.columns}
    df = raw.rename(columns=present)[list(present.values())].copy()

    # Ensure all expected columns exist
    for col in ["bid", "ask", "volume", "oi", "iv"]:
        if col not in df.columns:
            df[col] = np.nan

    expiry_date = date.fromisoformat(expiry_str)
    df["expiry"] = expiry_date

    # Filter invalid IV before Greeks
    df = df[df["iv"].notna() & (df["iv"] > 0)].copy()

    if not df.empty and S > 0:
        df = _compute_greeks(df, flag, S, expiry_date)
    else:
        df["delta"] = np.nan
        df["gamma"] = np.nan

    return df[["strike", "expiry", "bid", "ask", "volume", "oi", "iv", "delta", "gamma"]]


def _compute_iv_rank(calls_df: pd.DataFrame) -> float:
    """Rough IV rank from current chain median IV vs a simple range."""
    if calls_df.empty or "iv" not in calls_df.columns:
        return 0.0
    ivs = calls_df["iv"].dropna()
    if ivs.empty:
        return 0.0
    current_iv = float(ivs.median())
    # Without historical IV, return current median as a proxy (0–1 clipped)
    return float(np.clip(current_iv, 0.0, 1.0))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
async def fetch_chain(ticker: str) -> dict[str, pd.DataFrame | float]:
    """Fetch full options chain, compute Greeks, upsert to DB.

    Returns::
        {
            "calls": pd.DataFrame,
            "puts":  pd.DataFrame,
            "iv_rank": float,
        }
    Rows with iv <= 0 or iv NaN are filtered before Greeks are computed.
    """
    log.info("fetch_chain.start", ticker=ticker)

    async with _sem:
        loop = asyncio.get_event_loop()
        expiries, spot, ticker_obj = await loop.run_in_executor(
            None, _get_ticker_data, ticker
        )

    if not expiries:
        log.warning("fetch_chain.no_expiries", ticker=ticker)
        return {"calls": _EMPTY_DF.copy(), "puts": _EMPTY_DF.copy(), "iv_rank": 0.0}

    all_calls: list[pd.DataFrame] = []
    all_puts: list[pd.DataFrame] = []
    today = date.today()

    for expiry_str in expiries:
        try:
            async with _sem:
                loop = asyncio.get_event_loop()
                raw_calls, raw_puts = await loop.run_in_executor(
                    None, _get_option_chain, ticker_obj, expiry_str
                )
        except Exception as exc:
            log.warning("fetch_chain.expiry_error", expiry=expiry_str, error=str(exc))
            continue

        calls_df = _normalise_chain_df(raw_calls, "c", spot, expiry_str)
        puts_df = _normalise_chain_df(raw_puts, "p", spot, expiry_str)
        all_calls.append(calls_df)
        all_puts.append(puts_df)

    calls = pd.concat(all_calls, ignore_index=True) if all_calls else _EMPTY_DF.copy()
    puts = pd.concat(all_puts, ignore_index=True) if all_puts else _EMPTY_DF.copy()
    iv_rank = _compute_iv_rank(calls)

    # Upsert to DB
    rows: list[dict] = []
    for flag, df in [("c", calls), ("p", puts)]:
        for _, row in df.iterrows():
            rows.append(
                {
                    "ticker": ticker.upper(),
                    "snapshot_date": today,
                    "strike": float(row["strike"]),
                    "expiry": row["expiry"],
                    "call_put": flag,
                    "bid": _float_or_none(row.get("bid")),
                    "ask": _float_or_none(row.get("ask")),
                    "volume": _int_or_none(row.get("volume")),
                    "oi": _int_or_none(row.get("oi")),
                    "iv": _float_or_none(row.get("iv")),
                    "delta": _float_or_none(row.get("delta")),
                    "gamma": _float_or_none(row.get("gamma")),
                }
            )

    if rows:
        chunk_size = 500
        async with AsyncSessionLocal() as session:
            for i in range(0, len(rows), chunk_size):
                chunk = rows[i : i + chunk_size]
                stmt = (
                    upsert(Chain)
                    .values(chunk)
                    .on_conflict_do_nothing()
                )
                await session.execute(stmt)
            await session.commit()
        log.info("fetch_chain.upserted", ticker=ticker, rows=len(rows))

    return {"calls": calls, "puts": puts, "iv_rank": iv_rank}


async def get_chain(
    ticker: str,
    snapshot_date: date | None = None,
) -> dict[str, pd.DataFrame | float]:
    """Read chain from DB; fall back to fetch_chain if no rows found for today."""
    snap = snapshot_date or date.today()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chain).where(
                Chain.ticker == ticker.upper(),
                Chain.snapshot_date == snap,
            )
        )
        rows = result.scalars().all()

    if not rows:
        log.info("get_chain.cache_miss", ticker=ticker, date=str(snap))
        return await fetch_chain(ticker)

    calls_rows = [r for r in rows if r.call_put == "c"]
    puts_rows = [r for r in rows if r.call_put == "p"]

    calls = _rows_to_df(calls_rows)
    puts = _rows_to_df(puts_rows)
    iv_rank = _compute_iv_rank(calls)

    log.info("get_chain.cache_hit", ticker=ticker, calls=len(calls), puts=len(puts))
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


def _rows_to_df(rows: list[Chain]) -> pd.DataFrame:
    if not rows:
        return _EMPTY_DF.copy()
    return pd.DataFrame(
        [
            {
                "strike": r.strike,
                "expiry": r.expiry,
                "bid": r.bid,
                "ask": r.ask,
                "volume": r.volume,
                "oi": r.oi,
                "iv": r.iv,
                "delta": r.delta,
                "gamma": r.gamma,
            }
            for r in rows
        ]
    )
