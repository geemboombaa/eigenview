"""Run the activation engine over the dormant watchlist for a target date.

Pipeline: watchlist (dormant_bets) -> pull each contract's OI/vol/close history
from Databento -> compute IV per day -> score_activation(target) -> report + xlsx.

Usage:
  python scripts/run_activation.py --target 2026-05-23 [--limit 20] [--lookback 120]
  python scripts/run_activation.py --target 2026-05-23 --cost   # estimate only
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sqlite3
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DB_PATH = ROOT / "data" / "eigenview.db"

from eigenview.data.databento_history import osi_symbol, fetch_statistics, estimate_cost
from eigenview.factors.activation import score_activation

RISK_FREE = 0.045


def load_watchlist(con: sqlite3.Connection) -> list[dict]:
    rows = con.execute(
        "SELECT ticker, strike, expiry, call_put FROM dormant_bets"
    ).fetchall()
    out = []
    for tk, strike, exp, cp in rows:
        exp_d = dt.date.fromisoformat(exp)
        out.append({
            "ticker": tk, "strike": float(strike), "expiry": exp_d,
            "call_put": cp.upper()[:1],
            "osi": osi_symbol(tk, exp_d, cp, float(strike)),
        })
    # de-dup OSI (same contract can appear once)
    seen = {}
    for w in out:
        seen[w["osi"]] = w
    return list(seen.values())


def underlying_series(con: sqlite3.Connection) -> dict[str, dict[dt.date, tuple]]:
    rows = con.execute(
        "SELECT ticker, date, close, volume FROM prices WHERE timeframe='1d'"
    ).fetchall()
    out: dict[str, dict[dt.date, tuple]] = {}
    for tk, d, close, vol in rows:
        out.setdefault(tk, {})[dt.date.fromisoformat(d)] = (close, vol)
    return out


def compute_iv(close: float, spot: float, strike: float, d: dt.date, expiry: dt.date, cp: str):
    from py_vollib.black_scholes.implied_volatility import implied_volatility
    if not (close and close > 0 and spot and spot > 0):
        return None
    t = max((expiry - d).days, 1) / 365.0
    try:
        return implied_volatility(close, spot, strike, t, RISK_FREE, cp.lower())
    except Exception:
        return None


def persist_history(con: sqlite3.Connection, rows: list[tuple]) -> None:
    con.executemany(
        "INSERT OR REPLACE INTO contract_history (osi_symbol,ticker,date,oi,volume,close,iv) "
        "VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="2026-05-23")
    ap.add_argument("--lookback", type=int, default=120)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cost", action="store_true")
    ap.add_argument("--rescore", action="store_true",
                    help="re-run activation off the already-pulled contract_history (no download)")
    args = ap.parse_args()

    target = dt.date.fromisoformat(args.target)
    start = (target - dt.timedelta(days=args.lookback)).isoformat()
    end = target.isoformat()

    con = sqlite3.connect(DB_PATH)
    watch = load_watchlist(con)
    if args.limit:
        watch = watch[: args.limit]
    symbols = [w["osi"] for w in watch]
    print(f"watchlist: {len(watch)} contracts | window {start}..{end}")

    if args.cost:
        print(f"estimated cost: ${estimate_cost(symbols, start, end):.2f}")
        return

    by_osi = {w["osi"]: w for w in watch}
    und = underlying_series(con)
    series: dict[str, list[dict]] = {}

    if args.rescore:
        # Re-run activation off already-persisted history — no Databento call.
        for osi, d, oi, vol, close, iv in con.execute(
            "SELECT osi_symbol, date, oi, volume, close, iv FROM contract_history"
        ).fetchall():
            if osi not in by_osi:
                continue
            series.setdefault(osi, []).append(
                {"date": dt.date.fromisoformat(d), "oi": oi, "volume": vol, "close": close, "iv": iv})
        print(f"rescore: loaded {sum(len(v) for v in series.values())} rows for {len(series)} contracts")
    else:
        # 1) pull per-contract daily OI/vol/close
        df = fetch_statistics(symbols, start, end)
        print(f"pulled {len(df)} contract-day stat rows for {df['osi_symbol'].nunique()} contracts")

        # 2) compute IV per row + persist
        hist_rows: list[tuple] = []
        for r in df.itertuples():
            w = by_osi.get(r.osi_symbol)
            if not w:
                continue
            d = r.date
            spot = und.get(w["ticker"], {}).get(d, (None, None))[0]
            close = float(r.close) if r.close == r.close else None  # NaN guard
            oi = int(r.oi) if r.oi == r.oi else None
            vol = int(r.volume) if r.volume == r.volume else None
            iv = compute_iv(close, spot, w["strike"], d, w["expiry"], w["call_put"])
            hist_rows.append((r.osi_symbol, w["ticker"], d.isoformat(), oi, vol, close, iv))
            series.setdefault(r.osi_symbol, []).append(
                {"date": d, "oi": oi, "volume": vol, "close": close, "iv": iv})
        persist_history(con, hist_rows)
        print(f"persisted {len(hist_rows)} rows to contract_history")

    # 3) activation per contract.
    #    Window the underlying to the SAME lookback as the contract history, else its
    #    baseline becomes the 2yr median and "underlying move" fires on any uptrend.
    win_start = target - dt.timedelta(days=args.lookback)
    fired = []
    for osi, hist in series.items():
        w = by_osi[osi]
        u = [{"date": d, "close": c, "volume": v}
             for d, (c, v) in und.get(w["ticker"], {}).items()
             if win_start <= d <= target]
        res = score_activation(hist, u, w["call_put"], target)
        if res.fired:
            fired.append((w, res))

    # 4) aggregate to TICKER level (one moving stock shouldn't flood the list with
    #    every strike) — collect distinct triggers per ticker, keep strongest contract.
    by_tk: dict[str, dict] = {}
    for w, res in fired:
        t = w["ticker"]
        e = by_tk.setdefault(t, {"triggers": set(), "contracts": 0, "best": None})
        e["triggers"].update(res.triggers)
        e["contracts"] += 1
        if e["best"] is None or len(res.triggers) > len(e["best"][1].triggers):
            e["best"] = (w, res)

    ranked = sorted(by_tk.items(),
                    key=lambda kv: (len(kv[1]["triggers"]), kv[1]["contracts"]), reverse=True)

    print(f"\n{'='*100}")
    print(f"ACTIVATION on {target}: {len(fired)} contracts fired across {len(by_tk)} tickers")
    print(f"{'='*100}")
    print(f"{'TICKER':<7}{'#BETS':>6}{'BEST STRIKE/EXP':>22}{'AGEd':>6}  TRIGGERS (distinct across bets)")
    for t, e in ranked:
        w, res = e["best"]
        best = f"{w['call_put']}{w['strike']:.0f} {w['expiry']}"
        print(f"{t:<7}{e['contracts']:>6}{best:>22}"
              f"{(res.age_days if res.age_days is not None else -1):>6}  {','.join(sorted(e['triggers']))}")

    # 5) xlsx — per-contract 'fired' + 'by_ticker' summary
    import pandas as pd
    out_rows = []
    for w, res in fired:
        out_rows.append({
            "ticker": w["ticker"], "call_put": w["call_put"], "strike": w["strike"],
            "expiry": str(w["expiry"]), "osi": w["osi"],
            "age_days": res.age_days, "born_on": str(res.born_on) if res.born_on else None,
            "strength": res.strength, "triggers": ",".join(res.triggers),
            **{k: res.detail.get(k) for k in
               ("base_oi", "cur_oi", "oi_jump_pct", "base_vol_avg", "rec_vol_peak",
                "iv_jump", "price_jump_pct", "und_move")},
        })
    tk_rows = [{
        "ticker": t, "fired_bets": e["contracts"],
        "distinct_triggers": ",".join(sorted(e["triggers"])),
        "n_triggers": len(e["triggers"]),
        "best_contract": f"{e['best'][0]['call_put']}{e['best'][0]['strike']:.0f} {e['best'][0]['expiry']}",
    } for t, e in ranked]
    if out_rows:
        out = ROOT / "data" / f"activation_{target}.xlsx"
        with pd.ExcelWriter(out, engine="openpyxl") as xl:
            pd.DataFrame(tk_rows).to_excel(xl, sheet_name="by_ticker", index=False)
            pd.DataFrame(out_rows).sort_values("strength", ascending=False).to_excel(
                xl, sheet_name="fired_contracts", index=False)
        print(f"\ndumped {len(out_rows)} fired contracts / {len(tk_rows)} tickers to {out}")
    con.close()


if __name__ == "__main__":
    main()
