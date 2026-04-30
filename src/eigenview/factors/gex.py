from __future__ import annotations

from eigenview.factors.base import FactorResult


def score_gex(chains: list, spot_price: float, ticker: str = "") -> FactorResult:
    if not chains:
        return FactorResult.no_data("gex", "no chain data")

    valid = [c for c in chains if c.gamma is not None and c.oi is not None]
    if not valid:
        return FactorResult.no_data("gex", "no chain data")

    call_gex_by_strike: dict[float, float] = {}
    put_gex_by_strike: dict[float, float] = {}
    call_oi_by_strike: dict[float, float] = {}
    put_oi_by_strike: dict[float, float] = {}

    for c in valid:
        gex_val = c.gamma * c.oi * 100 * spot_price ** 2 * 0.01
        if c.call_put == "C":
            call_gex_by_strike[c.strike] = call_gex_by_strike.get(c.strike, 0.0) + gex_val
            call_oi_by_strike[c.strike] = call_oi_by_strike.get(c.strike, 0.0) + (c.oi or 0)
        else:
            put_gex_by_strike[c.strike] = put_gex_by_strike.get(c.strike, 0.0) + gex_val
            put_oi_by_strike[c.strike] = put_oi_by_strike.get(c.strike, 0.0) + (c.oi or 0)

    net_gex = sum(call_gex_by_strike.values()) - sum(put_gex_by_strike.values())

    call_wall: float | None = None
    call_candidates = {k: v for k, v in call_oi_by_strike.items() if k > spot_price}
    if call_candidates:
        call_wall = max(call_candidates, key=call_candidates.__getitem__)

    put_wall: float | None = None
    put_candidates = {k: v for k, v in put_oi_by_strike.items() if k < spot_price}
    if put_candidates:
        put_wall = max(put_candidates, key=put_candidates.__getitem__)

    gamma_flip = _find_gamma_flip(call_gex_by_strike, put_gex_by_strike, spot_price)

    flip_zone = False
    if gamma_flip is not None and spot_price > 0:
        flip_zone = abs(spot_price - gamma_flip) / spot_price <= 0.05

    if flip_zone:
        regime = "flip_zone"
        firing = True
        strength = 0.3
    elif net_gex < 0:
        regime = "short_gamma"
        firing = True
        strength = min(1.0, abs(net_gex) / 1e9)
    else:
        regime = "long_gamma"
        firing = False
        strength = 0.1

    cw_str = f"${call_wall:,.0f}" if call_wall else "N/A"
    pw_str = f"${put_wall:,.0f}" if put_wall else "N/A"
    gf_str = f"${gamma_flip:,.0f}" if gamma_flip else "N/A"

    if regime == "short_gamma":
        narrative = (
            f"Short gamma regime (net GEX: ${net_gex / 1e9:.2f}B). "
            f"Call wall {cw_str}, put wall {pw_str}. Dealer hedging amplifies moves."
        )
    elif regime == "flip_zone":
        narrative = (
            f"Near gamma flip {gf_str} (spot ${spot_price:,.0f}). "
            f"Regime transition zone — elevated vol risk."
        )
    else:
        narrative = (
            f"Long gamma regime (net GEX: ${net_gex / 1e9:.2f}B). "
            f"Call wall {cw_str}, put wall {pw_str}. Moves likely suppressed."
        )

    return FactorResult(
        factor_id="gex",
        firing=firing,
        strength=strength,
        label=regime,
        detail={
            "net_gex": net_gex,
            "call_wall": call_wall,
            "put_wall": put_wall,
            "gamma_flip": gamma_flip,
            "regime": regime,
        },
        narrative=narrative,
    )


def _find_gamma_flip(
    call_gex: dict[float, float],
    put_gex: dict[float, float],
    spot_price: float,
) -> float | None:
    all_strikes = sorted(set(call_gex) | set(put_gex))
    if len(all_strikes) < 2:
        return None

    net_by_strike = {
        s: call_gex.get(s, 0.0) - put_gex.get(s, 0.0) for s in all_strikes
    }

    prev_strike = None
    prev_net = None
    for strike in all_strikes:
        curr_net = net_by_strike[strike]
        if prev_net is not None and prev_net * curr_net < 0:
            # linear interpolation
            frac = abs(prev_net) / (abs(prev_net) + abs(curr_net))
            return prev_strike + frac * (strike - prev_strike)
        prev_strike = strike
        prev_net = curr_net
    return None
