"""
Parallel DB population: prices (365d), chains (today), catalysts, macro, news (7d).
Covers S&P 500 + NASDAQ-100. Concurrent fetching via asyncio.Semaphore.

Usage: uv run python scripts/populate_db.py
"""

from __future__ import annotations

import asyncio
import sys
import time
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import httpx
import pandas as pd
import requests

from eigenview.data.storage import create_tables, AsyncSessionLocal
from eigenview.data.prices import fetch_prices
from eigenview.data.chains import fetch_chain
from eigenview.data.calendar import get_catalysts
from eigenview.data.macro import fetch_macro
from sqlalchemy import text


_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
}


# ---------------------------------------------------------------------------
# Ticker lists
# ---------------------------------------------------------------------------

def get_sp500() -> list[str]:
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
            headers=_HEADERS, timeout=20
        )
        resp.raise_for_status()
        df = pd.read_html(StringIO(resp.text))[0]
        return df["Symbol"].str.replace(".", "-", regex=False).tolist()
    except Exception as e:
        print(f"  [WARN] SP500 fetch failed: {e}")
        return []


def get_ndx100() -> list[str]:
    try:
        resp = requests.get(
            "https://en.wikipedia.org/wiki/Nasdaq-100",
            headers=_HEADERS, timeout=20
        )
        resp.raise_for_status()
        tables = pd.read_html(StringIO(resp.text))
        for t in tables:
            for col in t.columns:
                if str(col).lower() in ("ticker", "symbol"):
                    vals = t[col].dropna().str.replace(".", "-", regex=False).tolist()
                    if len(vals) > 50:
                        return vals
    except Exception as e:
        print(f"  [WARN] NDX100 fetch failed: {e}")
    return []


# ---------------------------------------------------------------------------
# News via Finnhub only (AV = 25/day limit — not usable for bulk)
# ---------------------------------------------------------------------------

async def _fetch_news_finnhub_only(ticker: str, lookback_days: int = 7) -> int:
    """Fetch news from Finnhub only, skip AV rate-limited endpoint."""
    from datetime import datetime, timedelta, timezone
    from eigenview.data.news import _fetch_finnhub, _url_hash
    from eigenview.data.storage import AsyncSessionLocal, NewsItem
    from sqlalchemy.dialects.sqlite import insert as upsert

    try:
        async with httpx.AsyncClient() as client:
            articles = await _fetch_finnhub(client, ticker, lookback_days)
        if not articles:
            return 0
        rows = [
            {
                "ticker": a["ticker"],
                "headline": a["headline"],
                "summary": a["summary"] or None,
                "url_hash": a["url_hash"],
                "source": a["source"],
                "timestamp": a["timestamp"].replace(tzinfo=None) if a["timestamp"] else None,
            }
            for a in articles
        ]
        async with AsyncSessionLocal() as session:
            stmt = upsert(NewsItem).values(rows).on_conflict_do_nothing()
            await session.execute(stmt)
            await session.commit()
        return len(rows)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Parallel runners
# ---------------------------------------------------------------------------

async def run_parallel(
    label: str,
    tickers: list[str],
    coro_fn,
    concurrency: int,
    delay: float = 0.0,
) -> tuple[int, int]:
    """Run coro_fn(ticker) for all tickers with bounded concurrency."""
    sem = asyncio.Semaphore(concurrency)
    ok = 0
    fail = 0
    done = 0
    total = len(tickers)
    lock = asyncio.Lock()

    async def worker(ticker: str) -> None:
        nonlocal ok, fail, done
        async with sem:
            if delay:
                await asyncio.sleep(delay)
            try:
                await coro_fn(ticker)
                async with lock:
                    ok += 1
            except Exception:
                async with lock:
                    fail += 1
            async with lock:
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"  {label}: {done}/{total} (ok={ok} fail={fail})")

    await asyncio.gather(*[worker(t) for t in tickers])
    return ok, fail


# ---------------------------------------------------------------------------
# Row counts
# ---------------------------------------------------------------------------

async def print_counts() -> None:
    tables = [
        "prices", "chains", "news", "catalysts", "macro_daily", "cot_weekly",
        "picks", "signal_triggers", "factor_scores", "forward_returns", "dormant_bets",
    ]
    print("\n[DB COUNTS]")
    async with AsyncSessionLocal() as session:
        for t in tables:
            try:
                r = await session.execute(text(f'SELECT COUNT(*) FROM "{t}"'))
                # distinct tickers where applicable
                try:
                    r2 = await session.execute(text(f'SELECT COUNT(DISTINCT ticker) FROM "{t}"'))
                    n_tickers = r2.scalar()
                    print(f"  {t}: {r.scalar():,} rows | {n_tickers} tickers")
                except Exception:
                    print(f"  {t}: {r.scalar():,} rows")
            except Exception as e:
                print(f"  {t}: (error - {e})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    t0 = time.time()
    print("=== EigenView Parallel DB Population ===")

    print("\n[1/6] Creating tables...")
    await create_tables()

    print("\n[2/6] Fetching ticker lists...")
    sp500 = get_sp500()
    ndx100 = get_ndx100()
    tickers = sorted(set(sp500 + ndx100))
    print(f"  SP500={len(sp500)} NDX100={len(ndx100)} combined={len(tickers)}")
    if not tickers:
        print("[ERROR] No tickers — check network")
        return

    # --- PRICES: 50 concurrent --- (yfinance handles parallel fine)
    print(f"\n[3/6] PRICES: 365d for {len(tickers)} tickers (50 concurrent)...")
    ok, fail = await run_parallel(
        "prices", tickers,
        lambda t: fetch_prices(t, "1d", 365),
        concurrency=50,
    )
    print(f"  PRICES done: ok={ok} fail={fail} | elapsed={time.time()-t0:.0f}s")

    # --- CATALYSTS: 30 concurrent ---
    print(f"\n[4/6] CATALYSTS: {len(tickers)} tickers (30 concurrent)...")
    ok, fail = await run_parallel(
        "catalysts", tickers,
        get_catalysts,
        concurrency=30,
    )
    print(f"  CATALYSTS done: ok={ok} fail={fail} | elapsed={time.time()-t0:.0f}s")

    # --- MACRO: single call ---
    print("\n[5/6] MACRO: DIX/GEX/VIX/COT...")
    try:
        result = await fetch_macro()
        populated = [k for k, v in result.items() if v is not None]
        print(f"  MACRO done: {populated}")
    except Exception as e:
        print(f"  MACRO failed: {e}")

    # --- CHAINS: 20 concurrent --- (options API tolerates this)
    print(f"\n[6a/7] CHAINS: {len(tickers)} tickers (20 concurrent)...")
    ok, fail = await run_parallel(
        "chains", tickers,
        fetch_chain,
        concurrency=20,
    )
    print(f"  CHAINS done: ok={ok} fail={fail} | elapsed={time.time()-t0:.0f}s")

    # --- NEWS: 10 concurrent, Finnhub only (skip AV 25/day limit) ---
    print(f"\n[6b/7] NEWS: {len(tickers)} tickers (10 concurrent, Finnhub only)...")
    ok, fail = await run_parallel(
        "news", tickers,
        lambda t: _fetch_news_finnhub_only(t, lookback_days=7),
        concurrency=10,
        delay=0.2,
    )
    print(f"  NEWS done: ok={ok} fail={fail} | elapsed={time.time()-t0:.0f}s")

    await print_counts()
    print(f"\n=== Total time: {(time.time()-t0)/60:.1f} min ===")


if __name__ == "__main__":
    asyncio.run(main())
