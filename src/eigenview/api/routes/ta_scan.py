from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from eigenview.data.storage import AsyncSessionLocal, Chain, Price
from eigenview.factors.technical import score_technical

router = APIRouter()

from eigenview.data.universe import get_universe as _get_universe

_state: dict[str, Any] = {
    "running": False, "results": [], "scanned_at": None,
    "error": None, "tickers_scanned": 0, "tickers_total": 0, "message": "idle",
}
_bg_tasks: set[asyncio.Task] = set()


async def _batch_prices_from_db(tickers: list[str], days: int = 200) -> dict[str, pd.DataFrame]:
    """Read daily OHLCV for all tickers from the prices table."""
    from datetime import timedelta, datetime as dt
    cutoff = (dt.utcnow() - timedelta(days=days)).date()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Price)
            .where(
                Price.ticker.in_([t.upper() for t in tickers]),
                Price.timeframe == "1d",
                Price.date >= cutoff,
            )
            .order_by(Price.date.asc())
        )
        rows = result.scalars().all()

    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r.ticker, []).append({
            "date": r.date, "open": r.open, "high": r.high,
            "low": r.low, "close": r.close, "volume": r.volume,
        })

    result_dfs: dict[str, pd.DataFrame] = {}
    for ticker, row_list in out.items():
        df = pd.DataFrame(row_list)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").dropna(subset=["close"])
        if len(df) >= 30:
            result_dfs[ticker] = df
    return result_dfs


async def _options_vol_from_db(ticker: str) -> dict:
    """Read nearest-expiry options volume from DB chain snapshot."""
    async with AsyncSessionLocal() as session:
        latest = await session.execute(
            select(func.max(Chain.snapshot_date)).where(Chain.ticker == ticker.upper())
        )
        snap_date = latest.scalar()
        if snap_date is None:
            return {}

        rows = (await session.execute(
            select(Chain).where(Chain.ticker == ticker.upper(), Chain.snapshot_date == snap_date)
            .order_by(Chain.expiry.asc())
        )).scalars().all()

    if not rows:
        return {}

    # Use nearest expiry
    nearest_expiry = min(r.expiry for r in rows)
    nearest = [r for r in rows if r.expiry == nearest_expiry]
    call_vol = sum(r.volume or 0 for r in nearest if r.call_put == "c")
    put_vol = sum(r.volume or 0 for r in nearest if r.call_put == "p")
    pcr = round(put_vol / call_vol, 2) if call_vol > 0 else None
    return {"call_vol": call_vol, "put_vol": put_vol, "pcr": pcr, "opt_expiry": str(nearest_expiry)}


def _score_one(ticker: str, df: pd.DataFrame, lookback_bars: int = 10, spy_ret: float | None = None) -> dict:
    try:
        spot = float(df["close"].iloc[-1])
        avg_vol = float(df["volume"].iloc[-20:].mean()) if "volume" in df.columns else 0.0
        n = len(df)
        ticker_20d = float(df["close"].iloc[-1] / df["close"].iloc[-21] - 1) if n >= 21 else None
        rs_vs_spy = round((ticker_20d - spy_ret) * 100, 1) if ticker_20d is not None and spy_ret is not None else None

        best: object = None
        signal_age: int | None = None
        max_back = min(lookback_bars, n - 50)
        for i in range(max(0, max_back) + 1):
            sl = df.iloc[:n - i] if i > 0 else df
            r = score_technical(sl, ticker)
            if r.firing:
                best = r
                signal_age = i
                break

        if best is None:
            best = score_technical(df, ticker)

        return {
            "ticker": ticker, "spot": round(spot, 2),
            "avg_vol_m": round(avg_vol / 1_000_000, 2),
            "pattern": best.label, "firing": best.firing,
            "confidence": round(best.strength * 100, 1),
            "direction": best.detail.get("direction", "long"),
            "weekly_state": best.detail.get("weekly_state", "NEUTRAL"),
            "trend": best.detail.get("trend", "unknown"),
            "adx": best.detail.get("adx"), "rsi": best.detail.get("rsi"),
            "vol_ratio": best.detail.get("vol_ratio"),
            "vol_character": best.detail.get("vol_character"),
            "swing_high": best.detail.get("swing_high"),
            "swing_low": best.detail.get("swing_low"),
            "narrative": best.narrative,
            "signal_age": signal_age,
            "rs_vs_spy": rs_vs_spy,
            "call_vol": None, "put_vol": None, "pcr": None,
        }
    except Exception as exc:
        return {
            "ticker": ticker, "pattern": "ERROR", "firing": False,
            "confidence": 0, "direction": "—", "weekly_state": "—",
            "trend": "—", "adx": None, "rsi": None, "vol_ratio": None,
            "vol_character": "—", "spot": None, "avg_vol_m": 0,
            "narrative": str(exc)[:120],
            "signal_age": None, "rs_vs_spy": None,
            "call_vol": None, "put_vol": None, "pcr": None,
        }


async def _run_scan(ticker_list: list[str], min_volume_m: float, fetch_options: bool, lookback_bars: int = 10) -> None:
    global _state
    try:
        _state["message"] = f"Reading prices for {len(ticker_list)} tickers from DB…"
        price_map = await _batch_prices_from_db(ticker_list, days=200)
        _state["message"] = f"Loaded {len(price_map)} tickers. Filtering by volume…"

        if min_volume_m > 0:
            price_map = {
                t: df for t, df in price_map.items()
                if "volume" in df.columns
                and float(df["volume"].iloc[-20:].mean()) >= min_volume_m * 1_000_000
            }

        filtered = list(price_map.keys())
        _state["message"] = f"{len(filtered)} pass filter. Running TA…"
        _state["tickers_total"] = len(filtered)
        _state["tickers_scanned"] = 0

        spy_df = price_map.get("SPY")
        spy_ret: float | None = None
        if spy_df is not None and len(spy_df) >= 21:
            spy_ret = float(spy_df["close"].iloc[-1] / spy_df["close"].iloc[-21] - 1)

        loop = asyncio.get_event_loop()
        ta_sem = asyncio.Semaphore(8)

        async def _score_async(t: str, df: pd.DataFrame) -> dict:
            async with ta_sem:
                r = await loop.run_in_executor(None, _score_one, t, df, lookback_bars, spy_ret)
                _state["tickers_scanned"] += 1
                _state["message"] = f"TA scanning… {_state['tickers_scanned']}/{len(filtered)}"
                return r

        results: list[dict] = list(await asyncio.gather(
            *[_score_async(t, df) for t, df in price_map.items()]
        ))

        if fetch_options and filtered:
            _state["message"] = f"Fetching options volume for {len(filtered)} tickers from DB…"
            opt_sem = asyncio.Semaphore(8)

            async def _opt_bounded(t: str) -> tuple[str, dict]:
                async with opt_sem:
                    return t, await _options_vol_from_db(t)

            opt_data = dict(await asyncio.gather(*[_opt_bounded(t) for t in filtered]))
            for r in results:
                opts = opt_data.get(r["ticker"], {})
                r["call_vol"] = opts.get("call_vol")
                r["put_vol"] = opts.get("put_vol")
                r["pcr"] = opts.get("pcr")

        results.sort(key=lambda r: (-(1 if r.get("firing") else 0), -(r.get("confidence") or 0)))

        firing_n = sum(1 for r in results if r.get("firing"))
        _state = {
            "running": False,
            "results": results,
            "scanned_at": datetime.now().isoformat(timespec="seconds"),
            "error": None,
            "tickers_scanned": len(filtered),
            "tickers_total": len(filtered),
            "message": f"Done — {firing_n} firing / {len(results)} scanned",
        }
    except Exception as exc:
        _state = {
            **_state, "running": False,
            "error": str(exc),
            "message": f"Scan failed: {exc}",
        }


class TaScanRequest(BaseModel):
    tickers: list[str] | None = None
    universe: str | None = None
    min_volume_m: float = 1.0
    fetch_options: bool = True
    lookback_bars: int = 10


@router.post("/ta-scan")
async def start_ta_scan(req: TaScanRequest) -> dict:
    global _state
    if _state["running"]:
        return {"status": "already_running"}

    if req.tickers:
        ticker_list = [t.strip().upper() for t in req.tickers if t.strip()]
    else:
        universe_name = req.universe or "ndx100"
        ticker_list = await _get_universe(universe_name)
        if not ticker_list:
            return {"status": "error", "message": f"Failed to load universe '{universe_name}'"}

    _state = {
        "running": True, "results": [], "scanned_at": None, "error": None,
        "tickers_scanned": 0, "tickers_total": len(ticker_list),
        "message": f"Starting scan for {len(ticker_list)} tickers…",
    }

    task = asyncio.create_task(_run_scan(ticker_list, req.min_volume_m, req.fetch_options, req.lookback_bars))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)

    return {"status": "started", "count": len(ticker_list)}


@router.get("/ta-scan/results")
async def get_ta_scan_results() -> dict:
    return _state


@router.get("/ta-scan/universes")
async def list_universes() -> dict:
    ndx = await _get_universe("ndx100")
    sp5 = await _get_universe("sp500")
    return {"ndx100": len(ndx), "sp500": len(sp5)}
