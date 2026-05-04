# EigenView — Master Signal Audit & Proposal
# Last updated: 2026-05-03

All numbered items. Status: **Done** | **Partial** | **Missing**. Priority: P0 (critical bug) → P1 (core signal quality) → P2 (meaningful enhancement) → P3 (nice-to-have).

---

## PART 1 — MASTER ITEM TABLE

### Gate 0 — Macro Regime

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 1 | SPX GEX index positive/negative (+3 pts) | Done | — | |
| 2 | VIX M1/M2 contango/backwardation (+2 pts) | Done | — | |
| 3 | VIX M1 absolute level <20 (+2 pts) | Done | — | |
| 4 | DIX dark pool index >43% (+3 pts) | Done | — | |
| 5 | SPX breadth: % stocks above 50dma >50% (+2 pts) | **Missing** | P1 | In spec, not coded. Requires breadth data source |
| 6 | Retail capitulation bonus — Citadel GMI (+1 pt) | **Missing** | P2 | Page scrape needed |
| 7 | COT data integration in macro score | **Missing** | P2 | Table exists with data, never read by scorer |
| 8 | Fed meeting proximity modifier | **Missing** | P3 | FOMC dates from Finnhub calendar |
| 9 | VIX M3/M4/M5/M6 term structure curvature | **Missing** | P3 | Beyond M1/M2 contango — catch inversions further out |

---

### Gate 1 — Technical Analysis

#### Indicators

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 10 | EMA 21 / 50 (daily) | Done | — | |
| 11 | ADX 14 (daily) | Done | — | |
| 12 | RSI 14 (daily) | Done | — | |
| 13 | Bollinger Bands 20 (daily) | Done | — | |
| 14 | ATR 14 (daily) | Done | — | |
| 15 | Volume ratio vs 20d avg | Done | — | |
| 16 | EMA 200 (daily — long-term baseline) | **Missing** | P1 | Needed for weekly trend gate logic |
| 17 | Weekly EMA stack (10w / 20w / 50w) | **Missing** | P1 | Core of MTF framework — resample daily to weekly, no new data |
| 18 | Weekly ADX + RSI | **Missing** | P1 | Direction gate — block bullish picks in strong weekly downtrends |
| 19 | RSI divergence detector (bull + bear) | **Missing** | P1 | Price vs RSI local extrema over N bars — key for reversals |
| 20 | Fibonacci retracement levels | **Missing** | P2 | 38.2 / 50 / 61.8 of prior impulse — pullback quality check |
| 21 | MACD (daily) | **Missing** | P2 | Momentum divergence, histogram contraction pre-breakout |
| 22 | On-Balance Volume (OBV) | **Missing** | P2 | Cumulative buying pressure; divergence vs price = distribution signal |
| 23 | Volume character per bar (declining on pullback, expanding on breakout) | **Missing** | P2 | Rolling 5d vol trend direction — validates pullback/breakout quality |
| 24 | VWAP (intraday — 1H data) | **Missing** | P3 | Entry refinement only; needs 1H prices |
| 25 | Volume Profile / VPOC | **Missing** | P3 | Referenced in UI spec; requires full intraday volume data |

#### Patterns — Trend Continuation (existing)

| # | Pattern | Status | Priority | Quality Enhancement Needed |
|---|---------|--------|----------|---------------------------|
| 26 | `compression_break` | Done | P1 | Add: weekly BB also squeezing (MTF), vol >2x on break close, RSI <70 at break |
| 27 | `pullback_in_trend` | Done | P1 | Add: weekly trend bullish (REQUIRED filter), declining vol on pullback, Fib proximity |
| 28 | `breakout` | Done | P1 | Add: prior level tested ≥2x (proven level), closing above (not intraday), weekly not in downtrend |

#### Patterns — Trend Continuation (missing)

| # | Pattern | Status | Priority | Definition |
|---|---------|--------|----------|-----------|
| 29 | `flag` / `bull_flag` | **Missing** | P1 | Prior impulse >5% in ≤10 bars, consolidation ≤50% retracement, 5-15 bars, vol declining in flag, breakout on vol >1.5x. Noise filter: vol MUST decline during flag or it's distribution |
| 30 | `ema_reclaim` | **Missing** | P1 | Pullback below EMA50, then CLOSE back above EMA50 on vol >1.2x. Weekly trend must be bullish. First reclaim only (3rd touch usually breaks through) |
| 31 | `base_breakout` / VCP | **Missing** | P2 | 3-8 week tight range (<15% width), range gets progressively tighter each week, vol >2x on breakout close. Highest quality continuation pattern — low noise |

#### Patterns — Trend Reversal (all missing)

| # | Pattern | Status | Priority | Definition |
|---|---------|--------|----------|-----------|
| 32 | `bullish_reversal` | **Missing** | P1 | Prior downtrend (EMA21 < EMA50 ≥20 days), RSI divergence (price lower low, RSI higher low over ≥5 days), vol spike >2x on reversal bar, next bar closes green (2-bar confirm). Noise filter: weekly RSI must be turning up, not still falling |
| 33 | `oversold_bounce` | **Missing** | P2 | RSI <30 daily + RSI <35 weekly, price at/near put wall (GEX support), vol dry-up then expansion. Short-duration signal (1-3 days). Never fires without GEX put wall proximity — GEX is the noise filter |
| 34 | `failed_breakdown` | **Missing** | P2 | Established support level, price breaks below intraday, CLOSES above same or next day. Recovery vol >1.5x. Bear trap → short squeeze setup. Noise filter: support must be tested ≥2x previously |
| 35 | `bearish_reversal` | **Missing** | P2 | Macro RED only. Prior uptrend, RSI divergence (price higher high, RSI lower high ≥5 days), break below EMA21 on vol >1.5x. Never outputs a long pick |

#### Quality / Noise Filters (cross-pattern)

| # | Filter | Status | Priority | Rule |
|---|--------|--------|----------|------|
| 36 | Weekly trend alignment gate | **Missing** | P1 | No bullish picks if weekly EMA21 < EMA50 AND weekly ADX >25. Eliminates biggest source of false breakouts |
| 37 | Pattern close validation | **Partial** | P1 | Breakout: must CLOSE above level (not pierce). Currently only checks close vs recent_high — OK. But compression_break checks vs BBU intraday |
| 38 | Volume character validation | **Missing** | P1 | Pullbacks need DECLINING vol (healthy). Breakouts need EXPANDING vol. Currently only checks 1-day ratio, not direction trend |
| 39 | Extended RSI gate | **Missing** | P2 | Breakout patterns with daily RSI >75 flagged as LOW quality (already extended). Score penalized. |
| 40 | Post-earnings gap exclusion | **Missing** | P2 | Patterns that form in bars immediately after earnings gap have much lower signal quality — flag with quality penalty |
| 41 | 1H entry refinement | **Missing** | P3 | Use 1H chart to find exact entry within daily entry zone. Requires 1H data in scanner |

#### Score / Output

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 42 | IV Rank computation at scan time | **Missing** | P1 | Currently hardcoded `null` in `_pick_to_dict`. Compute from chain ATM IV vs 52-week IV range (TODO #4) |
| 43 | ATR-based entry zone | **Partial** | P2 | Current: swing_low + 30% of swing range. Improvement: entry_low = EMA21 or prior support, entry_high = entry_low + 0.5×ATR |
| 44 | ATR-based stop level | **Partial** | P2 | Current: swing_low × 0.98 (fixed %). Improvement: stop = entry_low − 1.5×ATR (volatility-normalized) |

---

### Gate 2 — GEX / Dealer Positioning

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 45 | Net dealer gamma (call GEX − put GEX) | Done | — | |
| 46 | Gamma flip level (linear interpolation) | Done | — | |
| 47 | Call wall (highest OI call above spot, ≤50% range) | Done | — | |
| 48 | Put wall (highest OI put below spot, ≤50% range) | Done | — | |
| 49 | Regime: short_gamma / long_gamma / flip_zone | Done | — | flip_zone = within ±5% of gamma flip |
| 50 | Max pain level | **Missing** | P1 | Strike where aggregate option value is minimized. Low-effort, high-display-value |
| 51 | GEX by expiry bucket (0DTE / weekly / monthly) | **Missing** | P2 | 0DTE GEX is mechanically different — amplifies intraday vol, not swing. Needs separate treatment |
| 52 | Delta Exposure (DEX) alongside GEX | **Missing** | P2 | Directional dealer hedge flow. GEX = gamma, DEX = delta. Together = full picture |
| 53 | GEX strike density near spot | **Missing** | P2 | Cluster of high-GEX strikes near spot = strong magnetic pull / resistance level |
| 54 | Vanna exposure (vol × delta sensitivity) | **Missing** | P3 | Important during IV crush events |
| 55 | Charm exposure (time-delta, 0DTE) | **Missing** | P3 | 0DTE-specific; not needed for swing trades |

---

### Factor 1 — Options Flow

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 56 | V/OI ratio ≥3.0 threshold | Done | — | |
| 57 | Premium filter ≥$500K per contract | Done | — | |
| 58 | Call/put premium totals + dominant side | Done | — | |
| 59 | Largest sweep size output | Done | — | |
| 60 | Aggressive side detection (ask-side vs bid-side fill) | **Missing** | P1 | Currently uses mid-price. Ask-side = buyer aggressive. Bid-side = seller aggressive. This is the most important flow signal — without it, volume/premium alone is ambiguous |
| 61 | Sweep vs block distinction | **Missing** | P1 | Sweep = same order fills across multiple exchanges simultaneously. Block = single large fill. Sweeps are more aggressive/urgent |
| 62 | Dark pool cluster detection | **Missing** | P2 | FINRA ATS data: 3+ prints in ±0.5% price band = institutional accumulation. Per spec: "max conviction" when combined with sweep. Data source: FINRA ATS download or paid feed |
| 63 | Multi-leg / spread detection | **Missing** | P2 | Single-leg flow = directional bet. Multi-leg = hedge or defined-risk. Directional weighted higher |
| 64 | Time-of-day weighting | **Missing** | P3 | First 30 min and last 30 min sweeps carry more urgency |
| 65 | Net OI change (new positions only) | **Missing** | P3 | Volume − closing trades = truly new open interest. More precise than V/OI ratio alone |

---

### Factor 2 — Dormant Bet Radar

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 66 | sig1: OI growth >10% from original (+2 pts) | Done | — | |
| 67 | sig2: Catalyst within 14 days (+2 pts) | Done | — | |
| 68 | sig3: Strike within 5% of spot (+2 pts) | Done | — | |
| 69 | sig4: Original premium ≥$1M (+1 pt) | Done | — | |
| 70 | sig5: ≥90 DTE at open (+1 pt) | Done | — | |
| 71 | sig6: Still >7 days to expiry (+1 pt) | Done | — | |
| 72 | **DormantBet table population** | **Missing** | P0 | **Critical gap.** `scanner.py` calls `score_dormant()` which reads `DormantBet` table — but nothing writes to that table. Need a `_identify_dormant_bets()` function in scanner: identify large (≥$500K premium), long-dated (≥90 DTE at open), ≥30-days-old positions from chain history. Run daily, upsert to `dormant_bets` |
| 73 | Recent volume on dormant strike | **Missing** | P1 | New fills appearing on a stale position = activation signal. Check daily chain volume at `best_bet.strike` vs its baseline |
| 74 | IV change at dormant strike | **Missing** | P2 | Vol being bid at that specific strike = someone paying for that move |
| 75 | Delta convergence (strike going ITM) | **Missing** | P2 | Track delta at dormant strike over time — increasing delta = price converging to strike |
| 76 | OI absolute floor check | **Missing** | P2 | OI may have grown 10% but from a tiny base — check absolute OI still meaningful (>500 contracts) |
| 77 | ML model v2 (GradientBoosting) | **Missing** | P3 | Spec Phase 2. Needs ≥30 days activation/non-activation history to train |

---

### Factor 3 — Catalyst + Sentiment

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 78 | Catalyst proximity scoring (<7d = +3, 7-30d = +1) | Done | — | |
| 79 | Article count novelty proxy | **Partial** | P1 | Simple `count/days` placeholder. Not a real z-score. Fires correctly but with no calibration |
| 80 | Keyword bullish/bearish scoring | **Partial** | P1 | 10-word sets. Brittle, noisy. Functional placeholder only |
| 81 | Sentiment direction output | Done | — | |
| 82 | **FinBERT NLP sentiment** | **Missing** | P1 | Replace keyword matching. Local model, no API cost. Gives probability scores per article, not word counts |
| 83 | **LLM MATERIAL/NOISE filter** (Claude API) | **Missing** | P1 | Per spec: classify each headline as MATERIAL (company-specific catalyst) vs NOISE (general market commentary). Run before sentiment scoring. Prevents macro noise inflating individual stock sentiment |
| 84 | **Novelty embedding distance** (MiniLM) | **Missing** | P1 | Per spec: embed each article, compare to 30-day rolling baseline per ticker. Z-score = how unusual is today's news flow. Current proxy (article count) is a poor substitute |
| 85 | News source credibility weighting | **Missing** | P2 | Reuters/WSJ/Bloomberg = weight 1.5. Press release = weight 0.5. Random blog = weight 0.3 |
| 86 | Earnings estimate revisions as catalyst | **Missing** | P3 | Analyst EPS revisions = forward-looking catalyst signal |
| 87 | Social sentiment (Reddit WSB, fintwit) | **Missing** | P3 | Out of scope for MVP; mention but defer |

---

### Synthesis / Gate Logic

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 88 | `qualify_pick()` — hard gates + 2/3 soft | Done | — | |
| 89 | `conviction_score()` 1-5 | Done | — | |
| 90 | `tier_score()` A/B/C/D | Done | — | |
| 91 | `setup_type()` | Done | — | |
| 92 | `entry_zone()` from swing levels | **Partial** | P2 | See item 43 |
| 93 | `stop_level()` fixed % | **Partial** | P2 | See item 44 |
| 94 | Signal freshness (`signal_fired_at`, age badges) | **Missing** | P1 | TODO #5. `signal_fired_at` field on Pick, age computed in API, Fresh/Valid/Stale badge in UI |
| 95 | Direction-aware gate (short setups when macro RED) | **Missing** | P2 | Macro RED → no long picks. Should output short setups from `bearish_reversal` pattern. Currently no short path exists |
| 96 | Heat map score storage (per-factor scores for all tickers) | **Missing** | P1 | Required for signal heat map. Currently only picks/bench saved. Need `FactorScore` table or JSON blob per ticker per day |

---

### Signal Heat Map (new feature)

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 97 | `/api/signals/heat` endpoint | **Missing** | P1 | Returns `{ta:[...5], gex:[...5], flow:[...5], dormant:[...5], sentiment:[...5]}` top-5 per factor |
| 98 | `signal-heat.js` frontend module | **Missing** | P1 | Grid: 5 columns × 5 rows. Color-coded by score. Click → select ticker |
| 99 | Factor score storage for all scanned tickers | **Missing** | P1 | See item 96 — prerequisite |

---

### Infrastructure / Data Pipeline

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 100 | Daily scan CLI | Done | — | |
| 101 | Fetch CLI per ticker | Done | — | |
| 102 | DB migration — new SignalBench columns (TODO #11) | **Missing** | P1 | `tier`, `factors_json`, `direction`, `setup_type`, `conviction`, `entry_low`, `entry_high`, `stop` |
| 103 | Windows Task Scheduler 8AM auto-scan (TODO #8) | **Missing** | P2 | `.bat` + Task Scheduler XML |
| 104 | Backend pytest suite updates for new pick fields (TODO #10) | **Missing** | P2 | |
| 105 | Historical options chain data | **Missing** | P3 | Blocked: historicaloptiondata.com or similar paid source needed for GEX/Flow backtest |
| 106 | FINRA ATS dark pool data feed | **Missing** | P3 | Required for item 62. Public download at finra.org/finra-data/browse-catalog/otc-transparency-data |
| 107 | SPX breadth data source | **Missing** | P1 | Required for item 5. Free: stooq.com `^SHI` or yfinance `^MMFI` (% above 50dma) |

---

### UI / Frontend

| # | Item | Status | Priority | Notes |
|---|------|--------|----------|-------|
| 108 | Pick cards (thesis, conviction, factor chips) | Done | — | |
| 109 | Factor strip with inline detail panels | Done | — | |
| 110 | Market context subnav strip | Done | — | |
| 111 | Category nav + WATCH tab | Done | — | |
| 112 | Date navigation (◀ TODAY ▶) | Done | — | |
| 113 | DEMO mode (mock picks) | Done | — | |
| 114 | Price chart (TradingView + GEX levels) | Done | — | |
| 115 | AI chat (SSE streaming) | Done | — | |
| 116 | Help page (9 tabs) | Done | — | |
| 117 | Themes (dark / light / glass / bento) | Done | — | |
| 118 | Auto-refresh (5 min poll) | Done | — | |
| 119 | NDX100 universe | Done | — | |
| 120 | Signal heat map panel (TODO #3) | **Missing** | P1 | New module `signal-heat.js` |
| 121 | Signal freshness badges (TODO #5) | **Missing** | P1 | Fresh (< 2h) / Valid (2-8h) / Stale (>8h) |
| 122 | Favorites persistence (TODO #6) | **Missing** | P2 | Favorites table + `/api/favorites` |
| 123 | Alert wiring (TODO #7) | **Missing** | P2 | Trigger: price enters entry zone |
| 124 | Category filter — mylist / closed / alerts (TODO #9) | **Missing** | P2 | Requires items 122 + 123 |
| 125 | Backtest chart overlay — signal markers (TODO #12) | **Missing** | P3 | Toggle on chart, `/api/signals/:ticker?tf=1d` |
| 126 | Voice orb module (TODO #15) | **Missing** | P3 | Registered, not mounted |

---

## PART 2 — TA SIGNAL QUALITY FRAMEWORK

This section defines the noise-elimination strategy for Gate 1. Nothing here changes what signals exist — it defines the quality filters that determine whether a signal is trustworthy.

### Core Principle: Multi-Timeframe (MTF) Analysis

Higher timeframes carry less noise because more data is aggregated per bar. The hierarchy:

```
Weekly  →  Direction gate (is the big trend with us?)
Daily   →  Pattern detection (primary signal, what and where?)
1H      →  Entry refinement (exact trigger within the daily zone)
```

**Rule:** A daily pattern that contradicts the weekly trend is noise 80% of the time. Do not eliminate it — mark it as LOW QUALITY and lower its confidence score.

### Weekly Direction Gate (items 17, 18, 36)

Computed from daily prices resampled to weekly — no new data source needed.

| Weekly State | Meaning | Bullish Pattern Handling |
|---|---|---|
| EMA10w > EMA20w, ADX_w > 20 | Strong uptrend | Full confidence |
| EMA10w > EMA20w, ADX_w < 20 | Weak / early uptrend | Confidence −10% |
| EMA10w < EMA20w, ADX_w < 20 | Sideways / choppy | Confidence −20%, only compression/reversal patterns |
| EMA10w < EMA20w, ADX_w > 25 | **Strong downtrend** | Block all bullish continuation patterns. Only reversals allowed, with extra confirmation requirement |

This single gate eliminates the largest class of false breakouts: daily breakouts in weekly downtrends.

### Pattern Quality Matrix

Each pattern has a required context, structure check, and confirmation check. Confidence is reduced when optional quality criteria aren't met — the pattern still fires, but at lower score.

#### `compression_break` (enhanced)

```
Context  :  Weekly not in strong downtrend (ADX_w < 25 if bearish)
Structure:  ATR ratio < 0.7 for ≥5 consecutive days (not just last bar)
             Price inside BB for ≥5 consecutive days before break
             RSI < 70 at break day (not already extended)
Confirm  :  Close above BBU (not intraday pierce)
             Volume ≥ 2.0x avg on break day (raised from 1.5x)
Quality+ :  Weekly BB squeezing simultaneously → confidence +10%
             MACD histogram contracting → confidence +5%
Noise    :  Compression during earnings week → confidence −20% (gap risk)
             Break on low volume (< 1.3x avg) → does not fire
```

#### `pullback_in_trend` (enhanced)

```
Context  :  Weekly uptrend REQUIRED (EMA10w > EMA20w). Most critical filter.
             Without this, pullback is often beginning of new downtrend.
Structure:  RSI 40-55 (healthy reset — not oversold, not still hot)
             Pullback did NOT break EMA50 (trend intact)
             Volume DECLINING during pullback (healthy retracement)
             Pullback touches or approaches Fib 38.2/50/61.8 of prior impulse
Confirm  :  First day of volume expansion after declining-vol pullback = entry
             Close above EMA21 on expansion day
Quality+ :  Fib alignment → confidence +5%
             OBV trend still rising during price pullback → confidence +10%
Noise    :  Volume expanding during pullback → pattern does NOT fire (distribution)
             3rd+ consecutive test of EMA21 without bounce → reduce confidence
```

#### `breakout` (enhanced)

```
Context  :  Weekly not in downtrend
             Prior resistance level tested ≥ 2x previously (proven level)
Structure:  Close above level (not just intraday touch)
             Base duration ≥ 10 bars above breakout level (not a V-spike)
             Range tightening into breakout (each of last 3 days has smaller range than day before)
Confirm  :  Volume ≥ 1.5x avg on break close
Quality+ :  Level tested 3+ times → confidence +10%
             Range tightening → confidence +5%
             Breakout occurs after compression period → confidence +10%
Noise    :  Volume < 1.2x avg → does NOT fire (unconfirmed)
             RSI > 75 at break → LOW QUALITY flag (extended, poor R:R)
             Break near daily market open (first 30 min) → wait for close confirmation
```

#### `flag` / `bull_flag` (new)

```
Context  :  Prior impulse ≥ 5% in ≤ 10 bars (flagpole exists)
             Weekly uptrend
Structure:  Consolidation ≤ 50% retracement of impulse height
             5–15 bar duration (too short = premature, too long = base not flag)
             Parallel or slightly downward channel (not widening)
Confirm  :  Volume MUST decline during flag formation (non-negotiable — expanding vol = distribution)
             Breakout of upper channel on vol ≥ 1.5x avg
Quality+ :  Flag channel getting tighter → confidence +10%
             Flagpole impulse was on very high vol → confidence +5%
Noise    :  Volume expanding during flag → does NOT fire
             Retracement > 50% of flagpole → not a flag, is a pullback (reclassify)
```

#### `ema_reclaim` (new)

```
Context  :  Weekly trend bullish (REQUIRED)
             Price has pulled below EMA50 — a test, not a new downtrend
Structure:  First reclaim (not 3rd or 4th test — multiple failures = structural breakdown)
             EMA50 acted as support intrabar (wick below, body above or at EMA)
Confirm  :  Close ABOVE EMA50 on vol ≥ 1.2x avg
Quality+ :  EMA50 is rising or flat (not declining) → confidence +5%
Noise    :  EMA50 is declining → reduce confidence 20% (catching a falling level)
             Previous reclaim failed within 10 bars → does NOT fire
```

#### `base_breakout` / VCP (new)

```
Context  :  3–8 week tight range (< 15% width from low to high)
             Prior uptrend before base (not a base in a downtrend)
             Weekly ADX declining during base (energy coiling, not trend losing strength)
Structure:  Range width gets smaller each week (week 3 range < week 2 range < week 1 range)
             Volume declining week over week during base
Confirm  :  Vol ≥ 2.0x avg on breakout close
             Close in upper 25% of day's range on breakout
Quality+ :  3+ week contraction → confidence +10%
             Volume reaches multi-week low in final contraction week → confidence +10%
Noise    :  Range not contracting → reclassify as flat base, lower confidence
             Volume expanding mid-base → potential distribution, lower confidence
```

#### `bullish_reversal` (new)

```
Context  :  Prior downtrend confirmed: EMA21 < EMA50 for ≥ 20 bars
             Weekly RSI turning up from below 40 (exhaustion)
             NOT in macro RED regime without additional confirmation
Structure:  RSI divergence: price makes lower low, RSI makes higher low over ≥ 5 bars
             (Detect via local extrema comparison — not just last 2 bars)
Confirm  :  High volume on reversal bar (≥ 2.0x avg) — exhaustion signal
             NEXT bar closes green = 2-bar confirmation (eliminates fakeouts)
             Close above EMA21 = structural change
Quality+ :  Volume on reversal bar highest in 20 days → confidence +15%
             Reversal at known support or put wall → confidence +10%
Noise    :  Weekly RSI still falling → confidence −20% (too early)
             No RSI divergence → does NOT fire as reversal (just a bounce)
             2-bar confirmation not met → pending, does not fire yet
```

#### `oversold_bounce` (new — SHORT DURATION, tactical)

```
Context  :  RSI_14 < 30 daily AND RSI_14 < 35 weekly (extreme oversold both TFs)
             Price at or within 2% of GEX put wall (REQUIRED — GEX is the floor, without it this is a falling knife)
Structure:  Volume dry-up (last 2 bars below 20d avg vol) — sellers exhausted
Confirm  :  First close green with vol expansion
Output   :  Labeled "TACTICAL BOUNCE" not "swing pick"
             Target: put_wall to gamma_flip level only
             Max hold: 3 days
Noise    :  No GEX put wall proximity → does NOT fire
             RSI < 30 but vol still expanding (sellers still active) → does NOT fire
```

#### `failed_breakdown` (new)

```
Context  :  Established horizontal support (tested ≥ 2x over ≥ 10 days)
Structure:  Price breaks below support (even intrabar)
             Recovers and CLOSES above support same or next session
             Recovery volume > 1.5x avg (real buying, not just lack of selling)
Confirm  :  2-session close above support → confirmed bear trap
Quality+ :  Recovery vol highest in 5 days → confidence +15%
             Short interest data showing high SI → short squeeze potential, +10%
Noise    :  Support level is declining EMA (not horizontal) → reclassify as ema_reclaim
             Recovery close is weak (bottom 30% of range) → not confirmed
```

#### `bearish_reversal` (new — MACRO RED ONLY)

```
Context  :  Macro regime RED (REQUIRED gate)
             Prior uptrend: EMA21 > EMA50 for ≥ 20 bars
Structure:  RSI divergence: price makes higher high, RSI makes lower high over ≥ 5 bars
Confirm  :  Break below EMA21 on vol ≥ 1.5x avg
             Close in lower 25% of day's range
Output   :  SHORT setup only. Direction = "short" in scorecard
Noise    :  No RSI divergence → does NOT fire
             Macro not RED → does NOT fire (no counter-trend shorts in uptrend)
```

### MTF Implementation Plan

No new data source needed for weekly analysis — resample daily prices:

```python
weekly_df = daily_df.resample('W-FRI').agg({
    'open': 'first', 'high': 'max', 'low': 'min',
    'close': 'last', 'volume': 'sum'
}).dropna()
weekly_df.ta.ema(length=10, append=True)   # EMA_10
weekly_df.ta.ema(length=20, append=True)   # EMA_20
weekly_df.ta.ema(length=50, append=True)   # EMA_50
weekly_df.ta.adx(length=14, append=True)   # ADX_14
weekly_df.ta.rsi(length=14, append=True)   # RSI_14
```

Returns a `WeeklyContext` dataclass passed into `score_technical()`. Used as context gate, not pattern detection.

### Pattern Confidence Score Summary

| Pattern | Base Confidence | Gate Removals (do not fire) | Noise Penalties |
|---|---|---|---|
| `compression_break` | 0.75 | vol < 1.3x, RSI > 80 | earnings week −0.20 |
| `pullback_in_trend` | 0.70 | vol expanding on pullback, no weekly uptrend | 3rd EMA test −0.10 |
| `breakout` | 0.80 | vol < 1.2x, no proven level | RSI > 75 −0.15 |
| `flag` | 0.75 | vol expanding in flag, retracement > 50% | — |
| `ema_reclaim` | 0.65 | recent failed reclaim, no weekly uptrend | declining EMA50 −0.20 |
| `base_breakout` | 0.85 | range not contracting | — |
| `bullish_reversal` | 0.70 | no RSI divergence, no 2-bar confirm | weekly RSI falling −0.20 |
| `oversold_bounce` | 0.60 | no GEX put wall, vol still expanding | — |
| `failed_breakdown` | 0.75 | no horizontal support, weak recovery | — |
| `bearish_reversal` | 0.70 | macro not RED, no RSI divergence | — |

---

## PART 3 — PRIORITY SUMMARY (P0→P3)

| Priority | # | Item |
|---|---|---|
| **P0** | 72 | DormantBet table population — nothing writes to it, factor is completely blind |
| **P1** | 5 | SPX breadth signal in macro regime |
| **P1** | 16-18 | EMA 200 + weekly EMA stack + weekly ADX/RSI (MTF framework foundation) |
| **P1** | 19 | RSI divergence detector (required for reversal patterns) |
| **P1** | 26-28 | Enhance existing 3 patterns with MTF + volume character filters |
| **P1** | 29-30 | Add `flag` + `ema_reclaim` patterns |
| **P1** | 32 | Add `bullish_reversal` pattern |
| **P1** | 36-38 | Weekly alignment gate + volume character validation |
| **P1** | 42 | IV Rank computation (currently null) |
| **P1** | 60-61 | Aggressive side detection + sweep vs block |
| **P1** | 73 | Recent volume on dormant strike |
| **P1** | 82-84 | FinBERT + LLM MATERIAL/NOISE + novelty embeddings |
| **P1** | 94 | Signal freshness field + age badges |
| **P1** | 96-99 | Heat map: factor score storage + API endpoint + UI module |
| **P1** | 102 | DB migration — SignalBench columns |
| **P1** | 107 | SPX breadth data source (stooq `^MMFI` or yfinance) |
| **P2** | 6-7 | Retail cap bonus + COT in macro score |
| **P2** | 20-23 | Fib levels, MACD, OBV, volume character indicator |
| **P2** | 31 | `base_breakout` pattern |
| **P2** | 33-35 | `oversold_bounce` + `failed_breakdown` + `bearish_reversal` |
| **P2** | 39-41 | RSI extension gate + gap exclusion + 1H entry |
| **P2** | 43-44 | ATR-based entry/stop |
| **P2** | 50-53 | Max pain + GEX by expiry + DEX + GEX density |
| **P2** | 62-63 | Dark pool cluster + spread detection |
| **P2** | 74-76 | IV at dormant strike + delta convergence + OI floor |
| **P2** | 85 | News source weighting |
| **P2** | 95 | Short pick path (macro RED → bearish output) |
| **P2** | 103-104 | Task Scheduler + backend tests |
| **P2** | 122-124 | Favorites + alerts + category filter |
| **P3** | 8-9 | Fed proximity + VIX term curvature |
| **P3** | 24-25 | VWAP + Volume Profile |
| **P3** | 54-55 | Vanna + Charm |
| **P3** | 64-65 | Flow time-of-day + net OI change |
| **P3** | 77 | Dormant ML model v2 |
| **P3** | 86-87 | Earnings estimate revisions + social sentiment |
| **P3** | 105-106 | Historical chain data + FINRA ATS feed |
| **P3** | 125-126 | Backtest overlay + voice orb |
