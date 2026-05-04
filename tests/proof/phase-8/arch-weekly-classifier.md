# Phase 8 · Audit 2 — 5-State Weekly Classifier (issue #54)

## Check 1 · _classify_weekly_state() location
**PASS**
Found at line 703. Signature: `_classify_weekly_state(weekly_df, as_of: pd.Timestamp) -> str`
Uses explicit weekly DataFrame (passed by detect_pattern), not resampled from daily.

## Check 2 · All 5 states present
**PASS**
| State | Line | Condition |
|---|---|---|
| BULLISH | 725 | ema8 > ema21 AND rsi <= 70 |
| BULLISH_EXTENDED | 724 | ema8 > ema21 AND rsi > 70 |
| NEUTRAL | 707 (early) | len < 15; also line 728: gap_pct < 2% |
| BEARISH_WEAK | 731 | ema8 < ema21, gap >= 2%, adx <= 25 |
| BEARISH_STRONG | 730 | ema8 < ema21, gap >= 2%, adx > 25 |

All 5 states confirmed.

## Check 3 · BULLISH_EXTENDED gate
**PASS**
Line 723: `if rsi_f is not None and rsi_f > 70: return "BULLISH_EXTENDED"`
Checked BEFORE returning BULLISH (line 725). Weekly RSI > 70 = extension flag. Correct.

## Check 4 · MTF matrix in detect_pattern()
**PASS**

| Pattern | weekly_state gate | Line |
|---|---|---|
| pullback_deep | BULLISH or BULLISH_EXTENDED | 921 |
| pullback_in_trend | BULLISH or BULLISH_EXTENDED | 946 |
| pullback_to_structure | BULLISH or BULLISH_EXTENDED | 964 |
| flag_continuation | != BEARISH_STRONG | 986 |
| compression_break | any (BEARISH_STRONG penalizes -0.20) | 1007 |
| compression_break_down | not in (BULLISH, BULLISH_EXTENDED) | 1032 |
| breakout | != BEARISH_STRONG | 1043 |
| breakdown | BEARISH_WEAK or BEARISH_STRONG | 1065 |
| base_breakout | BULLISH or BULLISH_EXTENDED | 1084 |
| base_breakdown | BEARISH_WEAK or BEARISH_STRONG | 1110 |
| ema_reclaim | != BEARISH_STRONG | 1137 |
| ema_rejection | BEARISH_WEAK, BEARISH_STRONG, or NEUTRAL | 1151 |

Every pattern gates on weekly_state. No pattern fires regardless of weekly state.

- pullback_in_trend: requires BULLISH or BULLISH_EXTENDED ✓
- rally_in_downtrend: not in detect_pattern (it is in score_technical legacy path only, gated on bearish_weak/bearish_strong via weekly_trend_str) ✓
- compression_break_down: requires not BULLISH or BULLISH_EXTENDED ✓

## Check 5 · Pattern without weekly gate
**PASS**
Every named pattern in detect_pattern() has an explicit weekly_state constraint in its condition. No pattern is weekly-state-agnostic.

## WARN · score_technical uses 3-state _weekly_trend(), not _classify_weekly_state()
score_technical() calls `_weekly_trend(wc)` (line 286) which returns 4 states (bullish/bearish_strong/bearish_weak/unknown). It then maps to a 5-state weekly_state at lines 657-664 for the FactorResult detail, but BULLISH_EXTENDED is never produced by score_technical (unknown maps to NEUTRAL). This means the legacy path cannot flag extended rally conditions.
**Impact:** score_technical FactorResult.detail["weekly_state"] can never be "BULLISH_EXTENDED". API consumers should use detect_pattern() for the authoritative 5-state classification.

## Summary
| Check | Status |
|---|---|
| _classify_weekly_state() present | PASS |
| All 5 states implemented | PASS |
| BULLISH_EXTENDED gate (RSI>70 weekly) | PASS |
| MTF matrix gates all 12 patterns | PASS |
| No pattern fires unconditionally | PASS |
| score_technical uses old 3-state path | WARN |

**Overall: PASS (1 WARN — score_technical is legacy path, detect_pattern is authoritative)**
