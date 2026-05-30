"""TA scan with quality filters applied in sequence:
  1. Liquidity: avg daily dollar volume >= min_avg_daily_dollar_volume
  2. TA fires
  3. RS rank: longs must be top 50% of universe by 20d return; shorts bottom 50%
  4. R:R >= min_rr_ratio (ATR-based stop, pattern-specific target)

No data pull — reads from DB prices only.
Config values: config.py (min_avg_daily_dollar_volume, min_rr_ratio, rs_percentile_min).
"""
import asyncio
import sys
sys.path.insert(0, "src")

import numpy as np
import pandas_ta as _pta  # noqa: F401 — registers df.ta accessor

from collections import Counter

from eigenview.config import settings
from eigenview.data.universe import get_universe
from eigenview.synthesis.scanner import _fetch_live, _score_with_lookback
from eigenview.synthesis.gate import SHORT_SETUP_PATTERNS, estimate_target

_HIGH = {
    "pullback", "breakout", "ema_reclaim", "reversal_long",
    "rally_short", "breakdown", "ema_rejection", "reversal_short",
}


async def main() -> None:
    tickers = await get_universe(settings.universe)

    # ── Pass 1: fetch all frames + compute RS 20d return ─────────────────────
    print("Pass 1: loading prices + RS returns …")
    frames: dict[str, object] = {}
    returns_20d: dict[str, float] = {}

    for t in tickers:
        df = await _fetch_live(t)
        if df is None or df.empty or len(df) < 25:
            continue
        frames[t] = df
        ret = float(df["close"].iloc[-1] / df["close"].iloc[-21] - 1) if len(df) >= 21 else 0.0
        returns_20d[t] = ret

    rs_all   = list(returns_20d.values())
    rs_med   = float(np.median(rs_all)) if rs_all else 0.0
    rs_p50   = rs_med  # top-50% threshold for longs / bottom-50% threshold for shorts

    print(
        f"Universe: {len(frames)} tickers  |  "
        f"RS 20d median: {rs_med*100:+.2f}%  "
        f"(longs need >{rs_med*100:.2f}%, shorts need <{rs_med*100:.2f}%)"
    )

    # ── Pass 2: apply filter funnel ───────────────────────────────────────────
    total     = 0
    liq_fail  = 0
    ta_fired  = 0
    rs_fail   = 0
    rr_fail   = 0
    rr_skip   = 0   # target could not be computed — passed through
    qualified = 0
    longs     = 0
    shorts    = 0
    labels: Counter[str] = Counter()
    tiers:  Counter[str] = Counter()
    rr_vals: list[float] = []

    for t, df in frames.items():
        if len(df) < 30:
            continue
        total += 1

        # ── Gate 1: liquidity ─────────────────────────────────────────────────
        adv = float(df["close"].tail(20).mean() * df["volume"].tail(20).mean())
        if settings.enable_liquidity_filter and adv < settings.min_avg_daily_dollar_volume:
            liq_fail += 1
            continue

        # ── Gate 2: TA fires ──────────────────────────────────────────────────
        r = _score_with_lookback(df, t)
        if not r.firing:
            continue
        ta_fired += 1

        is_short = r.label in SHORT_SETUP_PATTERNS

        # ── Gate 3: RS rank ───────────────────────────────────────────────────
        rs = returns_20d.get(t, 0.0)
        if settings.enable_rs_filter:
            if is_short:
                if rs > rs_p50:        # short needs to be underperformer
                    rs_fail += 1
                    continue
            else:
                if rs < rs_p50:        # long needs to be outperformer
                    rs_fail += 1
                    continue

        # ── Gate 4: R:R ───────────────────────────────────────────────────────
        entry = float(df["close"].iloc[-1])

        # ATR14 for stop sizing
        try:
            _df_atr = df.copy()
            _df_atr.ta.atr(length=14, append=True)
            _atr_col = next(
                (c for c in _df_atr.columns if c.startswith("ATRr_") or c.startswith("ATR_")),
                None,
            )
            atr = float(_df_atr[_atr_col].iloc[-1]) if _atr_col else entry * 0.02
        except Exception:
            atr = entry * 0.02

        stop   = (entry + atr) if is_short else (entry - atr)
        target = estimate_target(r.label, r.detail or {}, entry, stop, df)

        if target is not None:
            rr = abs(target - entry) / max(abs(entry - stop), 1e-6)
            rr_vals.append(rr)
            if settings.enable_rr_filter and rr < settings.min_rr_ratio:
                rr_fail += 1
                continue
        else:
            rr_skip += 1  # no target computable — pass through, flag in output

        # ── Passed all gates ──────────────────────────────────────────────────
        qualified += 1
        labels[r.label] += 1
        tier = (r.detail or {}).get("probability_tier", "UNKNOWN")
        tiers[tier] += 1
        if is_short:
            shorts += 1
        else:
            longs += 1

    # ── Report ────────────────────────────────────────────────────────────────
    adv_m = settings.min_avg_daily_dollar_volume / 1_000_000

    active = " | ".join(filter(None, [
        f"LIQ ${settings.min_avg_daily_dollar_volume//1_000_000}M" if settings.enable_liquidity_filter else None,
        f"RS p{settings.rs_percentile_min}" if settings.enable_rs_filter else None,
        f"RR {settings.min_rr_ratio:.0f}:1" if settings.enable_rr_filter else None,
    ])) or "none"
    print(f"\n{'='*58}")
    print(f"  FILTER FUNNEL  [{settings.universe.upper()}]  active={active}")
    print(f"{'='*58}")
    print(f"  Universe tickers          {len(frames):>5}")
    print(f"  With >=30 bars            {total:>5}")
    print(f"  Failed liquidity (<${adv_m:.0f}M)  {liq_fail:>5}")
    print(f"  TA fired                  {ta_fired:>5}")
    print(f"  Failed RS rank            {rs_fail:>5}  (wrong side of median {rs_med*100:+.2f}%)")
    print(f"  Failed R:R (<{settings.min_rr_ratio:.0f}:1)         {rr_fail:>5}")
    print(f"  R:R skipped (no target)   {rr_skip:>5}  (passed through)")
    print(f"  {'-'*40}")
    print(f"  QUALIFIED                 {qualified:>5}  (longs={longs}  shorts={shorts})")

    if rr_vals:
        print(f"\n  R:R stats (computed targets only)")
        print(f"    median {np.median(rr_vals):.2f}  mean {np.mean(rr_vals):.2f}  "
              f"min {min(rr_vals):.2f}  max {max(rr_vals):.2f}")

    print(f"\n  By tier:")
    for tier, c in sorted(tiers.items()):
        print(f"    {tier:<15} {c:>4}")

    print(f"\n  {'Pattern':<25} {'Count':>5}  Tier")
    print(f"  {'-'*40}")
    for lab, c in labels.most_common():
        t_label = "HIGH" if lab in _HIGH else "SPEC"
        print(f"  {lab:<25} {c:>5}  [{t_label}]")


if __name__ == "__main__":
    asyncio.run(main())
