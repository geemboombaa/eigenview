# Phase 8 · Audit 3 — Code Review: technical.py (issue #55)

## Function Inventory

| Function | Start | End | Lines | Status | Notes |
|---|---|---|---|---|---|
| _compute_weekly_context | 23 | 60 | 38 | PASS | Clean, well-bounded |
| _weekly_trend | 63 | 71 | 9 | PASS | Simple classifier |
| _vol_character | 74 | 91 | 18 | PASS | Linear regression slope |
| _rsi_divergence | 94 | 116 | 23 | PASS | Pivot-scan approach |
| _compute_fib_levels | 119 | 133 | 15 | PASS | Dictionary return |
| score_technical | 136 | 693 | 558 | FLAG | Monolith — legacy path |
| _classify_weekly_state | 703 | 731 | 29 | PASS | 5-state classifier |
| _swing_low | 734 | 741 | 8 | PASS | argrelextrema wrapper |
| _swing_high | 744 | 751 | 8 | PASS | argrelextrema wrapper |
| detect_pattern | 754 | 1165 | 412 | FLAG | Monolith — new path |

**Functions > 100 lines:** `score_technical` (558 lines), `detect_pattern` (412 lines). Both are documented monoliths by design — the long body is sequential elif chains, not nested complexity. Refactoring into sub-functions is post-MVP work. Not a bug, but noted.

## Dead Code Check

**WARN: Duplicate rsi_p60 assignment (FIXED)**
Lines 198-200 (pre-fix): `rsi_p60` was assigned twice — once correctly at line 198, then immediately overwritten by an identical expression at line 200 (between `rsi_p62` and `rsi_p65` assignments). This was dead code (the second assignment had no effect). Fixed: removed duplicate line 200.

**WARN: score_technical and detect_pattern both implement patterns**
Both functions implement `compression_break`, `ema_reclaim`, `ema_rejection`, `base_breakout`, `base_breakdown`, `pullback_in_trend`, `breakout`, `breakdown`. These are not dead code — they are two independent code paths:
- `score_technical`: legacy path, single DataFrame, 4-state weekly, used by scanner
- `detect_pattern`: new path, explicit daily+weekly DataFrames, 5-state weekly, used by tests
Risk: pattern logic can diverge between paths. Recommend using detect_pattern() as the single authority post-MVP and deprecating the pattern detection logic in score_technical().

## score_technical vs detect_pattern relationship
**PASS (independent paths, not callers of each other)**
`score_technical` does NOT call `detect_pattern`. They are independent. This matches the design intent: score_technical is the production path wired to the API; detect_pattern is the testable, auditable path used for unit testing.

## Hardcoded thresholds in detect_pattern (lines 754+)
**PASS**
Checked numeric literals in detect_pattern() pattern blocks:
- RSI comparisons: all use `rsi_p*_dp` percentile variables — no hardcoded RSI numbers
- ADX comparisons: all use `adx_p*_dp` percentile variables
- Vol comparisons: all use `vol_p*_dp` percentile variables
- Exceptions (intentional): `rsif < 90.0` in compression_break (absolute ceiling — correct, not a threshold), `_impulse > 5.0` in flag_continuation (percentage impulse check — structural constant, not a regime threshold), EMA proximity checks like `* 0.96` / `* 1.04` (structural band, not a signal threshold)

No inappropriate hardcoded signal thresholds found.

## Fixes Applied
1. **Removed duplicate rsi_p60 assignment** (line 200 in original) — eliminates dead redundant computation

## Summary
| Check | Status |
|---|---|
| Functions > 100 lines | FLAG (score_technical 558L, detect_pattern 412L — by design) |
| Dead code: duplicate rsi_p60 assignment | FIXED |
| Dead code: pattern duplication across paths | WARN (by design — tracked) |
| score_technical calls detect_pattern | PASS (independent) |
| Hardcoded thresholds in detect_pattern | PASS |

**Overall: PASS (1 FIXED, 1 WARN by design)**
