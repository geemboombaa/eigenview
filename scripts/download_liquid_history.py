"""Download daily contract history (OI/vol/close/IV) for liquid-ticker dormant bets.

Scope: liquid tickers (agg chain OI >= settings.dormant_min_ticker_oi), top-3 bets
each by premium, 120-day window, skipping contracts already stored. Writes
contract_history (INSERT OR IGNORE). Estimated cost ~$4.71.
"""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta

from eigenview.config import settings
from eigenview.data.databento_history import fetch_statistics, osi_symbol
from eigenview.synthesis.scanner import _compute_contract_iv

TOP_N = 3
DB = "data/eigenview.db"


def main() -> None:
    c = sqlite3.connect(DB)

    liquid = {
        t for t, oi in c.execute(
            """WITH latest AS (SELECT ticker, MAX(snapshot_date) sd FROM chains GROUP BY ticker)
               SELECT ch.ticker, SUM(COALESCE(ch.oi,0)) FROM chains ch
               JOIN latest l ON ch.ticker=l.ticker AND ch.snapshot_date=l.sd
               GROUP BY ch.ticker"""
        ).fetchall() if oi >= settings.dormant_min_ticker_oi
    }

    have = {r[0] for r in c.execute("SELECT DISTINCT osi_symbol FROM contract_history").fetchall()}

    sym_bet: dict[str, tuple] = {}  # osi -> (ticker, strike, expiry_date, call_put)
    for t in liquid:
        for expiry, cp, strike in c.execute(
            """SELECT expiry, call_put, strike FROM dormant_bets
               WHERE ticker=? ORDER BY original_premium DESC LIMIT ?""",
            (t, TOP_N),
        ).fetchall():
            ed = date.fromisoformat(expiry)
            sym = osi_symbol(t, ed, cp, strike)
            if sym not in have:
                sym_bet[sym] = (t, float(strike), ed, cp)

    symbols = sorted(sym_bet)
    print(f"liquid tickers: {len(liquid)}  contracts to pull: {len(symbols)}", flush=True)
    if not symbols:
        print("nothing to pull")
        c.close()
        return

    # underlying close per ticker per date for IV solve
    und: dict[str, dict[str, float]] = {}
    for tk, d, cl in c.execute("SELECT ticker, date, close FROM prices WHERE timeframe='1d'").fetchall():
        und.setdefault(tk.upper(), {})[d] = cl

    # Databento OPRA historical license ends at the prior session; requesting
    # through "today" crosses into the live-data window (403). Cap at yesterday.
    end_d = date.today() - timedelta(days=1)
    end = end_d.isoformat()
    start = (end_d - timedelta(days=120)).isoformat()
    print(f"fetching {start} -> {end}  (parallel, 4 workers) ...", flush=True)
    chunk = 150
    chunks = [symbols[i:i + chunk] for i in range(0, len(symbols), chunk)]
    n_batches = len(chunks)
    cur = c.cursor()
    total_new = 0

    def _rows(df):
        out = []
        for r in df.itertuples():
            bet = sym_bet.get(r.osi_symbol)
            if not bet:
                continue
            tk, strike, expiry, cp = bet
            d = r.date
            dstr = d.isoformat()
            spot = und.get(tk.upper(), {}).get(dstr)
            close = float(r.close) if r.close == r.close and r.close else None
            oi = int(r.oi) if r.oi == r.oi and r.oi else None
            vol = int(r.volume) if r.volume == r.volume and r.volume else None
            iv = _compute_contract_iv(close, spot, strike, d, expiry, cp)
            out.append((r.osi_symbol, tk, dstr, oi, vol, close, iv))
        return out

    # Fetch batches concurrently (network-bound; threads release the GIL during the
    # Databento call). DB writes stay in the main thread (SQLite single-writer) and
    # commit per batch as each future completes — crash-safe and resumable.
    done = 0
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(fetch_statistics, ch, start, end): bi for bi, ch in enumerate(chunks, 1)}
        for fut in as_completed(futs):
            bi = futs[fut]
            try:
                df = fut.result()
            except Exception as exc:
                print(f"  batch {bi}/{n_batches} FAILED: {exc}", flush=True)
                continue
            inserts = _rows(df)
            before = c.total_changes
            cur.executemany(
                "INSERT OR IGNORE INTO contract_history (osi_symbol, ticker, date, oi, volume, close, iv) "
                "VALUES (?,?,?,?,?,?,?)",
                inserts,
            )
            c.commit()
            total_new += c.total_changes - before
            done += 1
            print(f"  batch {bi}/{n_batches} ({done} complete): {len(df)} rows, "
                  f"{c.total_changes - before} inserted (cumulative {total_new})", flush=True)

    cov = c.execute("SELECT COUNT(DISTINCT ticker) FROM contract_history").fetchone()[0]
    print(f"DONE. new rows: {total_new}  contract_history ticker coverage now: {cov}", flush=True)
    c.close()


if __name__ == "__main__":
    main()
