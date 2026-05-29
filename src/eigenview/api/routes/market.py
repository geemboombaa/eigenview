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

    # Single source of truth for scoring/regime (same pure scorer the Gate-0 gate uses).
    from eigenview.factors.macro_regime import score_macro_row
    res = score_macro_row(row.dix, row.gex_index, row.vix_m1, row.vix_contango_pct)
    score = int(res.detail.get("score", 0))
    regime = res.label  # GREEN | YELLOW | RED | NO DATA

    parts = []
    if row.dix is not None:
        parts.append(f"DIX {row.dix:.1%}")
    if row.gex_index is not None:
        # gex_index is already Σ dealer gamma in $B (per 1% move) across S&P 500 components.
        parts.append(f"S&P GEX ${row.gex_index:.2f}B")
    if row.vix_m1 is not None:
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
