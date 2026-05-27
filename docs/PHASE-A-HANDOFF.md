# Phase A Handoff — TA Engine Swap (fresh-session prompt)

## State as of commit fc702c4 (branch feature/scanner-factor-scores-write)

Done and merged:
- Dormant firing = **activation engine only**. Static rubric (4/7≈0.57) no longer fires.
- Options-liquidity gate: agg chain OI < `dormant_min_ticker_oi` (5,000) → `NOT_LIQUID`, skipped.
- All activation/dormant/scanner thresholds moved to `config.py`. TA lookback 10→3.
- Liquid contract history downloaded: `contract_history` 125 → **446 tickers / 146,022 rows**.
- Dormant fire count after download: 23 → **81** (all activation-triggered, all liquid).
- `docs/dormant-flow.md` documents the dormant pipeline (Stage 4 marked vestigial).

NOT done: Phase A (the TA engine swap). Everything below.

## Locked decisions for Phase A (do NOT re-litigate)

1. **Single engine = `detect_pattern`** (27 setups, has 5-state MTF + BOS/CHoCH via smartmoneyconcepts). The naive 15-pattern body inside `score_technical` is deleted.
2. **`score_technical` stays as the name** — becomes a thin **adapter**: build weekly_df, call `detect_pattern`, map dict → `FactorResult`. Both `scanner.py` and `api/routes/ta_scan.py` keep calling `score_technical(df, ticker)` unchanged.
3. **Fire on structural gates. NO confidence number. NO 0.70 floor. NO calibration.** A pattern fires iff its hard gates pass (weekly MTF aligned + BOS/CHoCH confirm where relevant + GEX confluence + volume). Drop the hand-assigned 0.60–0.80 confidences entirely. `ta_pattern_confidence_threshold` becomes unused for firing.
4. **TA strength for ranking = objective count of confirmations that stacked** (weekly MTF aligned + BOS/CHoCH present + GEX confluence + strong volume), normalized 0–1. Not a guessed number, not calibration. (A flat binary 1.0 breaks `conviction_score`, which averages firing-factor strength — so use the count.)
5. **GEX confluence**: scanner computes GEX before TA and passes call-wall/put-wall/gamma-flip into `detect_pattern`. Long breakout through call-wall = +confluence; breakdown through put-wall = +confluence; reversal at flip = +confluence; pullback holding above flip = +confluence.

## Approved per-pattern upgrades (apply inside detect_pattern)

| Pattern | Upgrade |
|---------|---------|
| breakout / breakdown | require real **BOS** (swing-based, not rolling 20d max) + multi-day hold + vol_p85 + weekly aligned + GEX wall confluence |
| ema_reclaim / ema_rejection | require **CHoCH/BOS** confirm + close margin (>0.5%) + weekly aligned (kill whipsaw) |
| oversold_bounce | require **bull divergence + CHoCH** + level reclaim, not one green bar |
| bullish_reversal / overbought_reversal / bearish_reversal | require divergence + CHoCH (not RSI alone); GEX flip confluence |
| base_breakout / base_breakdown | require an actual trigger-break bar + vol expansion |
| compression_break(_down) | require weekly aligned + BOS + vol_p85 |
| pullback_in_trend | keep (cleanest); Fib + prior-swing confluence. **Do NOT add dormant/flow — those are options factors, not TA.** |
| failed_breakout / failed_breakdown | keep (already structural); add weekly + retest-rejection |

Cross-cutting: apply the 5-state weekly classifier uniformly (CLAUDE.md MTF matrix decides which categories are eligible per weekly state). Use BOS for continuation, CHoCH for reversal.

## Files in scope
- `src/eigenview/factors/technical.py` — `detect_pattern` upgrades + `score_technical` adapter rewrite.
- `src/eigenview/synthesis/scanner.py` — compute GEX before TA; pass GEX levels into the TA call.
- `src/eigenview/api/routes/ta_scan.py` — verify it still works through the adapter.
- `src/eigenview/synthesis/gate.py` — `SHORT_SETUP_PATTERNS` already extended; re-verify it covers every short in `detect_pattern`'s taxonomy.
- Tests: the old `score_technical` tests (`test_technical_real.py`, `test_technical_fixtures.py`, `test_technical_pullback.py`) assert the dead 15-pattern engine — **expect to rewrite them** against `detect_pattern`. `test_technical_phase6*` already target `detect_pattern`.

## Other checks / follow-ups (after Phase A)
- **Remove vestigial Stage 4**: once every liquid ticker has history, the static `score_bet_v2` firing path (`score_dormant`) is dead weight — delete it and simplify `score_dormant_from_history`.
- **Flow + GEX liquidity gating**: only dormant is gated on liquidity now. Flow and GEX also read `chains` — decide whether illiquid tickers should skip those too.
- **contract_history freshness**: the download was a one-off (data to 2026-05-22). Wire a recurring liquid-history refresh (extend `_refresh_watchlist_history` to the liquid set, filtered pull) or a scheduled job — otherwise activation goes stale.
- **Re-run `daily-scan`** end-to-end after Phase A to rewrite `factor_scores` with the new TA + dormant code and validate pick output.
- **forward_returns** still empty — only needed if calibration is ever revived (currently dropped).
- Diagnostic scripts left uncommitted: `scripts/{watch_download,scope_liquid_history_pull,scan_ta_dormant_activation}.py` — keep or delete.

---

## PASTE-READY PROMPT FOR NEW SESSION

> Read `docs/PHASE-A-HANDOFF.md`, `docs/dormant-flow.md`, and `CLAUDE.md`. We're on branch `feature/scanner-factor-scores-write` at commit fc702c4.
>
> Implement Phase A: swap the live TA engine from the naive 15-pattern `score_technical` body to `detect_pattern` (27 setups, MTF + BOS/CHoCH). Make `score_technical` a thin adapter over `detect_pattern` returning `FactorResult` (keep the name; both `scanner.py` and `api/routes/ta_scan.py` call it unchanged). 
>
> Firing rules: a pattern fires iff its structural hard gates pass — weekly 5-state MTF aligned + BOS/CHoCH confirm where relevant + GEX confluence + volume. **No confidence number, no 0.70 floor, no calibration.** TA `strength` = normalized count of confirmations that stacked (for ranking only). Apply the per-pattern upgrades and GEX-confluence rules in the handoff table. Pass GEX call-wall/put-wall/flip into `detect_pattern` (compute GEX before TA in the scanner). Do NOT add dormant/flow into TA.
>
> Use TDD. The old `score_technical` tests assert the dead engine — rewrite them against the new engine. Run the full suite green before committing. Then re-run `daily-scan` to validate and report the new TA firing count (target: far below the old 342/504).
>
> Propose the implementation plan first; wait for approval before editing.
