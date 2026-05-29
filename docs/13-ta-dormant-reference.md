# TA + Dormant — Implementation Reference (post Phase A)

Last updated: 2026-05-28 · branch `feature/ta-engine-swap` · commits `27c5f76`, `cd6e63d`

This doc reflects the **live code** after Phase A: TA engine swap, 7 setups
ported, per-pattern tightening, SMC import bug fixed.

---

## 1. Scanner pipeline — A → Z

`run_daily_scan(tickers, session)` in `src/eigenview/synthesis/scanner.py`.

```
A. score_macro_regime(session)                         → Gate 0 (macro)
B. _refresh_watchlist_history(session)                 → Databento contract pull (STALL — see §6)
C. for each ticker (bounded by scanner_concurrency):
   C1. df = await _fetch_live(ticker)                  → DB prices (Price table, 2yr daily)
   C2. read latest Chain snapshot for ticker           → options chain rows
   C3. gex = score_gex(chains, spot, ticker)           → call_wall, put_wall, gamma_flip
   C4. gex_levels = {call_wall, put_wall, gamma_flip}
   C5. ta = _score_with_lookback(df, ticker, gex_levels=gex_levels)
         loops i=0..lookback (default 3 days), calls score_technical, returns
         first firing result or last call's result
   C6. flow = score_flow(chains, ticker)
   C7. ticker_oi = Σ contract.oi
       if ticker_oi >= settings.dormant_min_ticker_oi (5,000):
           _identify_dormant_bets(...)
           dormant = score_dormant_from_history(...)
       else:
           dormant = NOT_LIQUID (no score, no fire)
   C8. sentiment = score_sentiment(ticker)
   C9. scorecard = TickerScorecard(macro, ta, gex, flow, dormant, sentiment, spot)
D. qualified = rank_picks(scorecards, macro_score)
E. write_picks(qualified, ...)
F. for each scorecard: upsert FactorScore(date, ticker, …)  → heat-map source
```

Gate logic for `qualified` (in `synthesis/gate.py`):

- Macro must not be `NO DATA` (regime unverifiable → block all picks, long & short).
- Hard gates: TA fires AND GEX fires.
- Soft gates: at least 2 of {flow, dormant, sentiment} fire.
- `pick.direction = "short"` iff `ta.label ∈ SHORT_SETUP_PATTERNS` (12 shorts).
- Macro `RED` → only shorts pass (long picks blocked).

---

## 2. TA engine — `detect_pattern` + `score_technical` adapter

### 2.1 Adapter (`score_technical(df, ticker, gex_levels=None)`)

Thin adapter over `detect_pattern`. Replaces the old naive 15-pattern body.

```
1. len(df) < 30  → FactorResult.no_data("technical", "insufficient price history")
2. weekly = _build_weekly(daily)  # W-FRI resample (open=first, high=max, low=min, close=last, vol=sum)
3. res = detect_pattern(daily, weekly, as_of=daily.index[-1])
4. pattern = res["pattern"]; firing = pattern not in {"no_pattern","no_data","NO DATA",""}
5. compute objective confirmation count (1..4):
      base       = 1   (the structural setup itself)
      + weekly   = 1 if weekly_state ∈ {BULLISH, BULLISH_EXTENDED, BEARISH_STRONG}
      + structure= 1 if pattern ∈ {bos_*, choch_*, breakout, breakdown,
                                   base_breakout, base_breakdown,
                                   failed_breakout, failed_breakdown,
                                   compression_break, compression_break_down}
                       or detail has bos_*/choch_* True flag
      + gex_conf = 1 if _gex_confluence(pattern, close, gex_levels) True
      + strong_v = 1 if detail.vol_ratio >= 1.3
      confirmations = min(4, sum)
6. strength = confirmations / 4.0  (firing→ always > 0)
7. return FactorResult(factor_id="technical", firing, strength, label=pattern, detail, narrative)
```

**Firing model:** structural — `detect_pattern`'s hard gates ARE the firing
decision. No confidence floor. `ta_pattern_confidence_threshold` no longer used.

**GEX confluence (strength-only — never blocks):**

```
_gex_confluence(pattern, close, levels):
    short_pattern:
        close <= gamma_flip                → True
        close <= put_wall * 1.02           → True
    long_pattern:
        close >= gamma_flip                → True
        close >= call_wall * 0.98          → True
    else: False
```

### 2.2 Weekly 5-state classifier — `_classify_weekly_state(weekly_df, as_of)`

States: `BULLISH | BULLISH_EXTENDED | NEUTRAL | BEARISH_WEAK | BEARISH_STRONG`

Driven by weekly EMA8/21 stack, weekly ADX, weekly RSI computed on
W-FRI-resampled bars.

### 2.3 SMC BOS / CHoCH

Library: `smartmoneyconcepts`. Hoisted to module top with `redirect_stdout` to
silence the library's Unicode banner (prior in-function import silently failed
on Windows cp1252 → `BOS/CHoCH = False` in every scan ever).

```
_smc.swing_highs_lows(ddf, swing_length=10)            → swing-point table
_smc.bos_choch(ddf, shl, close_break=True)             → DataFrame with BOS, CHOCH, BrokenIndex
recency filter: signal bar index OR BrokenIndex in last 60 bars
outputs: _bos_bullish_signal, _bos_bearish_signal,
         _choch_bullish_signal, _choch_bearish_signal
```

Hoisted above all pattern checks so the structural break signal is available
to `breakout`/`ema_reclaim`/`compression_break` tightening, not just the
dedicated `bos_*`/`choch_*` setups.

### 2.4 Adaptive thresholds

All key levels are 63-bar (3-month) rolling percentiles per ticker — never
fixed numbers. Examples:

| Var | What |
|---|---|
| `rsi_p15/20/25/40/55/65/80/85/90` | RSI percentiles |
| `adx_p25/30/40/70` | ADX percentiles |
| `vol_p35/40/55/65/70/72/85` | vol/avg ratio percentiles |
| `atr_p15/20` | ATR ratio percentiles |

Fallback to static estimates when < 60 bars.

### 2.5 Setup catalog — current (post-consolidation) gates

**TAXONOMY = 24 setups** (10 longs / 10 shorts / 2 mean-reversion each direction).
`bos_bullish`, `bos_bearish`, `choch_bullish`, `choch_bearish` eliminated as standalones —
BOS/CHoCH signals now gate the setups they structurally confirm.

| Pattern | Dir | BOS/CHoCH | HTF dir | Scan conditions |
|---|---|---|---|---|
| `pullback_deep` | long | — | BULLISH/EXTENDED | daily bullish · `rsi_p25 ≤ rsi ≤ rsi_p50` · close in EMA50 [-5%,+1%] · vol < vol_p60 · ADX ≥ adx_p30 |
| `pullback_in_trend` | long | — | BULLISH/EXTENDED | daily bullish · `rsi_p15 ≤ rsi ≤ rsi_p40` · close near EMA21 (±4%) · vol < vol_p72 |
| `pullback_to_structure` | long | — | BULLISH/EXTENDED | daily bullish · `rsi_p30 ≤ rsi ≤ rsi_p55` · vol < vol_p60 · close within 2% of prior 60-bar swing high |
| `flag_continuation` | long | BOS ✓ | ≠ BEARISH_STRONG | `rsi_p45 ≤ rsi ≤ rsi_p65` · vol < vol_p50 · squeeze ON · impulse > 5% last 10 bars |
| `bull_flag` | long | BOS ✓ | BULLISH | `45 ≤ rsi ≤ 65` · vol < 1.2× · squeeze ON · impulse > 5% |
| `compression_break` | long | BOS ✓ | BULLISH/EXTENDED | squeeze released · close > BBU · vol > vol_p85 · up candle · rsi < 90 |
| `breakout` | long | BOS ✓ | BULLISH/EXTENDED | swing high in last 60 · prior_approaches ≥ 1 · multi-day hold · vol > vol_p85 |
| `base_breakout` | long | BOS ✓ | BULLISH/EXTENDED | tight base (std_p25) · squeeze ON · close ≥ high_50d × 1.001 · vol > vol_p55 |
| `ema_reclaim` | long | BOS or CHoCH ✓ | BULLISH/EXTENDED | prev close < EMA50 · close > EMA50 × 1.005 · vol > vol_p55 |
| `bullish_reversal` | long | CHoCH ✓ | BEARISH_WEAK | EMA21 < EMA50 · ADX > adx_p25 · bull_div (or 10-bar fallback) · vol > vol_p75 · ADX ≥ adx_p30 · prev_close < close · rsi < rsi_p55 · weekly RSI < 35 |
| `oversold_bounce` | long | CHoCH ✓ | ≠ BEARISH_STRONG | rsi < rsi_p20 · up day · close > EMA200 · weekly ADX ≤ 30 · vol > vol_p60 · bull_div · close > EMA21 |
| `failed_breakdown` | long | CHoCH ✓ | ≠ BEARISH_STRONG | ≥ 6 bars · close ≤ recent_high · close > EMA21_ewm · open ≤ EMA21_ewm × 1.01 · ≥ 2/4 prior closes < EMA21_ewm · vol > vol_p65 |
| `bb_mean_reversion_long` | long | — | ≠ BULLISH_EXTENDED/BEARISH_STRONG | close ≤ BBL × 1.005 · ADX < adx_p35 (floor 20) · rsi < rsi_p30 |
| `ema200_snap_long` | long | — | N/A | close > 15% below EMA200 · ADX > p40 (cap 50) · weekly RSI < 35 · up day |
| `compression_break_down` | short | BOS ✓ | BEARISH_WEAK/STRONG | squeeze released · close < BBL · vol > vol_p85 · down candle |
| `breakdown` | short | BOS ✓ | BEARISH_WEAK/STRONG | swing low in last 60 · multi-day hold · vol > vol_p85 |
| `base_breakdown` | short | BOS ✓ | BEARISH_WEAK/STRONG | tight base (std_p25) · squeeze ON · close ≤ low_50d × 0.999 · vol > vol_p55 |
| `ema_rejection` | short | BOS or CHoCH ✓ | BEARISH_*/NEUTRAL | prev close > EMA50 · close < EMA50 × 0.995 · vol > vol_p55 |
| `overbought_reversal` | short | CHoCH ✓ | BULLISH/EXTENDED | daily bullish · ADX > adx_p40 · rsi > rsi_p80 · down day · close < open · vol > vol_p65 · weekly RSI > 65 |
| `bearish_reversal` | short | CHoCH ✓ | BULLISH/EXTENDED | daily bullish · ADX > adx_p70 · bear_div · vol > vol_p75 · rsi > rsi_p85 · weekly RSI > 65 |
| `failed_breakout` | short | CHoCH ✓ | BEARISH_STRONG/WEAK/NEUTRAL | ≥ 64 bars · prior swing high < pos 56 · exceeded last 4 bars · close < swing high · close < open · vol < vol_p55 |
| `rally_in_downtrend` | short | — | BEARISH_* | `rsi_p43 ≤ rsi ≤ rsi_p62` · EMA21 < EMA50 · close in EMA21 × [0.98, 1.0] · vol < vol_p55 |
| `bb_mean_reversion_short` | short | — | ≠ BULLISH_EXTENDED/BEARISH_STRONG | close ≥ BBU × 0.995 · ADX < adx_p35 · rsi > rsi_p70 |
| `ema200_snap_short` | short | — | N/A | close > 15% above EMA200 · weekly RSI > 70 · down day |

### 2.6 Check order in `detect_pattern`

Top of function down: `pullback_deep → pullback_in_trend → pullback_to_structure
→ flag_continuation → bull_flag → compression_break → compression_break_down →
breakout → breakdown → base_breakout → base_breakdown → ema_reclaim →
ema_rejection → bb_mean_reversion_long → bb_mean_reversion_short →
ema200_snap_long → ema200_snap_short → bullish_reversal → overbought_reversal →
bearish_reversal → oversold_bounce → failed_breakdown → failed_breakout →
rally_in_downtrend → no_pattern`.

First match wins.

### 2.7 Setup → SHORT classification (gate.py)

`SHORT_SETUP_PATTERNS = {bearish_reversal, breakdown, rally_in_downtrend,
compression_break_down, ema_rejection, base_breakdown, overbought_reversal,
failed_breakout, bb_mean_reversion_short, ema200_snap_short}` — 10 shorts.
Everything else (14) is long.

---

## 3. Current firing — sp500 DB scan (2026-05-28)

`scripts/ta_firing_count.py` over 491 sp500 tickers with DB prices (no
Databento refresh, no dormant overhead). Total fired = 376 (longs 157, shorts 219):

```
bos_bearish              118
bos_bullish              93
choch_bearish            67
pullback_in_trend        16
bb_mean_reversion_short  13
rally_in_downtrend       12
choch_bullish            10
bb_mean_reversion_long   10
failed_breakdown         10
bull_flag                7
failed_breakout          6
pullback_to_structure    5
pullback_deep            3
ema_rejection            2
ema_reclaim              1
overbought_reversal      1
compression_break        1
flag_continuation        1
breakout                 0
breakdown                0
base_breakout            0
base_breakdown           0
compression_break_down   0
oversold_bounce          0
bullish_reversal         0
bearish_reversal         0
ema200_snap_long         0
ema200_snap_short        0
```

74% of fires are bos_*/choch_* structural breaks now that SMC actually works.

---

## 4. Open tightening (proposed, NOT applied)

`bos_*` / `choch_*` are loose: SMC signal + weekly state, no volume or
direction confirmation. Proposed to bring total well below 342:

- `bos_bullish`: add `vol_ratio > vol_p72_dp` AND `close > open` (break candle).
- `bos_bearish`: add `vol_ratio > vol_p72_dp` AND `close < open`.
- `choch_bullish`: add bull_div AND `vol_ratio > vol_p65_dp`.
- `choch_bearish`: add bear_div AND `vol_ratio > vol_p65_dp`.

Estimated reduction: bos pair 211 → ~80–100, choch pair 77 → ~25–40. Total
~250/491 (~51%).

---

## 5. Dormant pipeline

See `docs/dormant-flow.md` (current). One-line summary:

`Liquidity (agg OI ≥ 5,000) → candidate filter (long-dated, big, not deep ITM,
OI ≥ 500) → activation engine (OI jump / vol surge / IV jump / underlying move,
fires when ≥ 2 triggers and strength ≥ 0.5)`.

Static rubric (`score_bet_v2`) is vestigial — ranking only, no longer fires.

---

## 6. Scan stall — Databento refresh (KNOWN)

`_refresh_watchlist_history` (scanner.py:122) ships **all 12,278 dormant-bet
OSI symbols in a single streaming HTTP request** to Databento. Read times out
after ~2h. Failure is caught by `try/except` at line 168 (graceful), but the
scan still hangs the full timeout duration first.

Fix (proposed, not applied): chunk OSI list (default 200) + per-chunk
`asyncio.wait_for` timeout (default 90s) + tolerate per-chunk failures. Two
new settings `databento_refresh_chunk_size` / `databento_chunk_timeout_s`.
Math: 12,278/200 = 62 chunks; worst case 93 min, realistic ~30 min.
