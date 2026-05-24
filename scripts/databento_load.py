"""Load EigenView price + options-chain data from Databento.

Equities  : EQUS.MINI ohlcv-1d (2yr) + ohlcv-1h (90d) -> prices table
Options   : OPRA.PILLAR definition + statistics (latest day) -> chains table
            monthly expiries only (3rd Friday), today .. +1yr
Greeks    : iv/delta/gamma computed locally (py_vollib) from mark + spot

Usage:
  python scripts/databento_load.py --tickers AAPL,NVDA --equities --options
  python scripts/databento_load.py --all --clear          # full run, wipe first
  python scripts/databento_load.py --all --cost           # cost estimate only
"""
from __future__ import annotations

import argparse
import asyncio
import calendar
import datetime as dt
import sqlite3
import sys
from pathlib import Path

import databento as db
import pandas as pd
from pandas.tseries.holiday import GoodFriday, USFederalHolidayCalendar

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DB_PATH = ROOT / "data" / "eigenview.db"

# OPRA daily-statistics stat_type codes (databento StatType enum)
ST_VOLUME = 6        # CLEARED_VOLUME  (quantity)
ST_LOWEST_OFFER = 7  # ask (price)
ST_HIGHEST_BID = 8   # bid (price)
ST_OPEN_INTEREST = 9 # OI (quantity)
ST_CLOSE = 11        # close price (price)

RISK_FREE = 0.045
END = "2026-05-23"  # latest available EQUS/OPRA day (T+1)


def load_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DATABENTO_KEY not in .env")


def get_universe_tickers() -> list[str]:
    from eigenview.data.universe import get_universe

    sp = asyncio.run(get_universe("sp500"))
    ndx = asyncio.run(get_universe("ndx100"))
    return sorted(set(sp) | set(ndx))


_HOLIDAY_CACHE: dict[int, set[dt.date]] = {}


def _market_holidays(year: int) -> set[dt.date]:
    if year not in _HOLIDAY_CACHE:
        lo, hi = f"{year}-01-01", f"{year}-12-31"
        fed = set(pd.Timestamp(d).date() for d in USFederalHolidayCalendar().holidays(lo, hi))
        gf = set(pd.Timestamp(d).date() for d in GoodFriday.dates(lo, hi))
        _HOLIDAY_CACHE[year] = fed | gf
    return _HOLIDAY_CACHE[year]


def monthly_expiry(year: int, month: int) -> dt.date:
    """Standard monthly opex = 3rd Friday, shifted earlier if that Friday is a market holiday."""
    fridays = [w[calendar.FRIDAY] for w in calendar.monthcalendar(year, month) if w[calendar.FRIDAY]]
    d = dt.date(year, month, fridays[2])
    while d in _market_holidays(year):
        d -= dt.timedelta(days=1)
    return d


def is_monthly(expiry: dt.date) -> bool:
    return expiry == monthly_expiry(expiry.year, expiry.month)


# ---------------------------------------------------------------- equities
def load_equities(client: db.Historical, tickers: list[str], con: sqlite3.Connection) -> None:
    today = dt.date.fromisoformat(END)
    rng = client.metadata.get_dataset_range(dataset="EQUS.MINI")
    avail_start = dt.date.fromisoformat(rng["start"][:10])
    start_1d = max(today - dt.timedelta(days=730), avail_start).isoformat()
    start_1h = max(today - dt.timedelta(days=90), avail_start).isoformat()

    cur = con.cursor()
    for schema, start, tf in [("ohlcv-1d", start_1d, "1d"), ("ohlcv-1h", start_1h, "1h")]:
        data = client.timeseries.get_range(
            dataset="EQUS.MINI", schema=schema, symbols=tickers,
            start=start, end=END, stype_in="raw_symbol",
        )
        df = data.to_df()
        if df.empty:
            print(f"  equities {schema}: no rows")
            continue
        df = df.reset_index()
        rows = []
        for r in df.itertuples():
            d = pd.Timestamp(r.ts_event).date().isoformat()
            rows.append((r.symbol, d, float(r.open), float(r.high), float(r.low),
                         float(r.close), int(r.volume), tf))
        cur.executemany(
            "INSERT OR REPLACE INTO prices (ticker,date,open,high,low,close,volume,timeframe) "
            "VALUES (?,?,?,?,?,?,?,?)", rows)
        con.commit()
        print(f"  equities {schema}: {len(rows)} rows ({start}..{END})")


def spot_map(con: sqlite3.Connection) -> dict[str, float]:
    cur = con.cursor()
    rows = cur.execute(
        "SELECT ticker, close FROM prices WHERE timeframe='1d' AND date=("
        "SELECT MAX(date) FROM prices p2 WHERE p2.ticker=prices.ticker AND timeframe='1d')"
    ).fetchall()
    m: dict[str, float] = {}
    for tk, c in rows:
        m[tk] = c
        m[tk.replace("-", "").replace(".", "")] = c  # OSI-root variant (BRK-B -> BRKB)
    return m


# ---------------------------------------------------------------- options
def _last_per(df: pd.DataFrame, stat: int, value_col: str) -> dict[str, float]:
    sub = df[df["stat_type"] == stat]
    if sub.empty:
        return {}
    return sub.groupby("symbol")[value_col].last().to_dict()


def _load_options_batch(client, tickers, con, today, start, spots, greeks) -> int:
    bs_delta, bs_gamma, implied_volatility = greeks
    opt_syms = [f"{t}.OPT" for t in tickers]

    ddf = client.timeseries.get_range(
        dataset="OPRA.PILLAR", schema="definition", symbols=opt_syms,
        start=start, end=END, stype_in="parent",
    ).to_df()
    defs: dict[str, tuple] = {}
    for r in ddf.itertuples():
        cls = getattr(r, "instrument_class", None)
        if cls not in ("C", "P"):
            continue
        exp = pd.Timestamp(r.expiration).date()
        if not (exp > today and is_monthly(exp)):
            continue
        defs[r.raw_symbol] = (float(r.strike_price), exp, cls)

    sdf = client.timeseries.get_range(
        dataset="OPRA.PILLAR", schema="statistics", symbols=opt_syms,
        start=start, end=END, stype_in="parent",
    ).to_df()
    oi = _last_per(sdf, ST_OPEN_INTEREST, "quantity")
    vol = _last_per(sdf, ST_VOLUME, "quantity")
    bid = _last_per(sdf, ST_HIGHEST_BID, "price")
    ask = _last_per(sdf, ST_LOWEST_OFFER, "price")
    close = _last_per(sdf, ST_CLOSE, "price")

    rows = []
    for sym, (strike, exp, cls) in defs.items():
        root = sym.strip().split()[0]
        S = spots.get(root)
        b, a, c = bid.get(sym), ask.get(sym), close.get(sym)
        mark = (b + a) / 2 if (b and a and b > 0 and a > 0) else (c if c and c > 0 else None)
        iv = dlt = gma = None
        if S and mark and mark > 0:
            t = max((exp - today).days, 1) / 365.0
            flag = cls.lower()
            try:
                iv = implied_volatility(mark, S, strike, t, RISK_FREE, flag)
                dlt = bs_delta(flag, S, strike, t, RISK_FREE, iv)
                gma = bs_gamma(flag, S, strike, t, RISK_FREE, iv)
            except Exception:  # noqa: BLE001  below-intrinsic / no-solution
                pass
        rows.append((root, END, strike, exp.isoformat(), cls,
                     b, a, int(vol.get(sym, 0)) or None,
                     int(oi.get(sym, 0)) or None, iv, dlt, gma))

    con.executemany(
        "INSERT INTO chains (ticker,snapshot_date,strike,expiry,call_put,bid,ask,volume,oi,iv,delta,gamma) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    return len(rows)


def load_options(client: db.Historical, tickers: list[str], con: sqlite3.Connection, batch: int = 40) -> None:
    from py_vollib.black_scholes.greeks.analytical import delta as bs_delta, gamma as bs_gamma
    from py_vollib.black_scholes.implied_volatility import implied_volatility

    today = dt.date.fromisoformat(END)
    start = (today - dt.timedelta(days=1)).isoformat()
    spots = spot_map(con)
    greeks = (bs_delta, bs_gamma, implied_volatility)

    total = 0
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        n = _load_options_batch(client, chunk, con, today, start, spots, greeks)
        total += n
        print(f"  options batch {i // batch + 1} ({chunk[0]}..{chunk[-1]}): {n} rows  [total {total}]")
    print(f"  options: {total} chain rows written (snapshot {END})")


# ---------------------------------------------------------------- cost
def estimate(client: db.Historical, tickers: list[str]) -> None:
    opt = [f"{t}.OPT" for t in tickers]
    today = dt.date.fromisoformat(END)
    start = (today - dt.timedelta(days=1)).isoformat()
    eq_start = (today - dt.timedelta(days=730)).isoformat()
    plan = [
        ("EQUS.MINI", "ohlcv-1d", "raw_symbol", tickers, eq_start),
        ("EQUS.MINI", "ohlcv-1h", "raw_symbol", tickers, (today - dt.timedelta(days=90)).isoformat()),
        ("OPRA.PILLAR", "definition", "parent", opt, start),
        ("OPRA.PILLAR", "statistics", "parent", opt, start),
    ]
    total = 0.0
    for ds, sch, sty, sy, s in plan:
        cost = client.metadata.get_cost(dataset=ds, symbols=sy, schema=sch, start=s, end=END, stype_in=sty)
        total += cost
        print(f"  {ds:12} {sch:11} ${cost:8.2f}")
    print(f"  TOTAL ${total:.2f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", help="comma list; default = SP500+NDX universe")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--equities", action="store_true")
    ap.add_argument("--options", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--clear", action="store_true", help="wipe prices+chains first")
    ap.add_argument("--cost", action="store_true", help="cost estimate only, no download")
    args = ap.parse_args()

    tickers = args.tickers.split(",") if args.tickers else get_universe_tickers()
    if args.limit:
        tickers = tickers[: args.limit]
    print(f"tickers: {len(tickers)}")

    client = db.Historical(load_key())
    if args.cost:
        estimate(client, tickers)
        return

    con = sqlite3.connect(DB_PATH)
    if args.clear:
        con.execute("DELETE FROM prices")
        con.execute("DELETE FROM chains")
        con.commit()
        print("cleared prices + chains")

    if args.all or args.equities:
        load_equities(client, tickers, con)
    if args.all or args.options:
        load_options(client, tickers, con)
    con.close()


if __name__ == "__main__":
    main()
