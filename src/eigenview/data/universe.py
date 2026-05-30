from __future__ import annotations

import asyncio
from datetime import date

import io

import pandas as pd
import requests
import structlog

log = structlog.get_logger(__name__)

_cache: dict[str, tuple[date, list[str]]] = {}
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EigenView/1.0)"}


def _read_wiki(url: str) -> list[pd.DataFrame]:
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    return pd.read_html(io.StringIO(resp.text))


def _fetch_ndx100() -> list[str]:
    try:
        tables = _read_wiki("https://en.wikipedia.org/wiki/Nasdaq-100")
        for df in tables:
            if "Ticker" in df.columns:
                tickers = df["Ticker"].dropna().str.strip().str.replace(r"\[.*\]", "", regex=True).tolist()
                result = [t for t in tickers if t and 1 < len(t) <= 6]
                if len(result) > 50:
                    return result
        return []
    except Exception as exc:
        log.warning("universe.ndx100_fetch_failed", error=str(exc))
        return []


def _fetch_sp500() -> list[str]:
    try:
        tables = _read_wiki("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        for df in tables:
            if "Symbol" in df.columns:
                tickers = df["Symbol"].dropna().str.strip().str.replace(r"\[.*\]", "", regex=True).str.replace(".", "-", regex=False).tolist()
                result = [t for t in tickers if t and 1 < len(t) <= 6]
                if len(result) > 400:
                    return result
        return []
    except Exception as exc:
        log.warning("universe.sp500_fetch_failed", error=str(exc))
        return []


async def get_universe(name: str) -> list[str]:
    today = date.today()
    if name == "both":
        ndx, sp = await get_index_lists()
        return sorted(set(ndx) | set(sp))

    cached = _cache.get(name)
    if cached and cached[0] == today and cached[1]:
        return cached[1]

    loop = asyncio.get_event_loop()
    if name == "ndx100":
        tickers = await loop.run_in_executor(None, _fetch_ndx100)
    elif name == "sp500":
        tickers = await loop.run_in_executor(None, _fetch_sp500)
    else:
        tickers = []

    if tickers:
        _cache[name] = (today, tickers)
        log.info("universe.loaded", name=name, count=len(tickers))
    return tickers


async def get_index_lists() -> tuple[list[str], list[str]]:
    """Return (ndx100, sp500) member lists from the already-wired source.

    Used both to build the 'both' scan universe and to tag index membership.
    No new data source — same lists the scanner already uses.
    """
    ndx = await get_universe("ndx100")
    sp = await get_universe("sp500")
    return ndx, sp


async def select_download_universe(session) -> tuple[list[str], dict]:
    """Filter-FIRST: from NDX∪SP500, keep only tradeable names using data ALREADY in the
    DB, so the download pulls only what's needed (not download-everything-then-filter).

    Filters (thresholds in config, each with a documented reason):
      - ATR(14) > download_min_atr            (from daily prices — too-quiet names dropped)
      - no earnings within blackout days      (from catalysts — event risk)
      - aggregate latest-snapshot OI >= dormant_min_ticker_oi  (liquidity proxy; the option
        volume column is ~85% null in Databento OPRA stats, so OI is the robust proxy. The
        download_options_volume_min gate is applied too, but only where volume is populated.)

    Returns (sorted keep-list, stats dict).
    """
    import numpy as np
    from collections import defaultdict
    from sqlalchemy import select

    from eigenview.config import settings
    from eigenview.data.storage import Catalyst, Price

    ndx, sp = await get_index_lists()
    universe = set(ndx) | set(sp)

    # ATR(14) from daily prices
    rows = (await session.execute(
        select(Price.ticker, Price.high, Price.low, Price.close)
        .where(Price.timeframe == "1d").order_by(Price.ticker, Price.date)
    )).all()
    H, L, C = defaultdict(list), defaultdict(list), defaultdict(list)
    for t, h, l, c in rows:
        H[t].append(h); L[t].append(l); C[t].append(c)
    atr_pass = set()
    for t in H:
        h = np.array(H[t][-20:]); l = np.array(L[t][-20:]); c = np.array(C[t][-20:])
        if len(c) < 15:
            continue
        tr = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
        if tr[-14:].mean() > settings.download_min_atr:
            atr_pass.add(t)

    # Earnings within blackout window
    cats = (await session.execute(
        select(Catalyst.ticker, Catalyst.event_type, Catalyst.days_from_now)
    )).all()
    earn_soon = {
        t for t, et, dfn in cats
        if et and "earn" in et.lower() and dfn is not None
        and 0 < dfn <= settings.download_earnings_blackout_days
    }

    # Narrow by the cheap SQL filters FIRST, then probe liquidity live on the survivors
    # (fewer Databento calls). OI + volume MUST come from source, not the stale SQL dump.
    candidates = sorted((universe & atr_pass) - earn_soon)

    import os
    import sys

    scripts_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
    )
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import databento as _db
    from databento_load import load_key, probe_liquidity

    client = _db.Historical(load_key())
    loop = asyncio.get_event_loop()
    liq = await asyncio.wait_for(
        loop.run_in_executor(None, lambda: probe_liquidity(client, candidates)),
        timeout=600.0,
    )

    min_oi = settings.dormant_min_ticker_oi
    min_vol = settings.download_options_volume_min
    keep = sorted(
        t for t in candidates
        if liq.get(t, (0, 0))[0] >= min_oi and liq.get(t, (0, 0))[1] >= min_vol
    )
    oi_only = [t for t in candidates if liq.get(t, (0, 0))[0] >= min_oi]
    stats = {
        "universe": len(universe),
        "atr_pass": len(universe & atr_pass),
        "earnings_excluded": len(earn_soon & universe),
        "candidates_probed": len(candidates),
        "oi_pass_live": len(oi_only),
        "keep": len(keep),
        "min_oi": min_oi,
        "min_vol": min_vol,
    }
    log.info("download_universe.selected", **stats)
    return keep, stats
