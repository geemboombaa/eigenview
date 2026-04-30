from __future__ import annotations

from datetime import date

from fastapi import APIRouter
from sqlalchemy import select

from eigenview.data.storage import AsyncSessionLocal, MacroDaily

router = APIRouter()


@router.get("/market/regime")
async def get_regime() -> dict:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MacroDaily).order_by(MacroDaily.date.desc()).limit(1)
        )
        row = result.scalar_one_or_none()

    if row is None:
        return {
            "score": 0,
            "regime": "UNKNOWN",
            "dix": None,
            "gex_index": None,
            "vix_m1": None,
            "vix_m2": None,
            "vix_contango_pct": None,
            "narrative": "No macro data. Run: eigenview fetch-macro",
        }

    # Recompute score from stored values
    score = 0
    if row.gex_index and row.gex_index > 0:
        score += 3
    if row.vix_contango_pct and row.vix_contango_pct > 0:
        score += 2
    if row.dix and row.dix > 0.43:
        score += 3
    if row.vix_m1 and row.vix_m1 < 20:
        score += 2
    score = min(10, max(0, score))

    if score >= 7:
        regime = "GREEN"
    elif score >= 3:
        regime = "YELLOW"
    else:
        regime = "RED"

    parts = []
    if row.dix:
        parts.append(f"DIX {row.dix:.1%}")
    if row.gex_index:
        parts.append(f"SPX GEX ${row.gex_index/1e9:.1f}B")
    if row.vix_m1:
        parts.append(f"VIX {row.vix_m1:.1f}")
    narrative = f"Macro regime {regime} ({score}/10): {', '.join(parts)}."

    return {
        "score": score,
        "regime": regime,
        "dix": row.dix,
        "gex_index": row.gex_index,
        "vix_m1": row.vix_m1,
        "vix_m2": row.vix_m2,
        "vix_contango_pct": row.vix_contango_pct,
        "narrative": narrative,
        "date": str(row.date),
    }
