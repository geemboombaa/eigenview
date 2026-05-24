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

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select, text
from eigenview.data.storage import (
    AsyncSessionLocal, Chain, DormantBet, Catalyst, Price, create_tables
)


MIN_OI = int(sys.argv[sys.argv.index("--min-oi") + 1]) if "--min-oi" in sys.argv else 500
MIN_PREMIUM = float(sys.argv[sys.argv.index("--min-premium") + 1]) if "--min-premium" in sys.argv else 250_000
MIN_DTE = 60  # lowered from 90 since we have limited chain data
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


async def find_candidates(session) -> list[dict]:
    """
    Scan chains table for large long-dated OI positions.
    Returns sorted list of candidate dormant bets.
    """
    # Get all far-dated chains with meaningful OI
    rows = await session.execute(
        select(Chain)
        .where(
            Chain.expiry >= TODAY + timedelta(days=MIN_DTE),
            Chain.oi >= MIN_OI,
        )
        .order_by(Chain.oi.desc())
    )
    chains = rows.scalars().all()

    candidates = []
    for c in chains:
        mid = ((c.bid or 0) + (c.ask or 0)) / 2
        est_premium = (c.oi or 0) * mid * 100
        if est_premium < MIN_PREMIUM:
            continue

        # Filter deep ITM (stock substitutes, not directional bets)
        # Call deep ITM = delta > 0.85; use delta if available, else strike/mid heuristic
        if c.delta is not None:
            if c.call_put.upper() == "C" and c.delta > 0.85:
                continue
            if c.call_put.upper() == "P" and c.delta < -0.85:
                continue

        dte = (c.expiry - TODAY).days

        candidates.append({
            "ticker": c.ticker,
            "strike": c.strike,
            "call_put": c.call_put,
            "expiry": c.expiry,
            "dte": dte,
            "oi": c.oi,
            "bid": c.bid,
            "ask": c.ask,
            "mid": mid,
            "est_premium": est_premium,
            "iv": c.iv,
            "delta": c.delta,
            "gamma": c.gamma,
        })

    # Deduplicate: keep highest OI per ticker/strike/expiry/cp
    seen = {}
    for c in candidates:
        key = (c["ticker"], c["strike"], str(c["expiry"]), c["call_put"])
        if key not in seen or c["oi"] > seen[key]["oi"]:
            seen[key] = c

    return sorted(seen.values(), key=lambda x: x["est_premium"], reverse=True)


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
            contract=f"{c['ticker']}_{c['expiry']}_{int(c['strike'])}{c['call_put']}",
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


async def score_candidate(c: dict, session) -> dict:
    """Score a candidate using available signals (bypass 30-day gate)."""
    spot = await get_spot(c["ticker"], session)
    catalyst_days = await get_catalyst_days(c["ticker"], session)

    score = 0
    signals = []

    # sig1 — OI size (proxy for conviction — no historical comparison available yet)
    if c["oi"] >= 5000:
        score += 2
        signals.append(f"OI={c['oi']:,} (very large)")
    elif c["oi"] >= 1000:
        score += 1
        signals.append(f"OI={c['oi']:,} (large)")

    # sig2 — catalyst proximity
    if catalyst_days is not None:
        if catalyst_days <= 14:
            score += 2
            signals.append(f"catalyst in {catalyst_days}d")
        elif catalyst_days <= 30:
            score += 1
            signals.append(f"catalyst in {catalyst_days}d")

    # sig3 — strike proximity to spot
    if spot > 0:
        pct = abs(c["strike"] - spot) / spot
        if pct < 0.05:
            score += 2
            signals.append(f"strike {pct*100:.1f}% from spot ${spot:.0f}")
        elif pct < 0.10:
            score += 1
            signals.append(f"strike {pct*100:.1f}% from spot ${spot:.0f}")

    # sig4 — premium size
    if c["est_premium"] >= 1_000_000:
        score += 1
        signals.append(f"${c['est_premium']/1e6:.1f}M est premium")

    # sig5 — DTE
    if c["dte"] >= 90:
        score += 1
        signals.append(f"{c['dte']}d to expiry")

    # sig6 — time alive (today = 1 day since we just loaded)
    score += 1  # always passes for new baseline bets

    direction = "CALL BET" if c["call_put"].upper() == "C" else "PUT BET"
    activation = score / 9

    return {
        **c,
        "spot": spot,
        "catalyst_days": catalyst_days,
        "score": score,
        "activation_pct": activation,
        "signals": signals,
        "direction": direction,
        "fires": activation >= 0.4,  # lowered threshold from 0.6 for cold-start
    }


async def main() -> None:
    await create_tables()

    async with AsyncSessionLocal() as session:
        print("Scanning chains for dormant bet candidates...")
        print(f"  Filters: OI>={MIN_OI}, est_premium>=${MIN_PREMIUM:,.0f}, DTE>={MIN_DTE}\n")

        candidates = await find_candidates(session)
        print(f"Found {len(candidates)} candidates across {len(set(c['ticker'] for c in candidates))} tickers")

        # Write top 500 to dormant_bets table
        written = await write_dormant_bets(candidates[:500], session)
        print(f"Wrote {written} new bets to dormant_bets table\n")

        # Score top 50 by premium
        print(f"{'='*90}")
        print(f"{'TICKER':<8} {'CP':<3} {'STRIKE':>8} {'EXPIRY':<12} {'DTE':>5} {'OI':>8} {'EST_PREM':>12} {'SCORE':>7} {'SIGNALS'}")
        print(f"{'='*90}")

        firing = []
        all_scored = []
        for c in candidates[:50]:
            scored = await score_candidate(c, session)
            all_scored.append(scored)
            if scored["fires"]:
                firing.append(scored)

            print(
                f"{scored['ticker']:<8} "
                f"{scored['call_put']:<3} "
                f"{scored['strike']:>8.0f} "
                f"{str(scored['expiry']):<12} "
                f"{scored['dte']:>5} "
                f"{scored['oi']:>8,} "
                f"${scored['est_premium']:>10,.0f} "
                f"  {scored['score']}/9 "
                f"  {', '.join(scored['signals'])}"
            )

        print(f"\n{'='*90}")
        print(f"\nFIRING (activation ≥ 40%): {len(firing)}/{min(50,len(candidates))} scored")
        print()
        for c in sorted(firing, key=lambda x: x["score"], reverse=True):
            print(f"  *** {c['ticker']} {c['direction']} — ${c['strike']:.0f} exp {c['expiry']} "
                  f"| OI={c['oi']:,} | ${c['est_premium']/1e6:.2f}M | score={c['score']}/9 | "
                  f"spot=${c['spot']:.0f} cat={c['catalyst_days']}d")
            for sig in c["signals"]:
                print(f"       • {sig}")
            print()

        # Summary stats
        print(f"{'='*90}")
        print(f"SUMMARY — all {len(candidates)} candidates:")
        by_ticker = {}
        for c in candidates:
            by_ticker.setdefault(c["ticker"], []).append(c)

        top_tickers = sorted(by_ticker.items(), key=lambda x: sum(c["est_premium"] for c in x[1]), reverse=True)[:20]
        print(f"\nTop 20 tickers by total dormant premium:")
        for ticker, bets in top_tickers:
            total = sum(b["est_premium"] for b in bets)
            max_oi = max(b["oi"] for b in bets)
            calls = sum(1 for b in bets if b["call_put"].upper() == "C")
            puts = sum(1 for b in bets if b["call_put"].upper() == "P")
            print(f"  {ticker:<8} ${total/1e6:>8.1f}M | {len(bets)} contracts | calls={calls} puts={puts} | max_oi={max_oi:,}")


if __name__ == "__main__":
    asyncio.run(main())
