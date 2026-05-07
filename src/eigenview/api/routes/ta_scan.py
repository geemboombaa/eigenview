from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from eigenview.data.prices import fetch_prices
from eigenview.factors.technical import score_technical

router = APIRouter()

_DEFAULT_UNIVERSE = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSM", "AVGO", "ORCL", "AMD",
    "TSLA", "NFLX", "SBUX", "NKE", "MCD",
    "JPM", "GS", "BAC",
    "LLY", "UNH", "JNJ",
    "XOM", "CVX",
    "SPY", "QQQ", "IWM", "GLD", "TLT",
    "PLTR", "COIN",
]

_NDX20 = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ORCL", "NFLX",
    "AMD", "ADBE", "QCOM", "COST", "AMAT", "MU", "LRCX", "PANW", "KLAC", "MRVL",
]

_TEST5 = ["NVDA", "AAPL", "TSLA", "META", "AMD"]

UNIVERSES = {
    "default": _DEFAULT_UNIVERSE,
    "ndx20": _NDX20,
    "test5": _TEST5,
}

_state: dict[str, Any] = {
    "running": False,
    "results": [],
    "scanned_at": None,
    "error": None,
    "tickers_scanned": 0,
    "tickers_total": 0,
    "message": "idle",
}


class TaScanRequest(BaseModel):
    tickers: list[str] | None = None
    universe: str | None = None


async def _scan_one(ticker: str) -> dict | None:
    try:
        df = await fetch_prices(ticker, "1d", 90)
        if df is None or df.empty or len(df) < 30:
            return {"ticker": ticker, "pattern": "NO DATA", "firing": False,
                    "confidence": 0, "direction": "—", "weekly_state": "—",
                    "trend": "—", "adx": None, "rsi": None, "vol_ratio": None,
                    "vol_character": "—", "spot": None, "narrative": "Insufficient data"}
        spot = float(df["close"].iloc[-1])
        r = score_technical(df, ticker)
        return {
            "ticker": ticker,
            "spot": round(spot, 2),
            "pattern": r.label,
            "firing": r.firing,
            "confidence": round(r.strength * 100, 1),
            "direction": r.detail.get("direction", "long"),
            "weekly_state": r.detail.get("weekly_state", "NEUTRAL"),
            "trend": r.detail.get("trend", "unknown"),
            "adx": r.detail.get("adx"),
            "rsi": r.detail.get("rsi"),
            "vol_ratio": r.detail.get("vol_ratio"),
            "vol_character": r.detail.get("vol_character"),
            "swing_high": r.detail.get("swing_high"),
            "swing_low": r.detail.get("swing_low"),
            "narrative": r.narrative,
        }
    except Exception as exc:
        return {"ticker": ticker, "pattern": "ERROR", "firing": False,
                "confidence": 0, "direction": "—", "weekly_state": "—",
                "trend": "—", "adx": None, "rsi": None, "vol_ratio": None,
                "vol_character": "—", "spot": None, "narrative": str(exc)[:120]}


@router.post("/ta-scan")
async def start_ta_scan(req: TaScanRequest | None = None) -> dict:
    global _state
    if _state["running"]:
        return {"status": "already_running"}

    if req and req.tickers:
        ticker_list = [t.strip().upper() for t in req.tickers if t.strip()]
    elif req and req.universe and req.universe in UNIVERSES:
        ticker_list = UNIVERSES[req.universe]
    else:
        ticker_list = _DEFAULT_UNIVERSE

    _state = {**_state, "running": True, "results": [], "error": None,
              "tickers_total": len(ticker_list), "tickers_scanned": 0,
              "message": f"Scanning {len(ticker_list)} tickers…"}

    async def _do() -> None:
        global _state
        sem = asyncio.Semaphore(6)

        async def _bounded(t: str) -> dict | None:
            async with sem:
                result = await _scan_one(t)
                _state["tickers_scanned"] += 1
                return result

        raw = await asyncio.gather(*[_bounded(t) for t in ticker_list])
        results = [r for r in raw if r is not None]
        results.sort(key=lambda r: (-(1 if r.get("firing") else 0), -(r.get("confidence") or 0)))

        _state = {
            "running": False,
            "results": results,
            "scanned_at": datetime.now().isoformat(timespec="seconds"),
            "error": None,
            "tickers_scanned": len(ticker_list),
            "tickers_total": len(ticker_list),
            "message": f"Done — {sum(1 for r in results if r.get('firing'))} patterns firing",
        }

    asyncio.create_task(_do())
    return {"status": "started", "count": len(ticker_list)}


@router.get("/ta-scan/results")
async def get_ta_scan_results() -> dict:
    return _state
