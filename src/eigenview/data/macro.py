from __future__ import annotations

import asyncio
import csv
import io
import re
from datetime import date, datetime, timedelta, timezone

import httpx
import structlog
import yfinance as yf
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from eigenview.data.storage import AsyncSessionLocal, CotWeekly, MacroDaily

log = structlog.get_logger(__name__)

_SQUEEZE_JSON_URL = "https://squeezemetrics.com/monitor/static/hist.json"
_SQUEEZE_PAGE_URL = "https://squeezemetrics.com/monitor/dix"
_VIXCENTRAL_URL = "https://vixcentral.com"
_COT_URL = "https://www.cftc.gov/dta/public/newcot/deafut.txt"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# DIX / GEX from SqueezeMetrics
# ---------------------------------------------------------------------------


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def _fetch_dix_gex(client: httpx.AsyncClient) -> tuple[float | None, float | None]:
    """Return (dix, gex_index) for today, or (None, None) on failure."""
    # Attempt 1: JSON endpoint
    try:
        resp = await client.get(
            _SQUEEZE_JSON_URL, headers=_BROWSER_HEADERS, timeout=15.0
        )
        if resp.status_code == 200:
            data = resp.json()
            # Format: list of {date, dix, gex} or dict with arrays
            if isinstance(data, list) and data:
                last = data[-1]
                dix = float(last.get("dix") or last.get("DIX", 0)) or None
                gex = float(last.get("gex") or last.get("GEX", 0)) or None
                log.info("fetch_dix.json_ok", dix=dix, gex=gex)
                return dix, gex
            if isinstance(data, dict):
                # {date: [...], dix: [...], gex: [...]}
                dix_list = data.get("dix") or data.get("DIX", [])
                gex_list = data.get("gex") or data.get("GEX", [])
                if dix_list:
                    return float(dix_list[-1]) or None, (
                        float(gex_list[-1]) if gex_list else None
                    )
    except Exception as exc:
        log.warning("fetch_dix.json_failed", error=str(exc))

    # Attempt 2: scrape the monitor page
    try:
        resp = await client.get(
            _SQUEEZE_PAGE_URL, headers=_BROWSER_HEADERS, timeout=15.0
        )
        if resp.status_code == 200:
            html = resp.text
            # Look for JSON blob in script tags
            match = re.search(r"var\s+data\s*=\s*(\[.*?\]);", html, re.DOTALL)
            if match:
                import json  # noqa: PLC0415

                raw = json.loads(match.group(1))
                if raw:
                    last = raw[-1]
                    dix = float(last.get("dix", 0)) or None
                    gex = float(last.get("gex", 0)) or None
                    return dix, gex
            # Fallback: parse visible number from page
            soup = BeautifulSoup(html, "lxml")
            dix_tag = soup.find(id="dix-value") or soup.find(
                class_=re.compile(r"dix", re.I)
            )
            if dix_tag:
                try:
                    dix = float(dix_tag.get_text(strip=True).replace("%", ""))
                    return dix, None
                except ValueError:
                    pass
    except Exception as exc:
        log.warning("fetch_dix.page_failed", error=str(exc))

    log.error("fetch_dix.unavailable")
    return None, None


# ---------------------------------------------------------------------------
# VIX term structure
# ---------------------------------------------------------------------------


def _vix_from_yfinance() -> tuple[float | None, float | None, float | None]:
    """Return (vix_m1, vix_m2, vix_m3) using yfinance spot + crude estimates."""
    try:
        loop_needed = False
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            loop_needed = True

        def _dl() -> float | None:
            try:
                ticker = yf.Ticker("^VIX")
                hist = ticker.history(period="1d")
                if not hist.empty:
                    return float(hist["Close"].iloc[-1])
            except Exception:
                pass
            return None

        if loop_needed:
            spot = _dl()
        else:
            spot = asyncio.get_event_loop().run_in_executor(None, _dl)
            # run_in_executor returns a coroutine here — fall back to sync
            spot = _dl()

        if spot:
            # Conservative term structure approximation when futures unavailable
            m1 = spot
            m2 = round(spot * 1.02, 2)
            m3 = round(spot * 1.04, 2)
            return m1, m2, m3
    except Exception as exc:
        log.warning("fetch_vix.yfinance_failed", error=str(exc))
    return None, None, None


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def _fetch_vix_term(
    client: httpx.AsyncClient,
) -> tuple[float | None, float | None, float | None]:
    """Return (vix_m1, vix_m2, vix_m3). Falls back to yfinance spot."""
    try:
        resp = await client.get(_VIXCENTRAL_URL, headers=_BROWSER_HEADERS, timeout=15.0)
        if resp.status_code == 200:
            html = resp.text
            # Look for embedded JSON
            json_match = re.search(
                r"var\s+contango_data\s*=\s*(\{.*?\});", html, re.DOTALL
            )
            if json_match:
                import json  # noqa: PLC0415

                cdata = json.loads(json_match.group(1))
                futures = cdata.get("futures") or cdata.get("vix_futures", [])
                if len(futures) >= 2:
                    m1 = float(futures[0]) if futures[0] else None
                    m2 = float(futures[1]) if futures[1] else None
                    m3 = float(futures[2]) if len(futures) > 2 and futures[2] else None
                    log.info("fetch_vix.json_ok", m1=m1, m2=m2, m3=m3)
                    return m1, m2, m3

            # Scrape the HTML table
            soup = BeautifulSoup(html, "lxml")
            # VIXCentral typically has a table with month columns
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    # Look for a row with numeric values that look like VIX levels (10-80)
                    floats = []
                    for c in cells:
                        try:
                            v = float(c.replace(",", ""))
                            if 5 < v < 150:
                                floats.append(v)
                        except ValueError:
                            continue
                    if len(floats) >= 3:
                        log.info(
                            "fetch_vix.table_ok",
                            m1=floats[0],
                            m2=floats[1],
                            m3=floats[2],
                        )
                        return floats[0], floats[1], floats[2]
    except Exception as exc:
        log.warning("fetch_vix.scrape_failed", error=str(exc))

    log.info("fetch_vix.falling_back_to_yfinance")
    loop = asyncio.get_event_loop()
    m1, m2, m3 = await loop.run_in_executor(None, _vix_from_yfinance)
    return m1, m2, m3


# ---------------------------------------------------------------------------
# CFTC COT
# ---------------------------------------------------------------------------

_COT_INSTRUMENTS = ("E-MINI S&P 500", "S&P 500 STOCK INDEX", "S&P 500 MINI")


async def _cot_cache_valid() -> tuple[bool, float | None]:
    """Return (is_fresh, cached_net_long_pct). Fresh = latest row < 7 days old."""
    cutoff = date.today() - timedelta(days=7)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CotWeekly)
            .where(CotWeekly.instrument == "ES")
            .order_by(CotWeekly.week_ending.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()

    if row and row.week_ending >= cutoff:
        return True, row.net_long_pct
    return False, None


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def _fetch_cot(client: httpx.AsyncClient) -> float | None:
    """Return net_long_pct for ES from CFTC. Upserts to cot_weekly."""
    is_fresh, cached_pct = await _cot_cache_valid()
    if is_fresh:
        log.info("fetch_cot.cache_hit", net_long_pct=cached_pct)
        return cached_pct

    resp = await client.get(_COT_URL, headers=_BROWSER_HEADERS, timeout=30.0)
    resp.raise_for_status()

    # Try to detect delimiter (comma or semicolon)
    raw_text = resp.text
    delimiter = "," if raw_text.count(",") > raw_text.count(";") else ";"

    reader = csv.DictReader(
        io.StringIO(raw_text), delimiter=delimiter
    )

    best_row: dict | None = None
    for row in reader:
        name_field = (
            row.get("Market_and_Exchange_Names")
            or row.get("Market and Exchange Names", "")
            or ""
        )
        name_upper = name_field.strip().upper()
        if any(inst in name_upper for inst in _COT_INSTRUMENTS):
            best_row = row
            break

    if not best_row:
        log.error("fetch_cot.instrument_not_found")
        return None

    try:
        longs = float(
            (
                best_row.get("Noncommercial_Positions_Long_All")
                or best_row.get("NonComm_Positions_Long_All", "0")
                or "0"
            ).replace(",", "")
        )
        shorts = float(
            (
                best_row.get("Noncommercial_Positions_Short_All")
                or best_row.get("NonComm_Positions_Short_All", "0")
                or "0"
            ).replace(",", "")
        )
    except ValueError as exc:
        log.error("fetch_cot.parse_error", error=str(exc))
        return None

    total = longs + shorts
    if total == 0:
        return None

    net_long_pct = round(longs / total * 100, 2)
    net_long_contracts = int(longs - shorts)

    # Parse week ending date
    date_str = (
        best_row.get("Report_Date_as_MM_DD_YYYY")
        or best_row.get("As_of_Date_In_Form_YYMMDD", "")
        or ""
    ).strip()
    week_ending: date = date.today()
    for fmt in ("%m/%d/%Y", "%y%m%d", "%Y-%m-%d"):
        try:
            week_ending = datetime.strptime(date_str, fmt).date()
            break
        except ValueError:
            continue

    async with AsyncSessionLocal() as session:
        stmt = (
            pg_insert(CotWeekly)
            .values(
                [
                    {
                        "week_ending": week_ending,
                        "instrument": "ES",
                        "net_long_pct": net_long_pct,
                        "net_long_contracts": net_long_contracts,
                    }
                ]
            )
            .on_conflict_do_update(
                index_elements=["week_ending", "instrument"],
                set_={
                    "net_long_pct": net_long_pct,
                    "net_long_contracts": net_long_contracts,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()

    log.info(
        "fetch_cot.done",
        week_ending=str(week_ending),
        net_long_pct=net_long_pct,
    )
    return net_long_pct


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def fetch_macro() -> dict:
    """Fetch DIX/GEX, VIX term structure, and COT. Upserts to macro_daily.

    Returns partial data (None for failed fields) rather than raising.
    """
    today = date.today()

    async with httpx.AsyncClient() as client:
        dix_task = asyncio.create_task(_fetch_dix_gex(client))
        vix_task = asyncio.create_task(_fetch_vix_term(client))
        cot_task = asyncio.create_task(_fetch_cot(client))

        results = await asyncio.gather(
            dix_task, vix_task, cot_task, return_exceptions=True
        )

    dix_result, vix_result, cot_result = results

    dix: float | None = None
    gex_index: float | None = None
    if isinstance(dix_result, tuple):
        dix, gex_index = dix_result
    else:
        log.warning("fetch_macro.dix_failed", error=str(dix_result))

    vix_m1: float | None = None
    vix_m2: float | None = None
    vix_m3: float | None = None
    if isinstance(vix_result, tuple):
        vix_m1, vix_m2, vix_m3 = vix_result
    else:
        log.warning("fetch_macro.vix_failed", error=str(vix_result))

    cot_es_net_long_pct: float | None = None
    if isinstance(cot_result, float):
        cot_es_net_long_pct = cot_result
    elif cot_result is None:
        pass
    else:
        log.warning("fetch_macro.cot_failed", error=str(cot_result))

    vix_contango_pct: float | None = None
    if vix_m1 and vix_m2 and vix_m1 != 0:
        vix_contango_pct = round((vix_m2 - vix_m1) / vix_m1 * 100, 4)

    payload = {
        "date": today,
        "dix": dix,
        "gex_index": gex_index,
        "vix_m1": vix_m1,
        "vix_m2": vix_m2,
        "vix_m3": vix_m3,
        "vix_contango_pct": vix_contango_pct,
        "cot_es_net_long_pct": cot_es_net_long_pct,
    }

    async with AsyncSessionLocal() as session:
        stmt = (
            pg_insert(MacroDaily)
            .values(
                [
                    {
                        k: v
                        for k, v in payload.items()
                        if k != "cot_es_net_long_pct"
                    }
                ]
            )
            .on_conflict_do_update(
                index_elements=["date"],
                set_={
                    "dix": dix,
                    "gex_index": gex_index,
                    "vix_m1": vix_m1,
                    "vix_m2": vix_m2,
                    "vix_m3": vix_m3,
                    "vix_contango_pct": vix_contango_pct,
                },
            )
        )
        await session.execute(stmt)
        await session.commit()

    log.info("fetch_macro.done", date=str(today), **{
        k: v for k, v in payload.items() if k != "date"
    })
    return payload
