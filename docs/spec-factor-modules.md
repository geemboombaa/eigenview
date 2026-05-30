# EigenView Factor Modules — Full Requirements Spec

## Scope

Six factor/synthesis modules. Each GIVEN/THEN AC maps to one testable behavior.
All thresholds live in `settings` (configurable via env vars — never hardcoded in logic).

---

## REQ-GEX — Dealer Gamma Exposure Factor

### REQ-GEX-1 — Net GEX calculation
GIVEN a list of chain rows with `gamma`, `oi`, `call_put`, `strike` populated
AND a `spot_price` > 0
THEN `net_gex = sum(call_gex_by_strike.values()) - sum(put_gex_by_strike.values())`
AND each contract's GEX contribution = `gamma × oi × 100 × spot² × 0.01`
AND result detail contains key `net_gex` (float, may be negative)

### REQ-GEX-2 — Regime classification
GIVEN `net_gex` and `gamma_flip` computed
THEN if price is within `settings.gex_flip_zone_pct` (default 5%) of gamma_flip → regime = `"flip_zone"`, strength = 0.3
AND if not flip_zone and net_gex < 0 → regime = `"short_gamma"`, strength = min(1.0, abs(net_gex) / 1e9)
AND if not flip_zone and net_gex >= 0 → regime = `"long_gamma"`, strength = 0.1
AND all three regimes set `firing = True`

### REQ-GEX-3 — Call wall and put wall
GIVEN call OI aggregated by strike
THEN call_wall = strike with highest call OI where `spot < strike ≤ spot × 1.5`
AND put_wall = strike with highest put OI where `spot × 0.5 ≤ strike < spot`
AND both returned in detail dict; `None` if no candidates in range

### REQ-GEX-4 — Gamma flip via linear interpolation
GIVEN net GEX by strike sorted ascending
THEN gamma_flip = interpolated price where net GEX crosses zero (sign change between adjacent strikes)
AND interpolation formula: `prev_strike + abs(prev_net)/(abs(prev_net)+abs(curr_net)) × (curr_strike - prev_strike)`
AND returns `None` if fewer than 2 strikes or no sign change found

### REQ-GEX-5 — Expiry bucketing
GIVEN chain rows with `expiry` attribute (date)
THEN each row's GEX contribution is added to `gex_by_expiry` dict
AND bucket key: `"0dte"` if dte ≤ 0, `"weekly"` if dte ≤ 7, `"monthly"` if dte ≤ 30, else `"quarterly"`
AND result detail contains key `gex_by_expiry` (dict[str, float], only populated buckets present)

### REQ-GEX-6 — Gamma cluster / pinning risk
GIVEN all strikes across calls and puts
THEN pin_strike = strike with highest `abs(call_gex - put_gex)` net exposure
AND `pinning_risk = True` if `abs(spot - pin_strike) / spot ≤ 0.01`
AND result detail contains key `gamma_cluster = {"pinning_risk": bool, "pin_strike": float|None}`

### REQ-GEX-7 — No data path
GIVEN chains list is empty OR no rows have both gamma and oi non-null
THEN return `FactorResult.no_data("gex", "no chain data")`

---

## REQ-FLOW — Options Flow Factor

### REQ-FLOW-1 — Sweep qualification
GIVEN a chain row with bid, ask, volume, oi populated
THEN mid = (bid + ask) / 2
AND premium = mid × volume × 100
AND voi = volume / oi (0 if oi = 0)
AND row qualifies if `premium ≥ settings.flow_min_premium_usd` AND `voi ≥ settings.flow_min_voi_ratio`
(defaults: $500K, 3.0)

### REQ-FLOW-2 — Dominant side and strength
GIVEN at least one qualified sweep
THEN call_premium = sum of qualified call premiums; put_premium = sum of qualified put premiums
AND dominant_side = "calls" if call_premium ≥ put_premium else "puts"
AND largest_sweep = max single qualified premium
AND strength = min(1.0, largest_sweep / settings.flow_strength_max_usd) (default $2M)
AND fires = True

### REQ-FLOW-3 — No qualified sweeps
GIVEN all chain rows fail qualification (below premium or V/OI threshold)
THEN return FactorResult with firing=False, label="NO FLOW"
AND detail contains: largest_sweep_usd=0, total_qualified=0, call_premium=0, put_premium=0, dominant_side="none"

### REQ-FLOW-4 — Narrative format
GIVEN flow fires
THEN narrative = "Aggressive {dominant_side} flow: {N} qualified sweep(s), largest ${X}M. Call/put premium ratio {R}:1."
AND ratio shown as "∞" when put_premium = 0

### REQ-FLOW-5 — All thresholds configurable
GIVEN settings contain flow_min_premium_usd, flow_min_voi_ratio, flow_strength_max_usd
THEN changing these values changes qualification and strength without code changes

---

## REQ-DORM — Dormant Bet Radar Factor

### REQ-DORM-1 — Accumulation guard (< 30 days history)
GIVEN days_of_history < 30
THEN return FactorResult with firing=False, label="ACCUMULATING"
AND narrative contains progress indicator (e.g. "Chain history {N}/30 days.")
AND does NOT query dormant_bets table

### REQ-DORM-2 — No bets tracked yet (≥ 30 days history)
GIVEN days_of_history ≥ 30 AND dormant_bets table has no rows for this ticker
THEN return FactorResult with firing=False, label="ACCUMULATING"
AND narrative = "No dormant bets tracked yet. Accumulating chain history."

### REQ-DORM-3 — 6-signal scorer
GIVEN a DormantBet row and current chain index
THEN score computed as:
  sig1: current_oi > original_oi × 1.1 → +2
  sig2: catalyst within 14 days → +2
  sig3: abs(bet.strike - spot) / spot < 0.05 → +2
  sig4: original_premium ≥ $1,000,000 → +1
  sig5: (expiry - original_date).days ≥ 90 → +1
  sig6: expiry > today + 7 days → +1
AND max possible score = 9 (MAX_SCORE)
AND activation_probability = best_score / MAX_SCORE

### REQ-DORM-4 — Firing threshold
GIVEN activation_probability computed
THEN fires = activation_probability ≥ settings.dormant_firing_threshold (default 0.44)
AND label = "ACTIVE" if fires else "DORMANT"
AND strength = activation_probability

### REQ-DORM-5 — Bet identification (scanner integration)
GIVEN chain rows from daily scan for a ticker
THEN positions with `(expiry - today).days ≥ settings.dormant_min_dte` (default 60)
AND `mid × oi × 100 ≥ settings.dormant_min_premium` (default $300K)
THEN upserted into dormant_bets table with contract key = f"{ticker}{expiry%y%m%d}{call_put}{int(strike)}"
AND existing contracts for same ticker+contract+date are not duplicated

### REQ-DORM-6 — Narrative content
GIVEN best_bet and scoring signals
THEN narrative opens with: "Dormant ${premium_m:.1f}M {call_put} at ${strike:.0f} (exp {expiry}) activating."
AND appends OI growth pct if growing
AND appends "Catalyst within 14 days." if catalyst_near
AND appends strike proximity pct if within 5% of spot

---

## REQ-SENT — Catalyst + Novelty Sentiment Factor

### REQ-SENT-1 — Lookback window
GIVEN ticker and session
THEN query NewsItem rows where timestamp ≥ now - settings.sentiment_lookback_days (default 3)
AND query all Catalyst rows for ticker

### REQ-SENT-2 — No data path
GIVEN no news rows found within lookback window
THEN return FactorResult.no_data("sentiment", "no recent news")
AND catalysts alone are NOT sufficient to fire sentiment

### REQ-SENT-3 — Keyword scoring
GIVEN news rows found
THEN for each article: text = headline + " " + summary
AND bull_hits = count of words in text that match BULLISH keyword set
AND bear_hits = count of words in text that match BEARISH keyword set
AND total_bull = sum(bull_hits); total_bear = sum(bear_hits)
AND sentiment_direction: "bullish" if total_bull > total_bear, "bearish" if total_bear > total_bull, else "neutral"

### REQ-SENT-4 — Catalyst proximity scoring
GIVEN catalyst rows for ticker
THEN catalyst_score: +3 per catalyst where 0 < days_from_now ≤ 7; +1 per catalyst where 7 < days_from_now ≤ 30
AND catalyst_near = True if catalyst_score ≥ 3

### REQ-SENT-5 — Firing condition
GIVEN sentiment computed
THEN fires = catalyst_near OR (len(news) ≥ 3 AND total_bull > total_bear)
AND strength = clamp((catalyst_score/3 + max(0, novelty_z)) / 2, 0.0, 1.0)
AND novelty_z = (news_count / lookback_days) - 1.0

### REQ-SENT-6 — Detail dict completeness
GIVEN sentiment result
THEN detail contains: news_count, catalyst_near, catalyst_score, novelty_z, bull_hits, bear_hits, bull_score (alias), bear_score (alias)

---

## REQ-MACRO — Macro Regime Gate (Gate 0)

### REQ-MACRO-1 — Scoring formula
GIVEN latest MacroDaily row from DB
THEN score starts at 0
AND +3 if gex_index > 0 (positive market-maker gamma)
AND +2 if vix_contango_pct > 0 (VIX term structure in contango)
AND +3 if dix > 0.43 (dark pool index above threshold — configurable via settings.macro_dix_threshold)
AND +2 if vix_m1 < 20 (low vol regime — configurable via settings.macro_vix_low_threshold)
AND score clamped to [0, 10]

### REQ-MACRO-2 — Regime thresholds
GIVEN score computed
THEN GREEN if score ≥ settings.macro_regime_green_threshold (default 7)
AND YELLOW if settings.macro_regime_red_threshold ≤ score < green_threshold
AND RED if score < settings.macro_regime_red_threshold (default 3)
AND firing = True for GREEN and YELLOW; False for RED
AND strength = score / 10

### REQ-MACRO-3 — Gate behavior (scanner integration)
GIVEN macro regime is RED
THEN qualify_pick() returns False for ALL long setups regardless of factor scores
AND short setups (patterns in SHORT_SETUP_PATTERNS) still qualify through RED gate

### REQ-MACRO-4 — No data path
GIVEN no MacroDaily row exists in DB
THEN return FactorResult.no_data("macro_regime", "no macro data in DB")

### REQ-MACRO-5 — Detail dict
GIVEN regime computed
THEN detail contains: score (int), dix (float|None), gex_index (float|None), vix_m1 (float|None), vix_contango_pct (float|None)

### REQ-MACRO-6 — Narrative format
GIVEN regime result
THEN narrative = "Macro regime {regime} ({score}/10): {comma-separated active signal names}."
AND signal names: "positive GEX", "VIX contango", "dark pool buying above threshold", "low vol regime"

---

## REQ-SYNTH — Synthesis Gate and Ranker

### REQ-SYNTH-1 — Hard gate logic
GIVEN a TickerScorecard
THEN qualify_pick returns False if macro_score < red_threshold AND setup is not short
AND qualify_pick returns False if technical.firing is False
AND qualify_pick returns False if gex.firing is False
AND qualify_pick returns True only if all hard gates pass AND soft_firing ≥ 2

### REQ-SYNTH-2 — Soft factor count
GIVEN flow, dormant, sentiment factors
THEN soft_firing = count of {flow.firing, dormant.firing, sentiment.firing} that are True
AND minimum 2 of 3 required for qualification (Tier A)

### REQ-SYNTH-3 — Conviction score (1–5)
GIVEN five factor strengths: technical, gex, flow, dormant, sentiment
THEN raw = mean of all five strengths
AND conviction 5 if raw ≥ 0.8, 4 if ≥ 0.6, 3 if ≥ 0.4, 2 if ≥ 0.2, else 1

### REQ-SYNTH-4 — Tier classification
GIVEN a scorecard that does not qualify (Tier A)
THEN Tier B: both hard gates fire AND soft_firing ≥ 1
AND Tier C: one hard gate fires AND soft_firing ≥ 1
AND Tier D: no hard gates but flow.strength ≥ 0.7 OR dormant.strength ≥ 0.6
AND None: does not meet any tier threshold

### REQ-SYNTH-5 — Ranking order
GIVEN list of qualified scorecards
THEN sorted descending by (conviction_score, dormant.strength, gex.strength)
AND every qualifying scorecard is returned (NO cap — removed 2026-05-29)

### REQ-SYNTH-6 — Entry zone calculation
GIVEN scorecard and direction (long/short)
THEN long entry_low = swing_low; entry_high = swing_low + (swing_high - swing_low) × 0.3
AND short entry_high = swing_high; entry_low = swing_high - (swing_high - swing_low) × 0.15
AND swing_low/high from technical.detail; fallback to spot ± 2%

### REQ-SYNTH-7 — Stop level calculation
GIVEN direction
THEN long stop = swing_low × 0.98
AND short stop = swing_high × 1.02

### REQ-SYNTH-8 — Pick persistence
GIVEN qualified scorecards after ranking
THEN each pick upserted to picks table (update if same ticker+date exists, insert otherwise)
AND factors_json column stores all 5 factor results as JSON
AND Tier B/C/D scorecards written to signal_bench table for future GBT training

### REQ-SYNTH-9 — Short setup identification
GIVEN technical.label
THEN setup classified as short if label in SHORT_SETUP_PATTERNS:
{bearish_reversal, breakdown, rally_in_downtrend, compression_break_down, ema_rejection,
base_breakdown, overbought_reversal, failed_breakout}
AND direction field on Pick = "short" for these, "long" otherwise
