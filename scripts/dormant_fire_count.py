"""Activation-only dormant fire count over the liquid universe (read-only).

Liquid = aggregate latest-snapshot chain OI >= settings.dormant_min_ticker_oi.
For each liquid ticker: score_dormant_from_history (activation engine). Count fires.
"""
from __future__ import annotations

import asyncio
import sys
import warnings

warnings.filterwarnings("ignore")
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import func, select

from eigenview.config import settings
from eigenview.data.storage import AsyncSessionLocal, Chain, Price
from eigenview.factors.dormant import score_dormant_from_history


async def _liquid_tickers(session) -> list[str]:
    latest = (
        select(Chain.ticker, func.max(Chain.snapshot_date).label("sd"))
        .group_by(Chain.ticker)
        .subquery()
    )
    rows = await session.execute(
        select(Chain.ticker, func.sum(func.coalesce(Chain.oi, 0)))
        .join(latest, (Chain.ticker == latest.c.ticker) & (Chain.snapshot_date == latest.c.sd))
        .group_by(Chain.ticker)
    )
    return sorted({t for t, oi in rows.all() if (oi or 0) >= settings.dormant_min_ticker_oi})


async def _score(ticker: str) -> dict | None:
    async with AsyncSessionLocal() as session:
        spot_row = await session.execute(
            select(Price.close).where(Price.ticker == ticker.upper(), Price.timeframe == "1d")
            .order_by(Price.date.desc()).limit(1)
        )
        spot = spot_row.scalar()
        if not spot:
            return None
        snap = (await session.execute(
            select(func.max(Chain.snapshot_date)).where(Chain.ticker == ticker)
        )).scalar()
        chains = [] if snap is None else (await session.execute(
            select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == snap)
        )).scalars().all()
        r = await score_dormant_from_history(ticker, session, float(spot), list(chains))
    dd = r.detail or {}
    return {
        "ticker": ticker,
        "firing": bool(r.firing),
        "activation": bool(r.firing and "triggers" in dd),
        "strength": round(float(r.strength or 0), 2),
        "triggers": ",".join(dd.get("triggers", []) or []),
        "strike": dd.get("best_bet_strike"),
        "expiry": dd.get("best_bet_expiry"),
    }


async def main() -> None:
    async with AsyncSessionLocal() as session:
        liquid = await _liquid_tickers(session)
    print(f"liquid tickers (agg OI >= {settings.dormant_min_ticker_oi}): {len(liquid)}", flush=True)

    sem = asyncio.Semaphore(8)

    async def bounded(t):
        async with sem:
            return await _score(t)

    res = [r for r in await asyncio.gather(*[bounded(t) for t in liquid]) if r]
    fired = sorted([r for r in res if r["firing"]], key=lambda x: -x["strength"])

    print(f"scored: {len(res)}   DORMANT FIRING (activation): {len(fired)}")
    print(f"{'TICKER':<8}{'STR':>5}  {'CONTRACT':<22}{'TRIGGERS'}")
    for r in fired:
        contract = f"${r['strike']:.0f} {r['expiry']}" if r["strike"] is not None else "-"
        print(f"{r['ticker']:<8}{r['strength']:>5}  {contract:<22}{r['triggers']}")


if __name__ == "__main__":
    asyncio.run(main())
