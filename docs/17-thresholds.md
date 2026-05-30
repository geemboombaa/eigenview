# Thresholds — values, rationale, validation status

**Rule:** no threshold hardcoded in logic. All live in `config.py` (env-overridable). Each must
have a *reason* and be *validated by the user*. This doc is the review surface.

Status legend: ✅ reasoned + accepted · 📐 industry-convention · ⚠️ **ARBITRARY — needs your call**

## Macro regime (Gate 0) — `factors/macro_regime.py`
| Setting | Value | Rationale | Status |
|---|---|---|---|
| `macro_regime_green_threshold` | 7 | ≥7/10 = strong tailwind; decisions log 2026-04-29 | ✅ |
| `macro_regime_red_threshold` | 3 | ≤3 blocks longs; calibrated to avoid blocking coiled/pre-rally states | ✅ |
| `macro_dix_bullish_threshold` | 0.43 | SqueezeMetrics DIX >43% = dark-pool buying; calibrated 45→43 (decisions log) | ✅ |
| `macro_vix_low_threshold` | 20.0 | VIX <20 = classic low-vol regime line | 📐 |
| `macro_weight_gex` / `_dix` | 3 / 3 | GEX + DIX weighted higher (positioning + flow) | ⚠️ why 3 not 2? |
| `macro_weight_contango` / `_vix` | 2 / 2 | VIX-derived signals weighted lower | ⚠️ |

## Pick gates (synthesis) — `config.py`
| Setting | Value | Rationale | Status |
|---|---|---|---|
| `min_rr_ratio` | 3.0 | reward:risk floor for any pick | ⚠️ 3.0 vs 2.0? (CLAUDE.md TA spec says 2.0 min) — **conflict, your call** |
| `min_avg_daily_dollar_volume` | 15M | options-tradeable liquidity floor; $50M over-filtered NDX | ✅ |
| `rs_percentile_min` | 50 | longs top-50% RS / shorts bottom-50% | 📐 |
| `ta_pattern_confidence_threshold` | 0.6 | min pattern confidence to fire | ⚠️ |
| `flow_min_premium_usd` | 500,000 | "institutional" premium floor | 📐 |
| `flow_min_voi_ratio` | 3.0 | V/OI ≥3 = new position vs existing | 📐 (EigenView spec) |
| `dormant_firing_threshold` | 0.5 | dormant strength to fire | ⚠️ |
| `sentiment_novelty_z_threshold` | 1.5 | novelty z to flag (sentiment rebuild pending) | ⚠️ |

## Conviction tiers — `synthesis/gate.py`
| Setting | Value | Rationale | Status |
|---|---|---|---|
| `conviction_strength_weight` / `_count_weight` | 0.65 / 0.35 | blend avg-strength vs #factors | ⚠️ |
| `conviction_t5/t4/t3/t2_threshold` | 0.80/0.60/0.40/0.20 | 5/4/3/2-star cutoffs | ⚠️ evenly-spaced guess |

## Entry / stop construction — `synthesis/gate.py`
| Setting | Value | Rationale | Status |
|---|---|---|---|
| `entry_zone_long_frac` / `_short_frac` | 0.30 / 0.15 | entry band depth as frac of swing range | ⚠️ |
| `stop_buffer_pct` | 0.02 | 2% beyond swing for stop | 📐 |
| `tier_d_flow_strength` / `_dormant_strength` | 0.70 / 0.60 | strong single-signal bench cutoffs | ⚠️ |

## Known hardcode still in code (not yet config-ified) — flagged
| Location | Literal | Issue |
|---|---|---|
| `factors/gex.py` | `strength=0.1` (long), `0.3` (flip), `/1e9` short scale | GEX strength is a **constant**, not a measurement — only the regime label is real. De-hardcode or drop strength (ties to "honest representation" UI fix). |
| `factors/dormant.py` / `activation.py` | many `activation_*` / `dormant_*` already in config ✅ | but the 6-signal **weights** producing the 1/7,2/7… ratios — confirm they're config-driven |

## How to validate
For each ⚠️: tell me the value + reason, or "keep + accept". I'll set it in `config.py` with your
rationale recorded here. Nothing ships with an unvalidated ⚠️ that gates picks.
