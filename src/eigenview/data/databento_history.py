"""Per-contract daily history from Databento OPRA (OI / volume / close).

Used by the activation engine to diff a watched dormant bet day-over-day from
real history — strike-level, no need to accumulate snapshots over time.
"""
from __future__ import annotations

import datetime as dt

import databento as db
import pandas as pd

from eigenview.config import settings

# OPRA daily-statistics stat_type codes (databento StatType enum)
ST_VOLUME = 6        # CLEARED_VOLUME (quantity)
ST_OPEN_INTEREST = 9  # OI (quantity)
ST_CLOSE = 11        # close price (price)

_DATASET = "OPRA.PILLAR"
_SYM_BATCH = 500


def osi_symbol(ticker: str, expiry: dt.date, call_put: str, strike: float) -> str:
    """Build the OSI option symbol Databento uses, e.g. 'AAPL  270115C00300000'."""
    root = ticker.replace("-", "").replace(".", "")[:6]
    cp = call_put.upper()[:1]
    return f"{root:<6}{expiry.strftime('%y%m%d')}{cp}{int(round(strike * 1000)):08d}"


def _client() -> db.Historical:
    if not settings.databento_key:
        raise RuntimeError("DATABENTO_KEY not configured")
    return db.Historical(settings.databento_key)


def estimate_cost(symbols: list[str], start: str, end: str) -> float:
    c = _client()
    total = 0.0
    for i in range(0, len(symbols), _SYM_BATCH):
        total += c.metadata.get_cost(
            dataset=_DATASET, symbols=symbols[i:i + _SYM_BATCH],
            schema="statistics", start=start, end=end, stype_in="raw_symbol",
        )
    return total


def fetch_statistics(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """Daily OI / volume / close per contract over [start, end].

    Returns long DataFrame: columns [osi_symbol, date, oi, volume, close].
    """
    c = _client()
    frames: list[pd.DataFrame] = []
    for i in range(0, len(symbols), _SYM_BATCH):
        batch = symbols[i:i + _SYM_BATCH]
        sdf = c.timeseries.get_range(
            dataset=_DATASET, schema="statistics", symbols=batch,
            start=start, end=end, stype_in="raw_symbol",
        ).to_df()
        if not sdf.empty:
            frames.append(sdf)
    if not frames:
        return pd.DataFrame(columns=["osi_symbol", "date", "oi", "volume", "close"])

    df = pd.concat(frames, ignore_index=True)
    df["date"] = pd.to_datetime(df["ts_event"]).dt.date

    def _last(stat: int, col: str) -> pd.Series:
        sub = df[df["stat_type"] == stat]
        return sub.groupby(["symbol", "date"])[col].last()

    oi = _last(ST_OPEN_INTEREST, "quantity").rename("oi")
    vol = _last(ST_VOLUME, "quantity").rename("volume")
    close = _last(ST_CLOSE, "price").rename("close")

    out = pd.concat([oi, vol, close], axis=1).reset_index()
    out = out.rename(columns={"symbol": "osi_symbol"})
    return out[["osi_symbol", "date", "oi", "volume", "close"]]
