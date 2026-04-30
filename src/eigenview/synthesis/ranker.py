from __future__ import annotations

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Pick, SignalBench
from eigenview.synthesis.gate import (
    TickerScorecard,
    conviction_score,
    entry_zone,
    qualify_pick,
    setup_type,
    stop_level,
)


def rank_picks(scorecards: list[TickerScorecard], macro_score: int) -> list[TickerScorecard]:
    qualified = [s for s in scorecards if qualify_pick(s, macro_score)]
    qualified.sort(
        key=lambda s: (conviction_score(s), s.dormant.strength, s.gex.strength),
        reverse=True,
    )
    return qualified[: settings.max_picks]


async def write_picks(
    qualified: list[TickerScorecard],
    macro_score: int,
    session: AsyncSession,
    all_scorecards: list[TickerScorecard] | None = None,
) -> list[Pick]:
    today = date.today()
    picks: list[Pick] = []

    # Seed id counter for SQLite compat (BigInteger PK needs explicit id on SQLite)
    max_id_res = await session.execute(select(func.max(Pick.id)))
    _next_id = (max_id_res.scalar() or 0) + 1

    for sc in qualified:
        conv = conviction_score(sc)
        stype = setup_type(sc)
        entry_lo, entry_hi = entry_zone(sc)
        stop = stop_level(sc)
        factors = {
            f.factor_id: {"firing": f.firing, "strength": f.strength, "label": f.label}
            for f in [sc.technical, sc.gex, sc.flow, sc.dormant, sc.sentiment]
        }
        factors_json = json.dumps(factors)

        stmt = select(Pick).where(Pick.date == today, Pick.ticker == sc.ticker)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        if row:
            row.score = float(conv)
            row.setup_type = stype
            row.conviction = conv
            row.entry_low = entry_lo
            row.entry_high = entry_hi
            row.stop = stop
            row.factors_json = factors_json
        else:
            row = Pick(
                id=_next_id,
                date=today,
                ticker=sc.ticker,
                score=float(conv),
                setup_type=stype,
                conviction=conv,
                entry_low=entry_lo,
                entry_high=entry_hi,
                stop=stop,
                factors_json=factors_json,
            )
            _next_id += 1
            session.add(row)

        await session.flush()
        picks.append(row)

    # Write signal bench entries for tickers that passed Gates 1+2 but not soft factors
    max_bench_res = await session.execute(select(func.max(SignalBench.id)))
    bench_id = (max_bench_res.scalar() or 0) + 1
    candidates = all_scorecards or qualified
    for sc in candidates:
        if sc.technical.firing and sc.gex.firing and not qualify_pick(sc, macro_score):
            soft_firing = sum([sc.flow.firing, sc.dormant.firing, sc.sentiment.firing])
            stmt = select(SignalBench).where(SignalBench.date == today, SignalBench.ticker == sc.ticker)
            result = await session.execute(stmt)
            bench_row = result.scalar_one_or_none()
            if not bench_row:
                session.add(SignalBench(
                    id=bench_id,
                    date=today,
                    ticker=sc.ticker,
                    soft_factors_firing=soft_firing,
                    reason=f"soft={soft_firing}/3",
                ))
                bench_id += 1
                await session.flush()

    return picks
