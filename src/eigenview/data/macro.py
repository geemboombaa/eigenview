from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as upsert
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from eigenview.config import settings
from eigenview.data.storage import (
    AsyncSessionLocal,
    Chain,
    CotWeekly,
    MacroDaily,
    Price,
    UniverseMembership,
)
from eigenview.factors.gex import score_gex

log = structlog.get_logger(__name__)

# CFTC Legacy Futures-Only COT (Socrata) — replaces the dead newcot/deafut.txt (404).
_COT_SOCRATA_URL = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
# FINRA daily consolidated-NMS short-volume file — free, no key. {date} = YYYYMMDD.
_FINRA_DAILY_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{date}.txt"

# Maps an instrument code → substrings identifying it in CFTC market names.
_COT_MARKET_FILTERS = {
    "ES": "E-MINI S&P 500",
}

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------------------
# VIX term structure — yfinance constant-maturity indices (^VIX, ^VIX3M)
# ---------------------------------------------------------------------------

def _fetch_vix_yf_sync() -> tuple[float | None, float | None, float | None]:
    """Blocking yfinance call. Returns (vix_m1, vix_m2, vix_m3).

    vix_m1 = ^VIX (30-day spot). vix_m2 = ^VIX3M (3-month constant-maturity — the
    standard free contango partner; not the literal 2nd-month VX future). vix_m3 = None.
    """
    import yfinance as yf

    def _last_close(sym: str) -> float | None:
        h = yf.Ticker(sym).history(period="5d")
        if h is None or h.empty or "Close" not in h:
            return None
        closes = h["Close"].dropna()
        if closes.empty:
            return None
        val = float(closes.iloc[-1])
        return val if val > 0 else None

    m1 = _last_close("^VIX")
    m2 = _last_close("^VIX3M")
    return m1, m2, None


async def _fetch_vix_term() -> tuple[float | None, float | None, float | None]:
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _fetch_vix_yf_sync)
    except Exception as exc:
        log.warning("fetch_vix.yf_failed", error=str(exc))
        return None, None, None


# ---------------------------------------------------------------------------
# DIX — reconstructed from FINRA daily short-volume + S&P 500 dollar weights
# ---------------------------------------------------------------------------

async def _sp500_latest_close() -> dict[str, float]:
    """Latest daily close per S&P 500 member, from the prices table."""
    async with AsyncSessionLocal() as session:
        members = (await session.execute(
            select(UniverseMembership.ticker).where(UniverseMembership.in_sp500 == True)  # noqa: E712
        )).scalars().all()
        member_set = {m.upper() for m in members}

        # latest close per ticker (daily timeframe)
        sub = (
            select(Price.ticker, func.max(Price.date).label("md"))
            .where(Price.timeframe == "1d")
            .group_by(Price.ticker)
            .subquery()
        )
        rows = (await session.execute(
            select(Price.ticker, Price.close)
            .join(sub, (Price.ticker == sub.c.ticker) & (Price.date == sub.c.md))
            .where(Price.timeframe == "1d")
        )).all()

    out: dict[str, float] = {}
    for tk, close in rows:
        if tk and close and tk.upper() in member_set:
            out[tk.upper()] = float(close)
    return out


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=20),
)
async def fetch_dix(max_lookback_days: int = 6) -> float | None:
    """Dollar-weighted Dark Index (DIX) over S&P 500 members.

    DPI_i = ShortVolume_i / TotalVolume_i (FINRA daily file). Dollar-weighted:
        DIX = Σ(close_i × ShortVolume_i) / Σ(close_i × TotalVolume_i)
    Returns None when no FINRA file or no member overlap is available.
    """
    closes = await _sp500_latest_close()
    if not closes:
        log.warning("fetch_dix.no_member_closes")
        return None

    async with httpx.AsyncClient(headers=_BROWSER_HEADERS, timeout=30.0) as client:
        text: str | None = None
        for back in range(max_lookback_days + 1):
            d = date.today() - timedelta(days=back)
            url = _FINRA_DAILY_URL.format(date=d.strftime("%Y%m%d"))
            try:
                resp = await client.get(url)
                if resp.status_code == 200 and resp.text:
                    text = resp.text
                    log.info("fetch_dix.file_ok", finra_date=d.isoformat())
                    break
            except httpx.HTTPStatusError:
                continue
        if text is None:
            log.error("fetch_dix.no_file_in_lookback")
            return None

    num = 0.0  # Σ close × short
    den = 0.0  # Σ close × total
    matched = 0
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) < 5 or parts[0] == "Date":
            continue
        sym = parts[1].strip().upper()
        close = closes.get(sym)
        if close is None:
            continue
        try:
            short_v = float(parts[2])
            total_v = float(parts[4])
        except (ValueError, IndexError):
            continue
        if total_v <= 0:
            continue
        num += close * short_v
        den += close * total_v
        matched += 1

    if den <= 0 or matched == 0:
        log.warning("fetch_dix.no_overlap", matched=matched)
        return None

    dix = round(num / den, 4)
    log.info("fetch_dix.done", dix=dix, members_matched=matched)
    return dix


# ---------------------------------------------------------------------------
# GEX — native aggregate of dealer gamma across S&P 500 component chains
# ---------------------------------------------------------------------------

async def compute_market_gex() -> float | None:
    """Σ net dealer GEX across S&P 500 component option chains (latest snapshot in DB).

    Reuses factors.gex.score_gex per ticker. Returns Σ net_gex / 1e9 (billions of $ of
    dealer gamma per 1% move). Sign is the regime signal. Reads existing chains/prices —
    no external pull. Returns None when no chain snapshot exists.
    """
    async with AsyncSessionLocal() as session:
        snap = (await session.execute(select(func.max(Chain.snapshot_date)))).scalar()
        if snap is None:
            return None

        members = (await session.execute(
            select(UniverseMembership.ticker).where(UniverseMembership.in_sp500 == True)  # noqa: E712
        )).scalars().all()
        member_set = {m.upper() for m in members}

        chain_rows = (await session.execute(
            select(Chain).where(Chain.snapshot_date == snap)
        )).scalars().all()

        closes = await _sp500_latest_close()

    by_ticker: dict[str, list] = {}
    for c in chain_rows:
        tk = (c.ticker or "").upper()
        if tk in member_set:
            by_ticker.setdefault(tk, []).append(c)

    if not by_ticker:
        return None

    total_net_gex = 0.0
    scored = 0
    for tk, chains in by_ticker.items():
        spot = closes.get(tk)
        if not spot or spot <= 0:
            continue
        res = score_gex(chains, spot, tk)
        ng = (res.detail or {}).get("net_gex")
        if ng is None:
            continue
        total_net_gex += float(ng)
        scored += 1

    if scored == 0:
        return None

    gex_index = round(total_net_gex / 1e9, 4)
    log.info("compute_market_gex.done", gex_index=gex_index, tickers_scored=scored, snapshot=str(snap))
    return gex_index


# ---------------------------------------------------------------------------
# COT — CFTC Socrata API (Legacy Futures-Only)
# ---------------------------------------------------------------------------

async def _cot_cache_valid(instrument: str) -> tuple[bool, float | None]:
    cutoff = date.today() - timedelta(days=7)
    async with AsyncSessionLocal() as session:
        row = (await session.execute(
            select(CotWeekly)
            .where(CotWeekly.instrument == instrument)
            .order_by(CotWeekly.week_ending.desc())
            .limit(1)
        )).scalar_one_or_none()
    if row and row.week_ending >= cutoff:
        return True, row.net_long_pct
    return False, None


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def _fetch_cot(
    client: httpx.AsyncClient, instrument: str = settings.cot_default_instrument
) -> float | None:
    """Non-commercial net-long % for `instrument` from CFTC Socrata. Upserts cot_weekly."""
    is_fresh, cached = await _cot_cache_valid(instrument)
    if is_fresh:
        log.info("fetch_cot.cache_hit", net_long_pct=cached)
        return cached

    market = _COT_MARKET_FILTERS.get(instrument)
    if not market:
        log.error("fetch_cot.unknown_instrument", instrument=instrument)
        return None

    params = {
        "$where": f"upper(market_and_exchange_names) like '%{market}%'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": "1",
    }
    resp = await client.get(_COT_SOCRATA_URL, params=params, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    if not data:
        log.error("fetch_cot.no_rows")
        return None

    row = data[0]
    try:
        longs = float(row["noncomm_positions_long_all"])
        shorts = float(row["noncomm_positions_short_all"])
    except (KeyError, ValueError) as exc:
        log.error("fetch_cot.parse_error", error=str(exc))
        return None

    total = longs + shorts
    if total <= 0:
        return None
    net_long_pct = round(longs / total * 100, 2)
    net_long_contracts = int(longs - shorts)

    week_ending: date | None = None
    raw_date = (row.get("report_date_as_yyyy_mm_dd") or "").split("T")[0]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            week_ending = datetime.strptime(raw_date, fmt).date()
            break
        except ValueError:
            continue
    if week_ending is None:
        log.error("fetch_cot.date_parse_failed", raw_date=raw_date)
        return None

    async with AsyncSessionLocal() as session:
        ins = upsert(CotWeekly).values([{
            "week_ending": week_ending,
            "instrument": instrument,
            "net_long_pct": net_long_pct,
            "net_long_contracts": net_long_contracts,
        }])
        await session.execute(ins.on_conflict_do_update(
            index_elements=["week_ending", "instrument"],
            set_={"net_long_pct": ins.excluded.net_long_pct,
                  "net_long_contracts": ins.excluded.net_long_contracts},
        ))
        await session.commit()

    log.info("fetch_cot.done", week_ending=str(week_ending), net_long_pct=net_long_pct)
    return net_long_pct


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def fetch_macro() -> dict:
    """Fetch VIX (yfinance), DIX (FINRA), GEX (native), COT (CFTC Socrata).

    Upserts macro_daily. Returns partial data (None for failed fields) — never raises.
    """
    today = date.today()

    async with httpx.AsyncClient(headers=_BROWSER_HEADERS) as client:
        vix_task = asyncio.create_task(_fetch_vix_term())
        dix_task = asyncio.create_task(fetch_dix())
        gex_task = asyncio.create_task(compute_market_gex())
        cot_task = asyncio.create_task(_fetch_cot(client))
        results = await asyncio.gather(
            vix_task, dix_task, gex_task, cot_task, return_exceptions=True
        )

    vix_result, dix_result, gex_result, cot_result = results

    vix_m1 = vix_m2 = vix_m3 = None
    if isinstance(vix_result, tuple):
        vix_m1, vix_m2, vix_m3 = vix_result
    else:
        log.warning("fetch_macro.vix_failed", error=str(vix_result))

    dix: float | None = dix_result if isinstance(dix_result, float) else None
    if not isinstance(dix_result, (float, type(None))):
        log.warning("fetch_macro.dix_failed", error=str(dix_result))

    gex_index: float | None = gex_result if isinstance(gex_result, float) else None
    if not isinstance(gex_result, (float, type(None))):
        log.warning("fetch_macro.gex_failed", error=str(gex_result))

    cot_es_net_long_pct: float | None = cot_result if isinstance(cot_result, float) else None
    if not isinstance(cot_result, (float, type(None))):
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
        row = {
            "date": today,
            "dix": dix,
            "gex_index": gex_index,
            "vix_m1": vix_m1,
            "vix_m2": vix_m2,
            "vix_m3": vix_m3,
            "vix_contango_pct": vix_contango_pct,
            "fetched_at": datetime.now(),
        }
        ins = upsert(MacroDaily).values([row])
        await session.execute(ins.on_conflict_do_update(
            index_elements=["date"],
            set_={k: getattr(ins.excluded, k) for k in
                  ("dix", "gex_index", "vix_m1", "vix_m2", "vix_m3", "vix_contango_pct", "fetched_at")},
        ))
        await session.commit()

    log.info("fetch_macro.done", **{k: v for k, v in payload.items() if k != "date"})
    return payload
