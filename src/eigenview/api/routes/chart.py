from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pandas as pd
import pandas_ta as ta  # noqa: F401
from fastapi import APIRouter
from sqlalchemy import select

from eigenview.data.storage import AsyncSessionLocal, Chain, Pick, Price, SignalTrigger

router = APIRouter()

_TF_LIMIT = {"1d": 200, "1h": 60, "1w": 52}
_TF_TIMEFRAME = {"1d": "1d", "1h": "1h", "1w": "1wk"}


def _to_unix(d: date | datetime) -> int:
    if isinstance(d, datetime):
        return int(d.replace(tzinfo=timezone.utc).timestamp())
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return int(dt.timestamp())


@router.get("/chart/{ticker}")
async def get_chart(ticker: str, tf: str = "1d") -> dict:
    ticker = ticker.upper()
    timeframe = _TF_TIMEFRAME.get(tf, "1d")
    limit = _TF_LIMIT.get(tf, 90)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Price)
            .where(Price.ticker == ticker, Price.timeframe == timeframe)
            .order_by(Price.date.asc())
            .limit(limit)
        )
        rows = result.scalars().all()

        # Data loaded externally via databento_load.py — serve what's in DB

        # Get GEX levels from today's pick factors_json
        today = date.today()
        pick_result = await session.execute(
            select(Pick).where(Pick.date == today, Pick.ticker == ticker)
        )
        pick = pick_result.scalar_one_or_none()

        # Fallback: get raw chains for GEX computation if no pick
        chains_for_gex = []
        if not (pick and pick.factors_json):
            chain_result = await session.execute(
                select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == today)
            )
            chains_for_gex = chain_result.scalars().all()

    if not rows:
        return {"candles": [], "indicators": {}, "gex_levels": {}, "pattern": {}}

    # Build DataFrame
    df = pd.DataFrame([
        {"date": r.date, "open": r.open, "high": r.high, "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()

    # Candles
    candles = [
        {
            "time": _to_unix(row.date),
            "open": round(row.open, 4) if row.open else 0,
            "high": round(row.high, 4) if row.high else 0,
            "low": round(row.low, 4) if row.low else 0,
            "close": round(row.close, 4) if row.close else 0,
            "volume": row.volume or 0,
        }
        for row in rows
    ]

    # Indicators
    indicators: dict = {}
    try:
        df.ta.ema(length=21, append=True)
        df.ta.ema(length=50, append=True)
        df.ta.bbands(length=20, append=True)

        def series_to_tv(col: str) -> list[dict]:
            if col not in df.columns:
                return []
            s = df[col].dropna()
            return [{"time": _to_unix(idx.date()), "value": round(float(v), 4)} for idx, v in s.items()]

        indicators["ema21"] = series_to_tv("EMA_21")
        indicators["ema50"] = series_to_tv("EMA_50")
        indicators["bb_upper"] = series_to_tv("BBU_20_2.0")
        indicators["bb_lower"] = series_to_tv("BBL_20_2.0")
    except Exception:
        pass

    # GEX levels from pick factors
    gex_levels: dict = {}
    pattern: dict = {}
    if pick and pick.factors_json:
        try:
            factors = json.loads(pick.factors_json)
            gex_data = factors.get("gex", {})
            detail = gex_data.get("detail", {})
            gex_levels = {
                "call_wall": detail.get("call_wall"),
                "put_wall": detail.get("put_wall"),
                "gamma_flip": detail.get("gamma_flip"),
            }
            ta_data = factors.get("technical", {})
            ta_detail = ta_data.get("detail", {})
            pattern = {
                "type": ta_detail.get("pattern", ta_data.get("label", "")),
                "confidence": ta_detail.get("confidence", ta_data.get("strength", 0)),
            }
        except Exception:
            pass

    # Fallback: compute GEX levels from Chain table
    if not any(gex_levels.values()) and chains_for_gex:
        try:
            from eigenview.factors.gex import score_gex
            spot = float(df["close"].iloc[-1])
            gex_result = score_gex(list(chains_for_gex), spot, ticker)
            d = gex_result.detail
            gex_levels = {
                "call_wall": d.get("call_wall"),
                "put_wall": d.get("put_wall"),
                "gamma_flip": d.get("gamma_flip"),
            }
        except Exception:
            pass

    entry_zone: dict = {}
    stop_price: float | None = None
    if pick:
        entry_zone = {
            "low": float(pick.entry_low) if pick.entry_low else None,
            "high": float(pick.entry_high) if pick.entry_high else None,
        }
        stop_price = float(pick.stop) if pick.stop else None

    return {
        "candles": candles,
        "indicators": indicators,
        "gex_levels": gex_levels,
        "pattern": pattern,
        "entry_zone": entry_zone,
        "stop": stop_price,
    }


@router.get("/chart/{ticker}/signals")
async def get_chart_signals(ticker: str) -> list[dict]:
    ticker = ticker.upper()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SignalTrigger)
            .where(SignalTrigger.ticker == ticker)
            .order_by(SignalTrigger.scan_date.desc())
            .limit(50)
        )
        triggers = result.scalars().all()
    return [
        {
            "scan_date": t.scan_date,
            "setup_type": t.setup_type,
            "direction": t.direction,
            "entry_low": t.entry_low,
            "entry_high": t.entry_high,
            "stop": t.stop,
            "target": t.target,
            "rr_ratio": t.rr_ratio,
            "fired_at": t.fired_at,
        }
        for t in triggers
    ]
