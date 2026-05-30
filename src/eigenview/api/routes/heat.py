from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query
from sqlalchemy import select

from eigenview.data.storage import AsyncSessionLocal, FactorScore, Pick

router = APIRouter()

_FACTORS = ["ta", "gex", "flow", "dormant", "sentiment"]
_TOP_N = 5


@router.get("/signals/heat")
async def get_signals_heat(date_str: str = Query(None, alias="date")) -> dict:
    """Return top-N tickers per factor column for the heat map / factor pulse panel."""
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            target = date.today()
    else:
        target = date.today()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(FactorScore).where(FactorScore.date == target)
        )
        rows = result.scalars().all()

    if not rows:
        return {f: [] for f in _FACTORS}

    def top_n(key_strength: str, key_label: str) -> list[dict]:
        scored = [
            {
                "ticker": r.ticker,
                "strength": getattr(r, key_strength) or 0.0,
                "label": getattr(r, key_label) or "",
                "spot": r.spot_price,
                "factors_firing": r.factors_firing or 0,
            }
            for r in rows
            if (getattr(r, key_strength) or 0) > 0
        ]
        scored.sort(key=lambda x: x["strength"], reverse=True)
        return scored[:_TOP_N]

    return {
        "date": str(target),
        "ta":        top_n("ta_strength",        "ta_label"),
        "gex":       top_n("gex_strength",       "gex_label"),
        "flow":      top_n("flow_strength",       "flow_label"),
        "dormant":   top_n("dormant_strength",    "dormant_label"),
        "sentiment": top_n("sentiment_strength",  "sentiment_label"),
        "pulse": sorted(
            [{"ticker": r.ticker, "factors_firing": r.factors_firing or 0,
              "spot": r.spot_price,
              "ta": r.ta_label, "gex": r.gex_label, "flow": r.flow_label,
              "dormant": r.dormant_label, "sentiment": r.sentiment_label,
              "ta_str": r.ta_strength or 0, "gex_str": r.gex_strength or 0,
              "flow_str": r.flow_strength or 0, "dormant_str": r.dormant_strength or 0,
              "sentiment_str": r.sentiment_strength or 0}
             for r in rows],
            key=lambda x: x["factors_firing"], reverse=True
        )[:20],
    }


@router.get("/signals/matrix")
async def get_signals_matrix(date_str: str = Query(None, alias="date")) -> dict:
    """Return all scanned tickers as a matrix (ticker × factor) for the Signal Matrix panel."""
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            target = date.today()
    else:
        target = date.today()

    async with AsyncSessionLocal() as session:
        fs_result = await session.execute(
            select(FactorScore).where(FactorScore.date == target)
        )
        scores = fs_result.scalars().all()

        picks_result = await session.execute(
            select(Pick).where(Pick.date == target)
        )
        picks = picks_result.scalars().all()

    picks_map = {p.ticker: {"conviction": p.conviction, "setup_type": p.setup_type} for p in picks}

    if not scores:
        return {"date": str(target), "rows": []}

    rows = []
    for s in scores:
        # ALL = every scanned ticker where TA OR dormant fired (matches product definition).
        if not ((s.ta_strength or 0) > 0 or (s.dormant_strength or 0) > 0):
            continue
        pick_info = picks_map.get(s.ticker, {})
        rows.append({
            "ticker": s.ticker,
            "setup_type": pick_info.get("setup_type") or s.ta_label or "",
            "in_picks": s.ticker in picks_map,
            "conviction": pick_info.get("conviction") or 0,
            "spot": s.spot_price,
            "macro_str": round(min(3.0, (s.macro_score or 0) * 0.3), 2),
            "ta_str": s.ta_strength or 0.0,
            "ta_label": s.ta_label or "",
            "ta_tier": s.ta_tier or "",
            "gex_str": s.gex_strength or 0.0,
            "gex_label": s.gex_label or "",
            "flow_str": s.flow_strength or 0.0,
            "flow_label": s.flow_label or "",
            "dormant_str": s.dormant_strength or 0.0,
            "dormant_label": s.dormant_label or "",
            "sentiment_str": s.sentiment_strength or 0.0,
            "sentiment_label": s.sentiment_label or "",
            "factors_firing": s.factors_firing or 0,
        })

    rows.sort(key=lambda r: (not r["in_picks"], -(r["conviction"] or 0), -(r["factors_firing"] or 0)))
    return {"date": str(target), "rows": rows}
