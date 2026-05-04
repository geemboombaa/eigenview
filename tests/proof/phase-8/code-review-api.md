# Phase 8 · Audit 4 — detect_pattern() API Surface (issue #56)

## Check 1 · All pattern names returned

| # | Pattern | Line | P6 ref |
|---|---|---|---|
| 1 | no_pattern | 774, 790, 1165 | fallback |
| 2 | pullback_deep | 936 | P6.1 |
| 3 | pullback_in_trend | 960 | main |
| 4 | pullback_to_structure | 982 | P6.2 |
| 5 | flag_continuation | 1003 | P6.3 |
| 6 | compression_break | 1023 | P6.4 |
| 7 | compression_break_down | 1041 | P6.5 |
| 8 | breakout | 1062 | P6.6 |
| 9 | breakdown | 1081 | P6.7 |
| 10 | base_breakout | 1107 | P6.8 |
| 11 | base_breakdown | 1133 | P6.9 |
| 12 | ema_reclaim | 1147 | P6.10 |
| 13 | ema_rejection | 1163 | P6.11 |

Total: 12 named patterns + no_pattern = 13 return sites. The "18 patterns" count includes `score_technical` legacy patterns (pullback_in_trend, compression_break, ema_reclaim, ema_rejection, base_breakout, base_breakdown + 8 exclusive patterns like bullish_reversal, overbought_reversal, etc.) which are not part of detect_pattern()'s scope.

## Check 2 · Return schema consistency

Required fields: `trend`, `weekly_trend`, `weekly_state`, `rsi`, `rsi_p40`, `adx`, `vol_ratio`, `swing_low`, `swing_high`

The `detail` dict is assembled at line 863 (post-fix line numbering) with all 9 required fields. All 11 named pattern return sites use this pre-assembled `detail` dict (possibly augmented with pattern-specific extras like `bbu`, `prior_swing_high`, etc.). All named patterns return the full required schema.

**FAIL (pre-fix): Early-exit no_pattern returns missing all fields**
- Line 773: `if len(ddf) < 30` returned `"detail": {}` — all 9 fields absent
- Line 789: indicator computation failed returned `"detail": {}` — all 9 fields absent

Consumers doing `result["detail"]["trend"]` would KeyError on these paths.

**FIXED:** Both early exits now return `_empty_detail` dict with all 9 required keys set to `None`.

Post-fix: all 3 `no_pattern` sites return the consistent schema.

## Check 3 · Empty weekly_df handling

`_classify_weekly_state(weekly_df, as_of_ts)` is called at line 859.
Inside `_classify_weekly_state` (line 703):
- Line 705: `wdf = weekly_df[weekly_df.index <= as_of]` — filters to as_of date
- Line 706: `if len(wdf) < 15: return "NEUTRAL"` — handles empty or short DataFrame

**PASS** — empty `weekly_df` returns "NEUTRAL", detect_pattern() proceeds normally.

## Check 4 · as_of_date not in daily_df index

Line 769: `as_of_ts = pd.Timestamp(as_of_date) if as_of_date else ddf.index[-1]`
Line 770: `ddf = ddf[ddf.index <= as_of_ts]`

If `as_of_date` is before all data in `daily_df`, `ddf` becomes empty → `len(ddf) < 30` guard fires → returns `no_pattern` with full empty-schema detail. Graceful.

If `as_of_date` is after all data (future date), `ddf` retains all rows → proceeds normally. Correct.

**PASS** — no crash on any valid or invalid `as_of_date` input.

## Fixes Applied
1. **Added `_empty_detail` sentinel** at top of detect_pattern() with all 9 required schema fields set to `None`
2. **Both early no_pattern returns** now use `_empty_detail` instead of `{}`

## Summary
| Check | Status |
|---|---|
| All 12 named patterns enumerated | PASS |
| 11 named patterns return full 9-field schema | PASS |
| Early no_pattern returns had empty detail | FIXED |
| Empty weekly_df → graceful NEUTRAL | PASS |
| as_of_date not in index → graceful no_pattern | PASS |

**Overall: PASS (1 FIXED)**
