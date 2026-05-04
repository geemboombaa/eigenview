from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select, distinct

from eigenview.api.routes.picks import recommend_structure
from eigenview.data.storage import AsyncSessionLocal, SignalBench

router = APIRouter()

TIER_LABELS = {"B": "FORMING", "C": "SETUP", "D": "UNUSUAL"}


def _bench_to_dict(b: SignalBench) -> dict:
    factors_raw: dict = {}
    if b.factors_json:
        try:
            factors_raw = json.loads(b.factors_json)
        except Exception:
            pass

    structure = recommend_structure(
        b.setup_type or "breakout",
        b.direction or "long",
        None,
    )

    tier = b.tier or "B"
    return {
        "ticker": b.ticker,
        "date": str(b.date),
        "conviction": b.conviction or 1,
        "setup_type": b.setup_type or "watch",
        "direction": b.direction or "long",
        "entry_low": b.entry_low,
        "entry_high": b.entry_high,
        "stop": b.stop,
        "thesis": "",
        "spot": None,
        "iv_rank": None,
        "structure": structure,
        "factors": factors_raw,
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, "WATCH"),
        "gates_missing": b.reason or "",
    }


@router.get("/bench/dates")
async def get_bench_dates() -> list[str]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(distinct(SignalBench.date)).order_by(SignalBench.date.desc())
        )
    return [str(d) for d in result.scalars().all()]


@router.get("/bench")
async def get_bench(date_str: str = Query(None, alias="date")) -> list:
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            target = date.today()
    else:
        target = date.today()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SignalBench)
            .where(SignalBench.date == target)
            .order_by(SignalBench.tier.asc(), SignalBench.conviction.desc())
        )
        items = result.scalars().all()

    return [_bench_to_dict(b) for b in items]


@router.get("/bench/count")
async def get_bench_count(date_str: str = Query(None, alias="date")) -> dict:
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            target = date.today()
    else:
        target = date.today()

    from sqlalchemy import func
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count()).select_from(SignalBench).where(SignalBench.date == target)
        )
        count = result.scalar() or 0
    return {"count": count, "date": str(target)}
