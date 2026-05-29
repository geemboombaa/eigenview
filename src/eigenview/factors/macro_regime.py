from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import MacroDaily
from eigenview.factors.base import FactorResult


def score_macro_row(
    dix: float | None,
    gex_index: float | None,
    vix_m1: float | None,
    vix_contango_pct: float | None,
) -> FactorResult:
    """Pure macro regime scorer over already-fetched signal values.

    All four signals None → NO DATA (the regime cannot be validated). This is the
    honest state when every macro source is unavailable — it must NOT masquerade
    as a confident RED 0/10.
    """
    if dix is None and gex_index is None and vix_m1 is None and vix_contango_pct is None:
        return FactorResult.no_data("macro_regime", "no macro data available")

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
        regime, firing = "GREEN", True
    elif score >= settings.macro_regime_red_threshold:
        regime, firing = "YELLOW", True
    else:
        regime, firing = "RED", False

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


async def score_macro_regime(session: AsyncSession) -> FactorResult:
    result = await session.execute(
        select(MacroDaily).order_by(MacroDaily.date.desc()).limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        return FactorResult.no_data("macro_regime", "no macro data in DB")

    return score_macro_row(
        dix=row.dix,
        gex_index=row.gex_index,
        vix_m1=row.vix_m1,
        vix_contango_pct=row.vix_contango_pct,
    )
