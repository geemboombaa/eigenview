from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import MacroDaily
from eigenview.factors.base import FactorResult


async def score_macro_regime(session: AsyncSession) -> FactorResult:
    result = await session.execute(
        select(MacroDaily).order_by(MacroDaily.date.desc()).limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return FactorResult.no_data("macro_regime", "no macro data in DB")

    dix = row.dix
    gex_index = row.gex_index
    vix_m1 = row.vix_m1
    vix_contango_pct = row.vix_contango_pct

    score = 0
    if gex_index is not None and gex_index > 0:
        score += 3
    if vix_contango_pct is not None and vix_contango_pct > 0:
        score += 2
    if dix is not None and dix > 0.43:
        score += 3
    if vix_m1 is not None and vix_m1 < 20:
        score += 2
    score = max(0, min(10, score))

    if score >= settings.macro_regime_green_threshold:
        regime = "GREEN"
        firing = True
    elif score >= settings.macro_regime_red_threshold:
        regime = "YELLOW"
        firing = True
    else:
        regime = "RED"
        firing = False

    narrative = (
        f"Macro regime {regime} ({score}/10): "
        + ", ".join(filter(None, [
            "positive GEX" if (gex_index is not None and gex_index > 0) else None,
            "VIX contango" if (vix_contango_pct is not None and vix_contango_pct > 0) else None,
            "dark pool buying above threshold" if (dix is not None and dix > 0.43) else None,
            "low vol regime" if (vix_m1 is not None and vix_m1 < 20) else None,
        ]))
        + "."
    )

    return FactorResult(
        factor_id="macro_regime",
        firing=firing,
        strength=score / 10,
        label=regime,
        detail={
            "score": score,
            "dix": dix,
            "gex_index": gex_index,
            "vix_m1": vix_m1,
            "vix_contango_pct": vix_contango_pct,
        },
        narrative=narrative,
    )
