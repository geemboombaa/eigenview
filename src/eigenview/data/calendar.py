from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

import httpx
import pandas as pd
import structlog
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from eigenview.config import settings
from eigenview.data.storage import AsyncSessionLocal, Catalyst

log = structlog.get_logger(__name__)

_sem = asyncio.Semaphore(10)

FINNHUB_EARNINGS_URL = "https://finnhub.io/api/v1/calendar/earnings"


def _yf_calendar(ticker: str) -> list[dict]:
    """Blocking: pull yfinance calendar and return normalised event dicts."""
    obj = yf.Ticker(ticker)
    calendar = obj.calendar  # dict or None
    events: list[dict] = []
    if not calendar:
        return events

    # "Earnings Date" may be a single Timestamp, a list, or absent
    earnings_raw = calendar.get("Earnings Date")
    if earnings_raw is None:
        return events

    if isinstance(earnings_raw, (list, tuple)):
        dates = earnings_raw
    else:
        dates = [earnings_raw]

    today = date.today()
    for d in dates:
        try:
            if isinstance(d, pd.Timestamp):
                ev_date = d.date()
            elif isinstance(d, date):
                ev_date = d
            else:
                ev_date = pd.Timestamp(d).date()
        except Exception:
            continue
        events.append(
            {
                "ticker": ticker.upper(),
                "event_type": "earnings",
                "event_date": ev_date,
                "days_from_now": (ev_date - today).days,
            }
        )
    return events


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(httpx.HTTPError),
)
async def _finnhub_earnings(ticker: str) -> list[dict]:
    """Async: fetch upcoming earnings from Finnhub for next 90 days."""
    today = date.today()
    to_date = today + timedelta(days=90)
    params = {
        "from": today.isoformat(),
        "to": to_date.isoformat(),
        "symbol": ticker.upper(),
        "token": settings.finnhub_key,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(FINNHUB_EARNINGS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    events: list[dict] = []
    earnings_calendar = data.get("earningsCalendar", [])
    if not earnings_calendar:
        return events

    for item in earnings_calendar:
        date_str = item.get("date")
        if not date_str:
            continue
        try:
            ev_date = date.fromisoformat(date_str)
        except ValueError:
            continue
        events.append(
            {
                "ticker": ticker.upper(),
                "event_type": "earnings",
                "event_date": ev_date,
                "days_from_now": (ev_date - date.today()).days,
            }
        )
    return events


def _dedup(events: list[dict]) -> list[dict]:
    """Remove duplicate (ticker, event_type, event_date) entries."""
    seen: set[tuple] = set()
    out: list[dict] = []
    for e in events:
        key = (e["ticker"], e["event_type"], e["event_date"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


async def get_catalysts(ticker: str) -> list[dict]:
    """Fetch and upsert catalyst events for a ticker.

    Combines yfinance calendar and Finnhub earnings endpoint.
    Returns list of dicts with keys: ticker, event_type, event_date, days_from_now.
    """
    log.info("get_catalysts.start", ticker=ticker)

    loop = asyncio.get_event_loop()
    async with _sem:
        yf_events: list[dict] = await loop.run_in_executor(None, _yf_calendar, ticker)

    try:
        fh_events = await _finnhub_earnings(ticker)
    except Exception as exc:
        log.warning("get_catalysts.finnhub_error", ticker=ticker, error=str(exc))
        fh_events = []

    all_events = _dedup(yf_events + fh_events)

    if all_events:
        today = date.today()
        rows = [
            {
                "ticker": e["ticker"],
                "event_type": e["event_type"],
                "event_date": e["event_date"],
                "days_from_now": (e["event_date"] - today).days,
            }
            for e in all_events
        ]
        async with AsyncSessionLocal() as session:
            stmt = (
                pg_insert(Catalyst)
                .values(rows)
                .on_conflict_do_update(
                    index_elements=["ticker", "event_type", "event_date"],
                    set_={"days_from_now": pg_insert(Catalyst).excluded.days_from_now},
                )
            )
            await session.execute(stmt)
            await session.commit()
        log.info("get_catalysts.upserted", ticker=ticker, count=len(rows))

    return all_events


async def days_to_next_catalyst(ticker: str) -> int | None:
    """Return days to the nearest upcoming event within 90 days, or None."""
    today = date.today()
    horizon = today + timedelta(days=90)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Catalyst)
            .where(
                Catalyst.ticker == ticker.upper(),
                Catalyst.event_date >= today,
                Catalyst.event_date <= horizon,
            )
            .order_by(Catalyst.event_date.asc())
        )
        row = result.scalars().first()

    if row is not None:
        return (row.event_date - today).days

    # Nothing in DB — try a live fetch
    events = await get_catalysts(ticker)
    upcoming = [
        e for e in events
        if e["event_date"] >= today and e["event_date"] <= horizon
    ]
    if not upcoming:
        return None

    nearest = min(upcoming, key=lambda e: e["event_date"])
    return (nearest["event_date"] - today).days
