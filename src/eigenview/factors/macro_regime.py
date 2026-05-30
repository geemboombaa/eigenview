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

    gex_ok = gex_index is not None and gex_index > 0
    contango_ok = vix_contango_pct is not None and vix_contango_pct > 0
    dix_ok = dix is not None and dix > settings.macro_dix_bullish_threshold
    vix_ok = vix_m1 is not None and vix_m1 < settings.macro_vix_low_threshold

    max_score = (settings.macro_weight_gex + settings.macro_weight_contango
                 + settings.macro_weight_dix + settings.macro_weight_vix)
    score = (
        (settings.macro_weight_gex if gex_ok else 0)
        + (settings.macro_weight_contango if contango_ok else 0)
        + (settings.macro_weight_dix if dix_ok else 0)
        + (settings.macro_weight_vix if vix_ok else 0)
    )
    score = max(0, min(max_score, score))

    if score >= settings.macro_regime_green_threshold:
        regime, firing = "GREEN", True
    elif score >= settings.macro_regime_red_threshold:
        regime, firing = "YELLOW", True
    else:
        regime, firing = "RED", False

    narrative = (
        f"Macro regime {regime} ({score}/{max_score}): "
        + ", ".join(filter(None, [
            "positive GEX" if gex_ok else None,
            "VIX contango" if contango_ok else None,
            "dark pool buying above threshold" if dix_ok else None,
            "low vol regime" if vix_ok else None,
        ]))
        + "."
    )

    return FactorResult(
        factor_id="macro_regime",
        firing=firing,
        strength=score / max_score,
        label=regime,
        detail={
            "score": score,
            "max_score": max_score,
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
