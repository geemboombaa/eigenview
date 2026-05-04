# Setup Coverage Table — 2026-05-04

## Bucket A — Works in detect_pattern() (proven, has tests)
| Setup | Test file | Notes |
|---|---|---|
| pullback_in_trend | test_technical_pullback.py | 15 tests passing; rolling p40 RSI threshold; real NVDA fixture data |

## Bucket B — Exists in score_technical() only (needs refactor)
| Setup | Location in score_technical() | Hardcoded thresholds | Library needed |
|---|---|---|---|
| bullish_reversal | Lines 230–243 | RSI < 55, vol > 1.8x avg, ADX > 15, 2-bar confirm | scipy (argrelextrema for swing detection) |
| overbought_reversal | Lines 246–260 | RSI > 68, vol > 1.2x avg, ADX > 20 | — |
| compression_break | Lines 263–278 | ATR last5 < 0.7x ATR 20avg, close > BBU, vol > 1.5x | pandas_ta bbands |
| compression_break_down | Lines 280–294 | ATR last5 < 0.7x ATR 20avg, close < BBL, vol > 1.5x | pandas_ta bbands |
| ema_reclaim | Lines 297–308 | close[-3] < EMA50, close now > EMA50, vol > 1.1x | — |
| ema_rejection | Lines 310–322 | close[-3] > EMA50, close now < EMA50, vol > 1.1x | — |
| rally_in_downtrend | Lines 343–356 | RSI 43–62, daily bearish, close < EMA21*1.01 | — |
| base_breakout | Lines 358–370 | ATR last5 < 0.65x 20avg, vol declining 10-bar, close >= 50d max * 0.97 | — |
| base_breakdown | Lines 372–384 | ATR last5 < 0.65x 20avg, vol declining 10-bar, close <= 50d min * 1.03 | — |
| oversold_bounce | Lines 386–397 | RSI < 32, up-day, vol > 1.2x, weekly ADX <= 30 | — |
| failed_breakdown | Lines 399–412 | Low < EMA21, close > EMA21, vol > 1.5x | — |
| breakout | Lines 414–431 | close > 20d recent_high, vol > 1.5x | — |
| breakdown | Lines 433–445 | close < 20d recent_low, vol > 1.5x | — |
| failed_breakout | Lines 447–457 | close[-2] > recent_high, close now < recent_high, vol > 1.2x | — |
| bearish_reversal | Lines 461–469 | RSI > 72, ADX > 25, bear_div, vol > 1.6x | scipy (RSI divergence) |

## Bucket C — Not implemented
| Setup | Category | Library needed | Complexity |
|---|---|---|---|
| pullback_deep | Pullback variant | pandas_ta (Fib retracement) | Low — RSI < 35, price 5–15% below EMA21, weekly pullback |
| pullback_to_structure | Pullback variant | scipy (argrelextrema swing detection) | Medium — needs prior swing high identified, price tests that level |
| flag_continuation | Continuation | pandas_ta | Medium — tight channel on declining vol after impulse leg |
| choch_bullish | Market structure | scipy or custom | High — Change of Character: first higher high after series of lower highs |
| choch_bearish | Market structure | scipy or custom | High — Change of Character: first lower low after series of higher highs |
| bos_bullish | Market structure | scipy or custom | High — Break of Structure: close above most recent swing high |
| bos_bearish | Market structure | scipy or custom | High — Break of Structure: close below most recent swing low |

## Mean Reversion (Q1-gated — scope pending)
| Setup | Notes |
|---|---|
| bb_mean_reversion_long | Not implemented; needs BBL touch + RSI < 30 + mean-reversion regime check |
| bb_mean_reversion_short | Not implemented; needs BBU touch + RSI > 70 + mean-reversion regime check |
| ema200_snap_long | Not implemented; needs close within 1% below EMA200 + bounce confirmation |
| ema200_snap_short | Not implemented; needs close within 1% above EMA200 + rejection confirmation |

## Summary
- Bucket A: 1 setup (pullback_in_trend — detect_pattern() with rolling percentile thresholds + 15 tests)
- Bucket B: 15 setups (score_technical() only — hardcoded RSI/vol thresholds, elif chain, no fixture tests)
- Bucket C: 7 setups (not implemented anywhere)
- Mean reversion (Q1-gated): 4 setups
- **Total mapped: 27 setups (21 primary + 4 mean-reversion + 2 counted in both B and C columns above)**

## Notes
- `pullback_in_trend` exists in BOTH score_technical() (old, hardcoded RSI 38–57) AND detect_pattern() (new, rolling p40). Bucket A applies — the detect_pattern() version is the canonical implementation going forward.
- All 15 Bucket B setups share the same structural problem: hardcoded RSI/vol thresholds baked into a single elif chain, no separate fixture, no dedicated test. Refactor target is detect_pattern() with rolling percentile thresholds per the pullback_in_trend model.
- Bucket C market-structure setups (choch, bos) require swing-point history with proper ordering logic — substantially more work than the indicator-based setups.
