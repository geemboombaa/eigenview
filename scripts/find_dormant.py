"""
Scan today's chains for dormant bet candidates.
Finds large OI positions at 90+ DTE, estimates premium, scores activation signals.
Writes candidates to dormant_bets table, then runs score_dormant on each.

Usage: uv run python scripts/find_dormant.py [--min-oi 500] [--min-premium 250000]
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select, text
from eigenview.config import settings
from eigenview.data.storage import (
    AsyncSessionLocal, Chain, DormantBet, Catalyst, Price, create_tables
)
from eigenview.factors.dormant import (
    candidate_dwoi_floor,
    dwoi,
    is_dormant_candidate,
    score_bet_v2,
)
from py_vollib.black_scholes import black_scholes as _bs_price


def _mark(c, spot: float) -> float:
    """EOD mid; fall back to Black-Scholes price from stored IV when bid/ask absent."""
    b, a = c.bid or 0, c.ask or 0
    if b > 0 and a > 0:
        return (b + a) / 2
    if c.iv and c.iv > 0 and spot > 0:
        t = max((c.expiry - TODAY).days, 1) / 365.0
        try:
            return _bs_price(c.call_put.lower(), spot, c.strike, t, 0.045, c.iv)
        except Exception:
            return 0.0
    return 0.0


MIN_OI = int(sys.argv[sys.argv.index("--min-oi") + 1]) if "--min-oi" in sys.argv else 500
MIN_PREMIUM = float(sys.argv[sys.argv.index("--min-premium") + 1]) if "--min-premium" in sys.argv else 1_000_000
MIN_DTE = 20  # min days-to-expiry filter
TODAY = date.today()


async def get_spot(ticker: str, session) -> float:
    r = await session.execute(
        select(Price.close)
        .where(Price.ticker == ticker, Price.timeframe == "1d")
        .order_by(Price.date.desc())
        .limit(1)
    )
    val = r.scalar()
    return float(val) if val else 0.0


async def get_catalyst_days(ticker: str, session) -> int | None:
    r = await session.execute(
        select(Catalyst.days_from_now)
        .where(Catalyst.ticker == ticker, Catalyst.days_from_now >= 0)
        .order_by(Catalyst.days_from_now)
        .limit(1)
    )
    val = r.scalar()
    return int(val) if val is not None else None


async def find_candidates(session) -> tuple[list[dict], dict[str, list]]:
    """
    Scan chains for big-relative-to-ticker long-dated positions.
    Bigness is per-ticker: ΔWOI ≥ max($1M tradeability, ticker's 80th pct).
    Returns (sorted candidate dicts, {ticker: full chain rows}).
    """
    rows = await session.execute(
        select(Chain).where(Chain.expiry >= TODAY + timedelta(days=MIN_DTE))
    )
    by_ticker: dict[str, list] = {}
    for c in rows.scalars().all():
        by_ticker.setdefault(c.ticker, []).append(c)

    candidates: list[dict] = []
    ticker_chains: dict[str, list] = {}
    for ticker, tch in by_ticker.items():
        spot = await get_spot(ticker, session)
        if spot <= 0:
            continue
        ticker_chains[ticker] = tch
        floor = candidate_dwoi_floor(tch, spot)
        for c in tch:
            if not is_dormant_candidate(c, spot, floor, TODAY, MIN_DTE):
                continue
            mid = _mark(c, spot)
            candidates.append({
                "ticker": c.ticker, "strike": c.strike, "call_put": c.call_put,
                "expiry": c.expiry, "dte": (c.expiry - TODAY).days, "oi": c.oi,
                "mid": mid, "est_premium": (c.oi or 0) * mid * 100,
                "dwoi": dwoi(c.delta, c.oi, spot),
                "iv": c.iv, "delta": c.delta, "spot": spot,
            })

    # Deduplicate: keep highest OI per ticker/strike/expiry/cp
    seen: dict = {}
    for c in candidates:
        key = (c["ticker"], c["strike"], str(c["expiry"]), c["call_put"])
        if key not in seen or c["oi"] > seen[key]["oi"]:
            seen[key] = c

    return sorted(seen.values(), key=lambda x: x["dwoi"], reverse=True), ticker_chains


async def write_dormant_bets(candidates: list[dict], session) -> int:
    """Write top candidates to dormant_bets table as baseline."""
    written = 0
    for c in candidates:
        existing = await session.execute(
            select(DormantBet).where(
                DormantBet.ticker == c["ticker"],
                DormantBet.strike == c["strike"],
                DormantBet.expiry == c["expiry"],
                DormantBet.call_put == c["call_put"],
            )
        )
        if existing.scalars().first():
            continue

        bet = DormantBet(
            ticker=c["ticker"],
            contract=f"{c['ticker']}_{c['expiry']}_{int(c['strike'])}{str(c['call_put']).upper()[:1]}",
            original_date=TODAY,
            strike=c["strike"],
            expiry=c["expiry"],
            call_put=c["call_put"],
            original_premium=c["est_premium"],
            current_oi=c["oi"],
            original_oi=c["oi"],
        )
        session.add(bet)
        written += 1

    await session.commit()
    return written


class _BetShim:
    """Adapts a candidate dict to the DormantBet interface score_bet_v2 expects."""
    def __init__(self, c: dict):
        self.ticker = c["ticker"]
        self.strike = c["strike"]
        self.call_put = c["call_put"]
        self.expiry = c["expiry"]
        self.original_oi = c["oi"]
        self.original_premium = c["est_premium"]
        self.original_date = TODAY


async def all_catalyst_days(session) -> dict[str, int]:
    """One query: ticker -> nearest upcoming catalyst day count (>=0)."""
    rows = await session.execute(
        select(Catalyst.ticker, Catalyst.days_from_now).where(Catalyst.days_from_now >= 0)
    )
    out: dict[str, int] = {}
    for tk, d in rows.all():
        if d is None:
            continue
        if tk not in out or d < out[tk]:
            out[tk] = int(d)
    return out


def score_candidate(c: dict, ticker_chains: dict, cat_days: dict) -> dict:
    """Score a candidate with the real engine (score_bet_v2). Bypasses the 30-day gate."""
    catalyst_days = cat_days.get(c["ticker"])
    catalyst_near = catalyst_days is not None and catalyst_days <= 14
    tch = ticker_chains.get(c["ticker"], [])
    score, detail = score_bet_v2(_BetShim(c), tch, c["spot"], catalyst_near)
    _MAX = 7
    return {
        **c,
        "catalyst_days": catalyst_days,
        "score": round(score, 2),
        "activation_pct": score / _MAX,
        "detail": detail,
        "direction": "CALL BET" if c["call_put"].upper() == "C" else "PUT BET",
        "fires": (score / _MAX) >= settings.dormant_firing_threshold,
    }


def _flatten(s: dict) -> dict:
    """Scored candidate dict -> flat row for the spreadsheet."""
    d = s["detail"]
    return {
        "ticker": s["ticker"],
        "direction": s["direction"],
        "call_put": s["call_put"],
        "strike": s["strike"],
        "expiry": str(s["expiry"]),
        "dte": s["dte"],
        "oi": s["oi"],
        "dwoi_usd": round(s.get("dwoi", 0)),
        "est_premium_usd": round(s["est_premium"]),
        "size_pct": d.get("size_pct"),
        "iv": round(s["iv"], 4) if s.get("iv") is not None else None,
        "iv_pct": d.get("iv_pct"),
        "hedge_purity": d.get("hedge_purity"),
        "isolation_mult": d.get("isolation_multiplier"),
        "catalyst_days": s["catalyst_days"],
        "spot": round(s["spot"], 2),
        "score": s["score"],
        "activation_pct": round(s["activation_pct"], 3),
        "fires": s["fires"],
    }


def dump_xlsx(scored: list[dict], path: Path) -> None:
    import pandas as pd

    rows = [_flatten(s) for s in scored]
    df = pd.DataFrame(rows)
    fire_pct = settings.dormant_firing_threshold
    firing = df[df["fires"]].sort_values(["score", "size_pct"], ascending=False)

    by_ticker = (
        df.groupby("ticker")
        .agg(candidates=("score", "size"),
             firing=("fires", "sum"),
             best_score=("score", "max"),
             max_size_pct=("size_pct", "max"),
             total_est_premium=("est_premium_usd", "sum"),
             max_oi=("oi", "max"))
        .reset_index()
        .sort_values(["firing", "best_score"], ascending=False)
    )

    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        df.sort_values(["score", "size_pct"], ascending=False).to_excel(xl, sheet_name="all_candidates", index=False)
        firing.to_excel(xl, sheet_name="firing", index=False)
        by_ticker.to_excel(xl, sheet_name="by_ticker", index=False)


async def main() -> None:
    await create_tables()

    async with AsyncSessionLocal() as session:
        print("Scanning chains for dormant bet candidates...")
        print(f"  Filter: DWOI >= max($1M, ticker 80th pct), DTE >= {MIN_DTE}\n")

        candidates, ticker_chains = await find_candidates(session)
        n_tickers = len(set(c["ticker"] for c in candidates))
        print(f"Found {len(candidates)} candidates across {n_tickers} tickers")

        cat_days = await all_catalyst_days(session)
        print(f"Catalysts available for {len(cat_days)} tickers\n")

        # Score EVERY candidate (no top-N cap) with the real relative engine.
        scored = [score_candidate(c, ticker_chains, cat_days) for c in candidates]
        firing = [s for s in scored if s["fires"]]
        fire_tickers = sorted(set(s["ticker"] for s in firing))
        print(f"FIRING (activation >= {settings.dormant_firing_threshold:.0%}): "
              f"{len(firing)} contracts across {len(fire_tickers)} tickers\n")

        # Persist all firing bets as the tracking baseline.
        firing_sorted = sorted(firing, key=lambda x: x["score"], reverse=True)
        written = await write_dormant_bets(firing_sorted, session)
        print(f"Wrote {written} firing bets to dormant_bets table")

        out = Path(__file__).parent.parent / "data" / "dormant_scan.xlsx"
        dump_xlsx(scored, out)
        print(f"Dumped {len(scored)} candidates to {out}\n")

        # Breadth check: are non-mega-caps firing? Show firing tickers by best score.
        best_by_ticker: dict[str, dict] = {}
        for s in firing:
            t = s["ticker"]
            if t not in best_by_ticker or s["score"] > best_by_ticker[t]["score"]:
                best_by_ticker[t] = s
        ranked = sorted(best_by_ticker.values(), key=lambda x: (x["score"], x["detail"].get("size_pct", 0)), reverse=True)
        print(f"{'='*92}")
        print(f"FIRING TICKERS ({len(ranked)}) — best dormant bet each, ranked by score then relative size")
        print(f"{'TICKER':<8}{'DIR':<10}{'STRIKE':>8}{'EXPIRY':>12}{'OI':>9}{'SIZE%':>7}{'IV%':>7}{'CATd':>6}{'SCORE':>7}")
        print(f"{'-'*92}")
        for s in ranked:
            d = s["detail"]
            ivp = d.get("iv_pct")
            print(f"{s['ticker']:<8}{s['direction']:<10}{s['strike']:>8.0f}{str(s['expiry']):>12}"
                  f"{s['oi']:>9,}{d.get('size_pct',0):>7.2f}{(ivp if ivp is not None else -1):>7.2f}"
                  f"{(s['catalyst_days'] if s['catalyst_days'] is not None else -1):>6}{s['score']:>7}")


if __name__ == "__main__":
    asyncio.run(main())
