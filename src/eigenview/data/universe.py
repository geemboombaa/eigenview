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


_STATIC_UNIVERSES: dict[str, list[str]] = {
    "test5": ["NVDA", "AAPL", "TSLA", "META", "AMD"],
}


async def get_universe(name: str) -> list[str]:
    if name in _STATIC_UNIVERSES:
        return _STATIC_UNIVERSES[name]

    today = date.today()
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
