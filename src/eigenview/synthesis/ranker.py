from __future__ import annotations

import json
from datetime import date, datetime


def _json_safe(obj):
    """Convert numpy/pandas scalars to native Python types for JSON serialization."""
    import numpy as np
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Pick, SignalBench
from eigenview.synthesis.gate import (
    SHORT_SETUP_PATTERNS,
    TickerScorecard,
    conviction_score,
    entry_zone,
    qualify_pick,
    setup_type,
    stop_level,
    tier_score,
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
            f.factor_id: {"firing": f.firing, "strength": f.strength, "label": f.label, "detail": f.detail}
            for f in [sc.technical, sc.gex, sc.flow, sc.dormant, sc.sentiment]
        }
        factors_json = json.dumps(factors, default=_json_safe)

        stmt = select(Pick).where(Pick.date == today, Pick.ticker == sc.ticker)
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()

        direction = "short" if sc.technical.label in SHORT_SETUP_PATTERNS else "long"
        if row:
            row.score = float(conv)
            row.setup_type = stype
            row.direction = direction
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
                direction=direction,
                conviction=conv,
                entry_low=entry_lo,
                entry_high=entry_hi,
                stop=stop,
                factors_json=factors_json,
                signal_fired_at=datetime.now(),
            )
            _next_id += 1
            session.add(row)

        await session.flush()
        picks.append(row)

    # Write bench entries for all tiers B/C/D (non-qualifying scorecards)
    max_bench_res = await session.execute(select(func.max(SignalBench.id)))
    bench_id = (max_bench_res.scalar() or 0) + 1
    candidates = all_scorecards or []
    for sc in candidates:
        t = tier_score(sc, macro_score)
        if t is None or t == "A":
            continue
        soft_firing = sum([sc.flow.firing, sc.dormant.firing, sc.sentiment.firing])
        stype = setup_type(sc)
        entry_lo, entry_hi = entry_zone(sc)
        stop = stop_level(sc)
        conv = max(1, min(3, soft_firing + (1 if sc.technical.firing else 0) + (1 if sc.gex.firing else 0) - 1))
        factors = {
            f.factor_id: {"firing": f.firing, "strength": f.strength, "label": f.label, "detail": f.detail}
            for f in [sc.technical, sc.gex, sc.flow, sc.dormant, sc.sentiment]
        }
        gates_missing = []
        if not sc.technical.firing:
            gates_missing.append("TA")
        if not sc.gex.firing:
            gates_missing.append("GEX")
        if soft_firing < 2:
            gates_missing.append(f"soft={soft_firing}/3")
        stmt = select(SignalBench).where(SignalBench.date == today, SignalBench.ticker == sc.ticker)
        result = await session.execute(stmt)
        bench_row = result.scalar_one_or_none()
        if bench_row:
            bench_row.tier = t
            bench_row.soft_factors_firing = soft_firing
            bench_row.reason = ",".join(gates_missing)
            bench_row.factors_json = json.dumps(factors, default=_json_safe)
            bench_row.direction = sc.technical.detail.get("direction", "long")
            bench_row.setup_type = stype
            bench_row.conviction = conv
            bench_row.entry_low = entry_lo
            bench_row.entry_high = entry_hi
            bench_row.stop = stop
        else:
            session.add(SignalBench(
                id=bench_id,
                date=today,
                ticker=sc.ticker,
                soft_factors_firing=soft_firing,
                reason=",".join(gates_missing),
                tier=t,
                factors_json=json.dumps(factors, default=_json_safe),
                direction=sc.technical.detail.get("direction", "long"),
                setup_type=stype,
                conviction=conv,
                entry_low=entry_lo,
                entry_high=entry_hi,
                stop=stop,
            ))
            bench_id += 1
            await session.flush()

    return picks
