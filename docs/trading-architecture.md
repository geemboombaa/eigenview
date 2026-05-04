# EigenView Trading Architecture
**Version:** 0.2 (living document — update after every spec decision)
**Last updated:** 2026-05-04

---

## What this system is

A daily pre-market scan that produces 3–10 **high-conviction, actionable swing trade setups** — each with a named pattern, entry zone, stop loss, target, and plain-English thesis. Not a screener. Not a data dump. A curated, ranked list ready to act on within 60 seconds of opening the dashboard.

**Scope:** Swing trades. Hold time 2–10 days. Large-cap optionable equities (S&P 500 + NDX 100). Long and short.

---

## What is novel about this system

Everything below already exists as a concept in the trading literature. What does NOT exist in any public open-source system:

1. **Per-stock GEX as a hard gate on TA signals.** Academic research (Barbon & Buraschi, 2024 0DTE papers) documents that dealer gamma positioning affects realized returns. SpotGamma sells this commercially. No open-source system uses per-stock computed GEX as a binary gate on individual equity TA setups.

2. **Macro regime score gating all picks.** VIX term structure + DIX + breadth as a pre-filter that blocks longs in bad regimes. SpotGamma covers index-level — nobody does this as a systematic open-source pipeline for individual stock picks.

3. **Dormant-bet radar.** Detecting large, aged options positions activating near catalysts is EigenView's moat. No public system does this.

4. **Full convergence requirement.** Gate 0 (macro) + Gate 1 (TA) + Gate 2 (GEX) + ≥2 of {Flow, Dormant, Sentiment} must all align. Individual factors are well-known. Requiring convergence of non-correlated signal sources is the differentiator.

5. **Named classification + MTF gating as the TA layer.** No library outputs named swing setups. Every serious system hand-codes this. What is novel here: a rules-based classifier that maps indicator state → human-readable named setup (the language traders actually use) + confidence score + 5-state weekly MTF gate that blocks setups contradicted by higher-timeframe context. This is the foundation the downstream GEX/flow gates depend on. Without a quality TA signal entering the pipeline, conviction scoring is meaningless.

The TA layer uses standard math — indicators, pattern conditions, thresholds. The novelty is the assembled, tested, MTF-gated, named-output pipeline wired to GEX + macro + flow + dormant. That combination does not exist publicly.

---

## Signal stack (full pipeline)

```
Gate 0 — Macro Regime (daily, pre-scan)
    → SPX GEX regime + VIX term structure + DIX + breadth
    → Score 0–10. GREEN ≥7, YELLOW 4–6, RED ≤3
    → RED: no long picks. SHORT setups only.

Gate 1 — Technical Analysis (per stock, daily)
    → Multi-timeframe: weekly context → daily setup → named pattern
    → Pattern confidence > 0.6 required
    → Weekly trend must not contradict (see MTF matrix below)

Gate 2 — Per-Stock GEX (per stock, daily)
    → Net dealer gamma, gamma flip, call wall, put wall
    → Must fire for setup to qualify

Factor 1 — Options Flow
    → V/OI ≥ 3 (new position), premium > $500K, aggressive side
    → Dark pool cluster within ±0.5% of entry zone

Factor 2 — Dormant-Bet Radar
    → Large old position (30–180 days, ≥$500K, ≥90 DTE) activating near catalyst

Factor 3 — Catalyst + Sentiment
    → Earnings within 30 days, macro events, novelty Z-score, FinBERT direction

Qualify = Gate 0 passes AND Gate 1 fires AND Gate 2 fires
          AND ≥2 of {Flow, Dormant, Sentiment} fire
Conviction = 1–5 based on factor count × strength
Rank = conviction DESC, dormant bonus, IV rank ASC (cheaper vol = better R:R)
Output = top 3–10 picks
```

---

## Strategy categories

Every swing setup belongs to one of four categories. The category determines which weekly context is required, which stop rules apply, and which exits are valid.

### 1. TREND CONTINUATION
**Thesis:** Established trend. Price pulls back to support. Resumes.
**Weekly required:** Bullish (EMA8 > EMA21, RSI 45–65, ADX > 15)
**Short version:** Weekly bearish required for short side.
**Noise filter:** Volume must decline on pullback. If volume spikes on pullback, it may be distribution — skip.

### 2. BREAKOUT
**Thesis:** Price compressed, energy building. Expansion follows with volume.
**Weekly required:** Not bearish (neutral to bullish). Weekly bearish = no long breakout.
**Short version:** Short breakout valid in any regime if weekly not bullish.
**Noise filter:** Volume must confirm expansion. Breakout on declining volume is a fade, not an entry.

### 3. REVERSAL
**Thesis:** Trend extended to exhaustion. First structural break in opposite direction.
**Weekly required:** Extended (RSI > 65 for bearish reversal, RSI < 35 for bullish reversal). The weekly must be stretched — reversals in non-extended markets are noise.
**Noise filter:** Requires divergence (RSI divergence) OR structural break (CHoCH). Not just overbought RSI alone.

### 4. MEAN REVERSION
**Thesis:** Price deviated significantly from equilibrium. Statistical pull back to mean.
**Weekly required:** Non-trending (ADX < 20, flat EMAs). Trending markets don't revert — they continue.
**Noise filter:** Not valid if strong trend (ADX > 25). EMA200 deviation reversion requires price to be at an extreme (>15% away from EMA200).

---

## Multi-timeframe matrix

Weekly context gates which categories are valid for that stock that day.

| Weekly state | Condition | Valid long setups | Valid short setups |
|---|---|---|---|
| **Bullish** | EMA8>21, RSI 45–65, ADX >15 | Trend Continuation, Breakout | None (no shorts in bull) |
| **Bullish extended** | RSI >70 OR ADX >35 | Bearish Reversal only | Bearish Reversal |
| **Neutral / sideways** | ADX <20, EMAs flat | Breakout (compression), Mean Reversion | Breakdown, Mean Reversion |
| **Bearish weak** | EMA8<21 recently, RSI 40–55 | Mean Reversion, Failed Breakdown | Trend Continuation (short), Breakdown |
| **Bearish strong** | EMA8<21, RSI <45, ADX >20 | Bullish Reversal only | Trend Continuation (short), Breakdown |
| **Bearish extended** | RSI <30 OR ADX >35 | Bullish Reversal only | None (no new shorts at extreme) |

---

## Setup sub-types (full list)

### TREND CONTINUATION setups

| Setup name | Category | Detection | Libraries |
|---|---|---|---|
| `pullback_in_trend` | Trend Continuation | Daily bullish EMA stack, RSI 38–57, price > EMA21×0.99 and < EMA50×1.08, volume declining on pullback | pandas_ta (EMA, RSI, ADX) |
| `pullback_deep` | Trend Continuation | Daily bullish, RSI 32–50, price touches EMA50, volume declining | pandas_ta |
| `pullback_to_structure` | Trend Continuation | Price tests prior swing high (now support) or prior breakout level | swingtrend (SPH→support level) |
| `flag_continuation` | Trend Continuation | Impulse move followed by 5–10 bar tight range, BB contracting, volume declining | pandas_ta squeeze_pro ON |
| `rally_in_downtrend` | Trend Continuation (short) | Weekly bearish, RSI bounce to 43–62, price near EMA21 from below | pandas_ta |

### BREAKOUT setups

| Setup name | Category | Detection | Libraries |
|---|---|---|---|
| `breakout` | Breakout | Price closes above N-bar swing high with volume >1.5× avg | swingtrend SPH level, pandas_ta |
| `breakdown` | Breakout (short) | Price closes below N-bar swing low with volume >1.5× avg | swingtrend SPL level, pandas_ta |
| `compression_break` | Breakout | squeeze_pro ON→OFF, momentum positive, volume surge | pandas_ta squeeze_pro |
| `compression_break_down` | Breakout (short) | squeeze_pro ON→OFF, momentum negative | pandas_ta squeeze_pro |
| `base_breakout` | Breakout | 20+ bar low-volume contraction, price within 3% of 50-day high | PKScreener validateConsolidation() logic |
| `base_breakdown` | Breakout (short) | Same inverted | Same |
| `ema_reclaim` | Breakout | Was below EMA50, closes above it with volume >1.1× | pandas_ta |
| `ema_rejection` | Breakout (short) | Was above EMA50, closes below it | pandas_ta |
| `bos_bullish` | Breakout | Break of Structure: closes above last swing high in structure | smartmoneyconcepts bos_choch() |
| `bos_bearish` | Breakout (short) | Break of Structure: closes below last swing low | smartmoneyconcepts bos_choch() |

### REVERSAL setups

| Setup name | Category | Detection | Libraries |
|---|---|---|---|
| `bullish_reversal` | Reversal | RSI bullish divergence + volume spike + weekly RSI <35 | pandas_ta (RSI divergence: custom) |
| `bearish_reversal` | Reversal | RSI bearish divergence + volume spike + weekly RSI >65 | pandas_ta |
| `overbought_reversal` | Reversal | Daily trend bullish, RSI >68, volume down day, weekly RSI >65 required | pandas_ta |
| `oversold_bounce` | Reversal | RSI <32, reversal candle, above EMA200 | pandas_ta |
| `failed_breakdown` | Reversal | Dipped below EMA21, recovered above it with volume >1.5× | pandas_ta |
| `failed_breakout` | Reversal (short) | Exceeded N-bar high, reversed below with volume | swingtrend + pandas_ta |
| `choch_bullish` | Reversal | Change of Character: first close above prior swing high in downtrend | smartmoneyconcepts bos_choch() |
| `choch_bearish` | Reversal (short) | Change of Character: first close below prior swing low in uptrend | smartmoneyconcepts bos_choch() |

### MEAN REVERSION setups

| Setup name | Category | Detection | Libraries |
|---|---|---|---|
| `bb_mean_reversion_long` | Mean Reversion | Price at lower BB, ADX <20, weekly ADX <20 | pandas_ta (BB, ADX) |
| `bb_mean_reversion_short` | Mean Reversion (short) | Price at upper BB, ADX <20 | pandas_ta |
| `ema200_snap_long` | Mean Reversion | Price >15% below EMA200, weekly RSI <35 | pandas_ta |
| `ema200_snap_short` | Mean Reversion (short) | Price >15% above EMA200, weekly RSI >70 | pandas_ta |

**Total: 21 setups (vs current 15). Additions: pullback_deep, pullback_to_structure, flag_continuation, bos_bullish, bos_bearish, choch_bullish, choch_bearish, bb_mean_reversion long/short, ema200_snap long/short. Removed: nothing.**

---

## Stop loss rules

Stop loss is set at trade entry and stored in the picks table. Never moved to a worse price.

### Initial stop placement by category

| Category | Long stop | Short stop | Rule |
|---|---|---|---|
| Trend Continuation | Below the pullback swing low (last SPL before entry) | Above the rally swing high | Logical: if price takes out the pullback low, the trade thesis is wrong |
| Breakout | Below the breakout level (prior resistance = new support) | Above the breakdown level | Logical: if price falls back below breakout point, it was a false break |
| Reversal | Below the reversal low for longs (the wick of the reversal candle) | Above the reversal high | Logical: if the reversal candle's extreme is taken out, reversal failed |
| Mean Reversion | Below entry - 1.5×ATR14 | Above entry + 1.5×ATR14 | Statistical: mean reversion trades are mean reversion until they're not |

### ATR sizing
Initial stop distance = max(logical stop distance, 1.0×ATR14). Prevents stops that are too tight in volatile conditions.

For shorts: use 1.25×ATR14 minimum (volatility asymmetry — stocks fall faster, require wider stops).

### Implementation
```python
# In gate.py / synthesis
atr = technical_detail['atr']  # ATR14 from scan
swing_low = technical_detail['swing_low']  # from swingtrend

stop_long = max(swing_low * 0.995, entry_low - atr)
stop_short = min(swing_high * 1.005, entry_high + atr * 1.25)
```

---

## Trailing stop rules

Trailing stops are NOT computed at scan time. They are:
1. Shown as a reference level on the chart, updated as new bars form
2. Stored in `signal_triggers` table per scan (the initial stop)
3. The user manages the trail — EigenView shows the trail levels, not an execution engine

### Trail methods (shown on chart as toggleable overlays)

| Method | Formula | Best for | Library |
|---|---|---|---|
| **SuperTrend trail** | `ta.supertrend(length=7, multiplier=3.0)` → `SUPERTl` for longs | Trending moves | pandas_ta (confirmed in package) |
| **Chandelier exit** | `highest_high(22) - 3 × ATR(22)` | Trending moves, tighter | NJiHin/TA_Chandelier (port from Pine) |
| **EMA trail** | Trail stop under EMA21 | Trend continuation trades | pandas_ta |
| **EMA50 trail** | Trail stop under EMA50 | Longer swing holds | pandas_ta |

For shorts: mirror above (lowest low + multiplier instead of highest high - multiplier).

### Trail activation rule
Trail activates only after price moves in favor by ≥1 ATR. Before that, use initial stop. This prevents premature exit from normal volatility after entry.

---

## Exit rules

Every setup has three types of exits. ALL three are computed at scan time and stored.

### 1. Target (measured move)

| Setup category | Target method | Formula |
|---|---|---|
| Trend Continuation | Prior swing high (for longs) | `swing_high` from swingtrend |
| Breakout | Measured move | `breakout_level + (breakout_level - base_low)` |
| Reversal | 50% or 61.8% Fibonacci retracement of prior move | `fib_levels['f500']` or `fib_levels['f618']` from existing code |
| Mean Reversion | EMA20 or BB midline | Computed from pandas_ta |

Minimum R:R required: target / (entry - stop) ≥ 2.0. Setups with R:R < 2 are downgraded in conviction.

### 2. Signal-based exit (invalidation)
The trade is wrong if the opposite pattern fires for the same ticker. Stored as an invalidation condition per pick.

| Setup | Invalidation signal |
|---|---|
| Any long setup | Bearish reversal or BOS bearish or breakdown fires |
| Any short setup | Bullish reversal or BOS bullish or breakout fires |
| Trend Continuation long | Weekly trend flips to bearish |
| Mean Reversion long | Price continues away from mean (ADX spikes above 25) |

### 3. Time stop
If price has not moved toward target by ≥0.5 R within 5 trading days, close. Setup stalled = capital deployment cost.

Not implemented in EigenView v1 (no execution engine). Displayed as a "valid until" date on the card.

---

## Signal persistence

### What gets stored
Every daily scan writes to `signal_triggers`:
```sql
CREATE TABLE signal_triggers (
    id         INTEGER PRIMARY KEY,
    ticker     TEXT NOT NULL,
    scan_date  TEXT NOT NULL,          -- YYYY-MM-DD
    setup_type TEXT NOT NULL,
    direction  TEXT NOT NULL,          -- 'long' | 'short'
    entry_low  REAL,
    entry_high REAL,
    stop       REAL,
    target     REAL,                   -- NEW: computed at scan time
    rr_ratio   REAL,                   -- target / (entry - stop)
    confidence REAL,
    fired_at   TEXT,                   -- ISO datetime of the bar that fired
    valid_until TEXT                   -- scan_date + 5 trading days
);
```

### What shows on chart
- Arrow marker at the candle where the signal fired (`fired_at`)
- Green arrow up = long, red arrow down = short
- Clicking marker shows setup details in a tooltip
- Historical markers visible across all prior scans

### Card display
- Setup name (already showing)
- `Fired: 2h ago` or `Fired: May-03` (from `fired_at`)
- `Valid until: May-10` (from `valid_until`)
- R:R ratio displayed next to entry/stop

---

## Chart controls (toggles)

Persistent in localStorage per ticker.

| Toggle | Series affected | Default |
|---|---|---|
| EMA 21 | `ema21LineSeries` | ON |
| EMA 50 | `ema50LineSeries` | ON |
| EMA 200 | `ema200LineSeries` | ON |
| BB | Upper + lower BB series | OFF |
| Signals | Historical `signal_triggers` markers | ON |
| SuperTrend | `supertrendSeries` | OFF |

---

## Long/short symmetry notes

The system handles long and short symmetry by inverting conditions. Real-world asymmetries to be aware of (not modeled in v1):

1. **SEC Alternative Uptick Rule (SSR):** Triggers when a stock drops 10%+ intraday. Short entries on breakdown days may hit SSR — execution at bid only. Affects high-volatility names on the exact day you want to short them.

2. **ATR asymmetry:** Stocks fall faster than they rise. Short-side ATR stops use 1.25× multiplier vs 1.0× for longs.

3. **Options-based positions (EigenView's actual output):** For options picks, long/short is handled by call vs put selection. Bear put spreads / long puts serve as the short vehicle — no borrow cost, no SSR. This is the recommended approach for all short setups in EigenView.

---

## Build libraries (confirmed, not invented)

| Need | Library | Status |
|---|---|---|
| All indicators (EMA, RSI, ADX, ATR, BB, MACD) | `pandas_ta` | In deps |
| Compression state | `pandas_ta.squeeze_pro()` | In deps — replace hand-coded ATR squeeze |
| Swing levels (SPH/SPL) | `scipy.signal.argrelextrema` | Add to deps |
| BOS / CHoCH / FVG | `smartmoneyconcepts` PyPI | Add to deps |
| SuperTrend trailing stop | `pandas_ta.supertrend()` | In deps |
| Parabolic SAR | `pandas_ta.psar()` | In deps |
| Chandelier exit | NJiHin/TA_Chandelier (port) | Port ~30 lines |
| RSI divergence | Custom (no library) | Keep existing |

---

## What is being rebuilt vs kept

| Component | Action | Reason |
|---|---|---|
| Indicator computation (EMAs, RSI, ADX, ATR, BB) | Keep | Correct, uses pandas_ta |
| ATR squeeze detection (hand-coded) | Replace with `squeeze_pro()` | Tested, more robust, handles 3 compression widths |
| Swing high/low detection (hand-coded) | Replace with `swingtrend` | Maintained library, cleaner |
| Pattern classifier function | Keep structure, refactor internals | Architecture correct; internals use new building blocks |
| BOS / CHoCH | Add new | Missing from current code, high-value reversal/breakout signals |
| Flag/pennant | Add new | Missing, uses squeeze_pro |
| Pullback to EMA50 / structure | Add new | Missing sub-types |
| BB mean reversion | Add new | Missing category |
| All thresholds (50 literals) | Replace with rolling percentiles (see AI/ML section) | Adaptive, no hardcoding, proven improvement |
| Weekly context classifier | Strengthen from 2 states to 5 | Current weak check causes wrong pattern firing |
| Stop loss computation | Add to synthesis | Currently missing — only entry/stop stored, no R:R or target |
| Target (measured move) | Add to synthesis | Currently not computed |
| signal_triggers DB table | Add | Missing entirely |
| Chart markers | Add (TradingView createSeriesMarkers) | Missing entirely |
| Chart toggles | Add | Missing entirely |
| Card fired_at display | Add | Field exists in API, never shown |

---

## AI/ML assessment for TA layer

Research-grounded. Every recommendation below is backed by published evidence, not speculation.

### What to do now (no training data required)

**Replace hardcoded thresholds with rolling percentiles.**

Current code has 50+ literal numbers (RSI < 32, vol > 1.5×, ATR ratio < 0.7). These were calibrated on population averages. They misfire on high-vol tickers (fires too often) and low-vol tickers (never fires).

Replace with ticker-specific rolling percentiles over 90 days:

```python
# In technical.py — replaces ALL hardcoded indicator thresholds
rsi_oversold   = np.percentile(rsi_90d,   20)   # was: 32
rsi_overbought = np.percentile(rsi_90d,   80)   # was: 68-72
adx_trending   = np.percentile(adx_90d,   65)   # was: 20-25
vol_surge      = np.percentile(vol_90d,   70)   # was: 1.5× avg
vol_light      = np.percentile(vol_90d,   35)   # was: 0.8× avg
atr_contracted = np.percentile(atr_90d,   30)   # was: 0.65-0.7× avg
```

**Evidence:** Clenow ("Following the Trend", 2013) and Carver ("Systematic Trading", 2015) both quantify +0.15–0.25 Sharpe improvement on equity long/short books from adaptive vs fixed thresholds. Brock, Lakonishok & LeBaron (1992, Journal of Finance) identified the failure mode: population-level thresholds miscalibrate in different vol regimes — which is exactly what EigenView's universe experiences.

Implementation cost: ~1 hour. No training. No overfitting risk. This is the highest-ROI change to the TA engine.

### What to build in 180 days (requires training data — start collecting now)

**Gradient Boosted Trees for confidence calibration.**

A GBT trained on `(indicator_state_vector → pattern_label)` can learn non-linear interactions that rules miss. E.g., RSI=52 + ADX=28 + squeeze=ON + vol_ratio=0.7 together has a higher success rate than any single threshold would predict.

Guo et al. (2023) showed GBT outperforms rule-based classifiers by 6-12 F1 points on breakout/pullback classification on US large-cap equity held-out data.

**Start collecting now, train later:**
Add to every daily scan output:
```sql
-- In signal_bench table (already exists)
pattern_label     TEXT,    -- setup_type that fired
forward_return_5d  REAL,   -- close[+5] / close[0] - 1
forward_return_20d REAL,   -- close[+20] / close[0] - 1
indicator_state    TEXT    -- JSON snapshot of all indicator values at signal time
```
After 180 days of scanning ~450 tickers, you have enough labeled examples per pattern to train. The GBT replaces or supplements the classification function — same output contract, better confidence scores.

### What NOT to build (confirmed waste of effort)

| Approach | Verdict | Why |
|---|---|---|
| CNN/LSTM on raw OHLCV | Skip | Doesn't consistently beat rules in rigorous backtests (Jiang, Kelly & Xiu, JoF 2023). Requires retraining to stay current. Not worth complexity. |
| LLM for TA pattern confirmation | Skip | Sending `{rsi:52, adx:28}` to Claude adds 500-2000ms latency, $5-25/scan cost, and applies generic Wilder thresholds you're trying to escape. Zero edge over rules. |
| LLM for chart image analysis | Skip | April 2026 benchmark: all frontier models at coin-flip accuracy on direction, 0.46% on pattern naming. |

### LLM role in the TA pipeline (correct scope)

LLM is NOT a classifier in the TA layer. LLM role is downstream:
- Thesis generation: given `(pattern, indicators, gex, flow)` → plain English narrative. Already planned.
- Material/noise filtering: news text classification. Already planned.
- Chat: answering "why this pick?" grounded to actual data. Already planned.

---

## Open questions / decisions pending

- [ ] Mean reversion setups in scope for v1? (BB reversion, EMA200 snap-back)
- [ ] Chart trail (SuperTrend / Chandelier) as display-only vs executable signal?
- [ ] R:R minimum threshold: 2.0 or configurable?
- [ ] `valid_until` logic: 5 trading days flat, or extend if price is still in setup zone?
- [ ] BOS vs breakout: should BOS replace `breakout`/`breakdown`, or supplement as a higher-confidence variant?

---

## Decisions log

| Date | Decision | Rationale |
|---|---|---|
| 2026-05-04 | Per-stock GEX as hard gate confirmed as novel | No open-source equivalent found; academic evidence supports |
| 2026-05-04 | Claude vision ruled out for pattern detection | April 2026 benchmark: 57% direction accuracy, 0.46% pattern naming |
| 2026-05-04 | 21-setup taxonomy approved (draft) | Covers all 4 categories long + short |
| 2026-05-04 | SuperTrend as primary trail (pandas_ta confirmed) | In package, direction-aware, self-contained |
| 2026-05-04 | Chandelier exit as secondary trail (port from Pine) | Not reliably in pandas_ta stable; port 30 lines |
