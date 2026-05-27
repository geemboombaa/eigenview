"""Activation engine — is a *dormant* bet waking up?

The dormant screen (factors/dormant.py) finds big sleeping positions. This layer
sits on top and answers: has this contract changed *significantly from its dormant
baseline*?

Logic (per user): compare the DORMANT BASELINE (median/avg over the older part of
the window, while it was asleep) to the RECENT state (last few days). Fire on a big
jump in ANY of:
  - OI        : current OI well above its dormant baseline   (accumulation)
  - volume    : a recent day traded far above its dormant norm (sudden activity)
  - IV        : implied vol jumped above its dormant baseline  (demand)
  - underlying: the stock moved hard in the bet's direction on heavy volume

This is NOT day-over-day — gradual accumulation over weeks still trips it, because
we compare to the sleeping baseline, not to yesterday.

Born-on (true age) is read from the OI ramp so we know if a position was quietly
built months ago (the insider tell) vs brand new.

All thresholds live in config (settings.activation_*) so they tune without code edits.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date

from eigenview.config import settings


@dataclass
class ActivationResult:
    fired: bool
    triggers: list[str] = field(default_factory=list)
    strength: float = 0.0
    born_on: date | None = None
    age_days: int | None = None
    detail: dict = field(default_factory=dict)


def _is_call(call_put: str) -> bool:
    return str(call_put).upper().startswith("C")


def _median(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return statistics.median(xs) if xs else None


def _mean(xs: list[float]) -> float | None:
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _last_valid(xs: list) -> float | None:
    for v in reversed(xs):
        if v is not None and v == v:  # not None, not NaN
            return v
    return None


def _born_on(dates: list[date], ois: list[int | None]) -> date | None:
    present = [(d, o) for d, o in zip(dates, ois) if o]
    if not present:
        return None
    peak = max(o for _, o in present)
    for d, o in present:
        if o >= settings.activation_age_oi_frac * peak:
            return d
    return present[0][0]


def score_activation(
    hist: list[dict],
    underlying: list[dict],
    call_put: str,
    target: date,
) -> ActivationResult:
    """`hist`: ascending daily dicts {date, oi, volume, close, iv}.
    `underlying`: ascending daily dicts {date, close, volume}.

    Splits the series into a dormant BASELINE (older) and a RECENT window, then
    fires on a significant baseline->recent jump in any signal.
    """
    recent_days = settings.activation_recent_days
    hist = sorted(hist, key=lambda r: r["date"] if r["date"] <= target else date.min)
    hist = [r for r in hist if r["date"] <= target]
    if len(hist) < settings.activation_min_history:
        return ActivationResult(fired=False, detail={"reason": "insufficient_history"})

    dates = [r["date"] for r in hist]
    ois = [r.get("oi") for r in hist]
    vols = [r.get("volume") for r in hist]
    ivs = [r.get("iv") for r in hist]

    base = slice(0, len(hist) - recent_days)
    rec = slice(len(hist) - recent_days, len(hist))

    born = _born_on(dates, ois)
    age = (target - born).days if born else None

    triggers: list[str] = []
    detail: dict = {}

    # OI: current vs dormant baseline (catches gradual accumulation)
    base_oi = _median(ois[base])
    cur_oi = _last_valid(ois[rec]) or _last_valid(ois)
    if base_oi and cur_oi:
        d_oi = cur_oi - base_oi
        detail["base_oi"] = round(base_oi)
        detail["cur_oi"] = round(cur_oi)
        detail["oi_jump_pct"] = round(d_oi / base_oi, 3)
        if d_oi >= settings.activation_oi_min_delta and d_oi >= settings.activation_oi_jump_pct * base_oi:
            triggers.append("oi_jump")

    # Volume: rec_vol_peak = max single-day volume in the recent 10-day window.
    # Compared against base_vol = mean daily volume over the entire baseline (dormant) period.
    # Fires only if the peak recent day is >= 10x the sleeping average AND >= 1000 contracts.
    base_vol = _mean(vols[base])
    rec_vol_peak = max([v for v in vols[rec] if v is not None], default=0)
    if base_vol is not None:
        detail["base_vol_avg"] = round(base_vol, 1)
        detail["rec_vol_peak"] = rec_vol_peak
        if rec_vol_peak >= settings.activation_vol_min and rec_vol_peak >= settings.activation_vol_mult * max(base_vol, 1):
            triggers.append("volume_surge")

    # IV: current vs dormant baseline
    base_iv = _median(ivs[base])
    cur_iv = _last_valid(ivs[rec])
    if base_iv and cur_iv:
        detail["iv_jump"] = round(cur_iv - base_iv, 4)
        if cur_iv - base_iv >= settings.activation_iv_jump_abs:
            triggers.append("iv_jump")

    # Underlying: recent move in the bet's direction on heavy volume
    u = sorted([r for r in underlying if r["date"] <= target], key=lambda r: r["date"])
    if len(u) > recent_days + 5:
        u_close = [r.get("close") for r in u]
        u_vol = [r.get("volume") for r in u]
        u_base_close = _median(u_close[: len(u) - recent_days])
        u_cur_close = _last_valid(u_close[len(u) - recent_days:])
        u_base_vol = _mean(u_vol[: len(u) - recent_days])
        u_rec_vol_peak = max([v for v in u_vol[len(u) - recent_days:] if v is not None], default=0)
        if u_base_close and u_cur_close:
            move = u_cur_close / u_base_close - 1
            directional = move if _is_call(call_put) else -move
            detail["und_move"] = round(directional, 3)
            if (directional >= settings.activation_und_move_pct and u_base_vol
                    and u_rec_vol_peak >= settings.activation_und_vol_mult * u_base_vol):
                triggers.append("underlying_move")

    return ActivationResult(
        fired=len(triggers) >= settings.activation_min_triggers,
        triggers=triggers,
        strength=round(len(triggers) / settings.activation_max_triggers, 3),
        born_on=born,
        age_days=age,
        detail=detail,
    )
