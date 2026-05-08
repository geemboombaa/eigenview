from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf
from fastapi import APIRouter
from pydantic import BaseModel

from eigenview.factors.technical import score_technical

router = APIRouter()

# ── Universes ─────────────────────────────────────────────────────────────────

_NDX100 = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
    "NFLX", "TMUS", "AMD", "ADBE", "QCOM", "AMAT", "INTU", "CSCO", "CMCSA", "BKNG",
    "VRTX", "REGN", "GILD", "MDLZ", "ADP", "PANW", "ABNB", "LRCX", "MCHP", "CRWD",
    "MU", "SNPS", "CDNS", "CTAS", "KLAC", "FTNT", "ROP", "ORLY", "PCAR", "PAYX",
    "CPRT", "EXC", "CHTR", "CEG", "MRVL", "ROST", "BIIB", "KDP", "IDXX", "FAST",
    "VRSK", "ODFL", "DDOG", "ANSS", "DLTR", "EA", "WDAY", "MRNA", "ZS", "TEAM",
    "NXPI", "PYPL", "TTWO", "ULTA", "VEEV", "ON", "MNST", "MPWR", "TSCO", "TTD",
    "CSGP", "DXCM", "ENPH", "ILMN", "MELI", "ASML", "CDW", "PDD", "FANG", "SIRI",
    "EBAY", "MTCH", "APP", "HOOD", "COIN", "ARM", "SMCI", "MSTR", "PLTR", "RIVN",
    "LCID", "ZM", "DOCU", "OKTA", "SNOW", "DKNG", "RBLX", "PINS", "SNAP", "UBER",
]

_SP500_EXTRA = [
    "BRK-B", "JPM", "JNJ", "V", "UNH", "XOM", "WMT", "MA", "PG", "HD",
    "CVX", "ABBV", "LLY", "BAC", "KO", "PFE", "MRK", "DIS", "WFC", "PEP",
    "TMO", "ABT", "DHR", "MCD", "NEE", "ACN", "VZ", "TXN", "BMY",
    "AMGN", "RTX", "PM", "SCHW", "HON", "UPS", "MS", "GS", "BLK", "LOW",
    "CAT", "AXP", "SPGI", "GE", "T", "DE", "SYK", "ISRG", "MDT",
    "AMT", "SO", "CI", "CVS", "TJX", "SBUX", "PLD", "NOW", "CB",
    "CL", "ELV", "ZTS", "ICE", "NOC", "USB", "TGT", "CME",
    "PNC", "F", "GM", "NKE", "HUM", "SLB", "COF", "D", "EQIX", "WM",
    "ETN", "ITW", "MMM", "APD", "GD", "HCA", "AON", "WELL", "FDX", "NSC",
    "EMR", "MCO", "PSA", "TRV", "ALL", "DD",
    "AFL", "OXY", "SHW", "BK", "GIS", "MET", "ADM", "HSY",
    "SPG", "FICO", "DUK", "AEP", "PEG", "STZ", "EXR", "YUM", "KMB",
    "SPY", "QQQ", "IWM", "GLD", "TLT", "IYR", "XLF", "XLE", "XLK", "XLV",
]

_SP500 = list(dict.fromkeys([*_NDX100, *_SP500_EXTRA]))

_DEFAULT = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "AVGO", "AMD",
    "TSLA", "NFLX", "PLTR", "COIN", "ORCL",
    "JPM", "GS", "BAC",
    "LLY", "UNH", "JNJ",
    "XOM", "CVX",
    "SPY", "QQQ", "IWM", "GLD", "TLT",
    "MCD", "SBUX", "NKE", "HOOD",
]

_TEST5 = ["NVDA", "AAPL", "TSLA", "META", "AMD"]

UNIVERSES: dict[str, list[str]] = {
    "default": _DEFAULT,
    "ndx100": _NDX100,
    "sp500": _SP500,
    "test5": _TEST5,
}

# ── Global state ──────────────────────────────────────────────────────────────

_state: dict[str, Any] = {
    "running": False, "results": [], "scanned_at": None,
    "error": None, "tickers_scanned": 0, "tickers_total": 0, "message": "idle",
}
_bg_tasks: set[asyncio.Task] = set()  # strong refs — prevents GC


# ── Batch price download (single yfinance call for all tickers) ────────────────

async def _batch_download(tickers: list[str], days: int = 90) -> dict[str, pd.DataFrame]:
    loop = asyncio.get_event_loop()

    def _dl() -> pd.DataFrame:
        return yf.download(
            tickers, period=f"{days}d", interval="1d",
            auto_adjust=True, progress=False, threads=True,
        )

    raw: pd.DataFrame = await loop.run_in_executor(None, _dl)
    if raw is None or raw.empty:
        return {}

    out: dict[str, pd.DataFrame] = {}
    if isinstance(raw.columns, pd.MultiIndex):
        for t in tickers:
            try:
                df = raw.xs(t, axis=1, level=1).copy()
                df.columns = df.columns.str.lower()
                df.index.name = "date"
                df = df.dropna(subset=["close"])
                if len(df) >= 30:
                    out[t] = df
            except Exception:
                pass
    else:
        # Single ticker: columns are flat
        df = raw.copy()
        df.columns = df.columns.str.lower()
        df.index.name = "date"
        df = df.dropna(subset=["close"])
        if len(df) >= 30 and tickers:
            out[tickers[0]] = df
    return out


# ── Options volume ─────────────────────────────────────────────────────────────

async def _options_vol(ticker: str) -> dict:
    loop = asyncio.get_event_loop()

    def _dl() -> dict:
        try:
            tkr = yf.Ticker(ticker)
            expiries = tkr.options
            if not expiries:
                return {}
            chain = tkr.option_chain(expiries[0])
            call_vol = int(chain.calls["volume"].fillna(0).sum())
            put_vol  = int(chain.puts["volume"].fillna(0).sum())
            pcr      = round(put_vol / call_vol, 2) if call_vol > 0 else None
            return {"call_vol": call_vol, "put_vol": put_vol, "pcr": pcr, "opt_expiry": expiries[0]}
        except Exception:
            return {}

    try:
        return await asyncio.wait_for(loop.run_in_executor(None, _dl), timeout=10.0)
    except Exception:
        return {}


# ── TA score (sync, called in executor) ───────────────────────────────────────

def _score_one(ticker: str, df: pd.DataFrame) -> dict:
    try:
        spot    = float(df["close"].iloc[-1])
        avg_vol = float(df["volume"].iloc[-20:].mean()) if "volume" in df.columns else 0.0
        r       = score_technical(df, ticker)
        return {
            "ticker": ticker, "spot": round(spot, 2),
            "avg_vol_m": round(avg_vol / 1_000_000, 2),
            "pattern": r.label, "firing": r.firing,
            "confidence": round(r.strength * 100, 1),
            "direction": r.detail.get("direction", "long"),
            "weekly_state": r.detail.get("weekly_state", "NEUTRAL"),
            "trend": r.detail.get("trend", "unknown"),
            "adx": r.detail.get("adx"), "rsi": r.detail.get("rsi"),
            "vol_ratio": r.detail.get("vol_ratio"),
            "vol_character": r.detail.get("vol_character"),
            "swing_high": r.detail.get("swing_high"),
            "swing_low": r.detail.get("swing_low"),
            "narrative": r.narrative,
            "call_vol": None, "put_vol": None, "pcr": None,
        }
    except Exception as exc:
        return {
            "ticker": ticker, "pattern": "ERROR", "firing": False,
            "confidence": 0, "direction": "—", "weekly_state": "—",
            "trend": "—", "adx": None, "rsi": None, "vol_ratio": None,
            "vol_character": "—", "spot": None, "avg_vol_m": 0,
            "narrative": str(exc)[:120],
            "call_vol": None, "put_vol": None, "pcr": None,
        }


# ── Core scan coroutine ────────────────────────────────────────────────────────

async def _run_scan(ticker_list: list[str], min_volume_m: float, fetch_options: bool) -> None:
    global _state
    try:
        # Step 1: batch price download
        _state["message"] = f"Downloading prices for {len(ticker_list)} tickers…"
        price_map = await _batch_download(ticker_list)
        _state["message"] = f"Downloaded {len(price_map)} tickers. Filtering by volume…"

        # Step 2: volume filter
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

        # Step 3: TA scoring in executor (CPU-bound)
        loop = asyncio.get_event_loop()
        ta_sem = asyncio.Semaphore(8)

        async def _score_async(t: str, df: pd.DataFrame) -> dict:
            async with ta_sem:
                r = await loop.run_in_executor(None, _score_one, t, df)
                _state["tickers_scanned"] += 1
                _state["message"] = f"TA scanning… {_state['tickers_scanned']}/{len(filtered)}"
                return r

        results: list[dict] = list(await asyncio.gather(
            *[_score_async(t, df) for t, df in price_map.items()]
        ))

        # Step 4: options volume (optional)
        if fetch_options and filtered:
            _state["message"] = f"Fetching options volume for {len(filtered)} tickers…"
            opt_sem = asyncio.Semaphore(8)

            async def _opt_bounded(t: str) -> tuple[str, dict]:
                async with opt_sem:
                    return t, await _options_vol(t)

            opt_data = dict(await asyncio.gather(*[_opt_bounded(t) for t in filtered]))
            for r in results:
                opts = opt_data.get(r["ticker"], {})
                r["call_vol"]   = opts.get("call_vol")
                r["put_vol"]    = opts.get("put_vol")
                r["pcr"]        = opts.get("pcr")

        # Step 5: sort
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


# ── API endpoints ─────────────────────────────────────────────────────────────

class TaScanRequest(BaseModel):
    tickers: list[str] | None = None
    universe: str | None = None
    min_volume_m: float = 1.0
    fetch_options: bool = True


@router.post("/ta-scan")
async def start_ta_scan(req: TaScanRequest | None = None) -> dict:
    global _state
    if _state["running"]:
        return {"status": "already_running"}

    if req is None:
        req = TaScanRequest()

    if req.tickers:
        ticker_list = [t.strip().upper() for t in req.tickers if t.strip()]
    elif req.universe and req.universe in UNIVERSES:
        ticker_list = UNIVERSES[req.universe]
    else:
        ticker_list = _DEFAULT

    _state = {
        "running": True, "results": [], "scanned_at": None, "error": None,
        "tickers_scanned": 0, "tickers_total": len(ticker_list),
        "message": f"Starting scan for {len(ticker_list)} tickers…",
    }

    task = asyncio.create_task(_run_scan(ticker_list, req.min_volume_m, req.fetch_options))
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)  # auto-cleanup; no GC risk during run

    return {"status": "started", "count": len(ticker_list)}


@router.get("/ta-scan/results")
async def get_ta_scan_results() -> dict:
    return _state


@router.get("/ta-scan/universes")
async def list_universes() -> dict:
    return {k: len(v) for k, v in UNIVERSES.items()}
