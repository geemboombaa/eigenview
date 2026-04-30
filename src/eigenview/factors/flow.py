from __future__ import annotations

from eigenview.config import settings
from eigenview.factors.base import FactorResult


def score_flow(chains: list, ticker: str = "") -> FactorResult:
    if not chains:
        return FactorResult.no_data("flow", "no chain data")

    call_premium = 0.0
    put_premium = 0.0
    qualified: list[tuple[str, float]] = []  # (call_put, premium)

    for c in chains:
        bid = c.bid or 0.0
        ask = c.ask or 0.0
        volume = c.volume or 0
        oi = c.oi or 0

        mid = (bid + ask) / 2.0
        premium = mid * volume * 100
        voi = volume / oi if oi > 0 else 0.0

        if premium >= settings.flow_min_premium_usd and voi >= settings.flow_min_voi_ratio:
            qualified.append((c.call_put, premium))
            if c.call_put.lower() == "c":
                call_premium += premium
            else:
                put_premium += premium

    if not qualified:
        return FactorResult(
            factor_id="flow",
            firing=False,
            strength=0.0,
            label="NO FLOW",
            detail={
                "largest_sweep_usd": 0.0,
                "total_qualified": 0,
                "call_premium": 0.0,
                "put_premium": 0.0,
                "dominant_side": "none",
            },
            narrative="No qualified sweeps above threshold.",
        )

    largest_sweep = max(p for _, p in qualified)
    total_qualified = len(qualified)
    dominant_side = "calls" if call_premium >= put_premium else "puts"

    fires = total_qualified >= 1 and largest_sweep >= settings.flow_min_premium_usd
    strength = min(1.0, largest_sweep / 2_000_000)

    ratio = (call_premium / put_premium) if put_premium > 0 else float("inf")
    if ratio == float("inf"):
        ratio_str = "∞"
    else:
        ratio_str = f"{ratio:.1f}"

    narrative = (
        f"Aggressive {dominant_side} flow: {total_qualified} qualified sweep(s), "
        f"largest ${largest_sweep / 1e6:.2f}M. "
        f"Call/put premium ratio {ratio_str}:1."
    )

    return FactorResult(
        factor_id="flow",
        firing=fires,
        strength=strength,
        label=dominant_side,
        detail={
            "largest_sweep_usd": largest_sweep,
            "total_qualified": total_qualified,
            "call_premium": call_premium,
            "put_premium": put_premium,
            "dominant_side": dominant_side,
        },
        narrative=narrative,
    )
