# CONFLUENCE — Merged Project Instructions for Claude Code
# (EigenView + PULSE macro layer · Updated April 2026)

You are the build agent for **EigenView**, a curated daily options + futures intelligence dashboard. This file is your north star. Read it on every fresh session. Keep it updated as decisions lock.

---

## REPORTING STYLE — MANDATORY (no rambling)

When reporting findings, audits, or status: **plain English, one table where it fits, no preamble.**
- NO code-speak in prose: don't cite file paths, line numbers, function names, or internal variable names in explanations. Explain what the thing *does* in trader/user terms. Pseudo-code only if logic must be shown.
- NO narrating the investigation ("I read X, then traced Y…"). State the conclusion.
- Issues → ONE table: Problem | Fix | Status. No per-item essays.
- No restating the question, no "great question", no back-and-forth filler.
- Detailed file/line evidence belongs in a doc under `docs/`, not in chat.
- Token discipline is a hard rule here, not a preference.

## STALE-SPEC RULE — code is truth (locked 2026-05-29)

Any doc/spec older than 2 weeks is NOT authoritative. Before trusting any doc (incl. the taxonomy/dormant/macro descriptions in THIS file), verify against code; on conflict, **code wins** and the doc must be rewritten. Known-stale: TA "21 setups" (code has 16), dormant "6-signal scorer" (code is a 4-trigger tally), macro "5 signals" (code has 4).

---

## WHAT THE PRODUCT IS — ONE PARAGRAPH

A dashboard that runs every morning and outputs **a short ranked list of specific instruments to look at today** — stocks (options plays) and optionally futures — each with a score, setup type, entry zone, stop level, and a plain-English thesis. Not a scanner. Not a data dump. A curated, opinionated, ready-to-act list. The macro regime is checked first; if it's red, no long picks appear regardless of individual stock signals.

---

## WHAT IT IS NOT

- Not a scanner with filter panels
- Not a raw data dashboard
- Not a backtesting platform (v1)
- Not a broker integration (v1)
- Not real-time tick streaming (v1 — 15-min delayed data is fine)
- Not multi-user or cloud-deployed (v1 — local Windows only)
- Not configurable to the point of overwhelming the user

---

## THE SIGNAL STACK (9 layers, 2 projects merged)

**Gate 0 — Macro Regime Gate** *(from PULSE — NEW)*
Runs before any pick is scored. 4 signals → score 0–10.
- SPX GEX regime (positive/negative vs gamma flip)
- VIX M1/M2 term structure (contango = bullish, backwardation = danger)
- DIX dark pool index (SqueezeMetrics — >43% = bullish)
- SPX breadth (% stocks above 50dma — >50% = healthy)
- Retail capitulation bonus (+1 if Citadel GMI capitulation active)

GREEN ≥7 → screener runs normally
YELLOW 4–6 → picks shown with CAUTION flag
RED ≤3 → no long picks output, short setups only

**Gate 1 — Technical Analysis** *(from EigenView — unchanged)*
Hard gate. EMA stack, ADX, RSI, ATR, Bollinger, volume profile, swing levels. ML pattern classifier: compression_break | breakout | pullback_in_trend | flag | etc. Firing condition: pattern confidence >0.6 AND weekly trend not contradicting daily.

**Gate 2 — Per-Stock GEX / Dealer Positioning** *(both projects — one implementation)*
Hard gate. Net dealer gamma, gamma flip level, call wall, put wall, regime flag (short_gamma / long_gamma / flip_zone).

**Factor 1 — Options Flow** *(both projects — merged, enhanced)*
From EigenView: V/OI ratio (≥3 = new position), premium >$500K, aggressive side detection.
From PULSE: dark pool cluster detection (3+ prints in ±0.5% price band).
Combined: 1 qualified contract (premium + V/OI + side) AND dark pool cluster at entry = max conviction.

**Factor 2 — Dormant-Bet Radar** *(EigenView — THE moat)*
Large long-dated positions (30–180 days old, ≥$500K premium, ≥90 DTE at opening) scored for activation probability near catalyst. V1: rule-based 6-signal scorer. V2: sklearn GradientBoosting on historical data.

**Factor 3 — Catalyst + Novelty Sentiment** *(EigenView — unchanged)*
Earnings within 30 days, macro events (Fed/CPI/NFP/FDA), novelty embedding distance from 30-day baseline per ticker, LLM MATERIAL/NOISE filter, FinBERT direction scoring.

**Factor 4 — Macro Timing Layer** *(from PULSE — NEW)*
VIX M1/M2 backwardation score, DIX trend direction, retail capitulation indicator. These upgrade individual pick conviction scores when the macro environment is reversal-favorable. Applied as a conviction bonus, not a hard gate.

**Futures Signal Stack** *(from PULSE — optional module)*
ES/NQ: GEX regime + CTA flip level proximity. CL/GC: OVX/GVZ term structure + COT net long percentile + futures curve shape (contango/backwardation). These instruments do NOT get dormant-bet or TA scoring — only macro regime + their specific signals.

**GATE LOGIC:**
```
Qualify = Macro Regime (Gate 0) passes AND TA (Gate 1) fires AND GEX (Gate 2) fires
          AND at least 2 of {Flow, Dormant, Sentiment} fire
Conviction = 1–5 based on firing count × strength
Rank = conviction DESC, then dormant bonus, then IV rank (cheaper vol = better R:R)
Output = every qualifying instrument per day (NO cap — show what the scan returns)
```

---

## MVP DEFINITION — What Ships First

**MVP = the smallest thing that proves the product works.**

MVP scope:
1. **Macro regime gate** — calculates and displays GREEN/YELLOW/RED every morning
2. **3–5 stock picks per day** — with TA + GEX gates + at least flow OR sentiment firing
3. **Score + setup type + entry zone + stop** on each pick
4. **LLM thesis** on each pick (2–3 sentences)
5. **Wireframe v2 UI** wired to real data — no module framework yet, no template switcher
6. **AI chat** wired to Claude API — one question, one answer, grounded to pick data

**NOT in MVP:**
- Dormant-bet radar (requires 30+ days of chain data accumulation — start storing NOW, activate later)
- Novelty embeddings (add in Phase 3)
- Futures instruments (add after MVP validates)
- Template switcher / custom canvas
- Module framework (extract into modules after MVP works as a monolith)
- Alert system
- Closed picks archive / journal

**Why this sequence:** Prove the data pipeline works → prove the scoring produces real picks → prove the AI thesis is useful → THEN build the surrounding product.

---

## PHASE 1 — Data Layer (MVP critical path)

**Goal:** Clean data in SQLite. Nothing else. No factors, no UI, no AI.
**Acceptance:** `eigenview fetch NVDA` runs clean, writes all tables, prints summary. Tests pass.
**Estimated time:** 2–3 hours

### Files to build in Phase 1:

**`src/eigenview/data/prices.py`**
- yfinance wrapper for OHLCV (daily + intraday 1h)
- Returns: pandas DataFrame with open/high/low/close/volume
- Cache: SQLite with 15-min TTL for intraday, overnight for daily
- Test: fetch_prices("NVDA", "1d", 90) returns 90 rows, no gaps on trading days

**`src/eigenview/data/chains.py`**
- Options chain from yfinance (free, 15-min delay)
- Compute greeks: delta, gamma via py_vollib Black-Scholes
- Returns: dict {calls: DataFrame, puts: DataFrame} with columns: strike, expiry, bid, ask, volume, OI, IV, delta, gamma
- Also computes and returns: IV rank (current IV vs 52-week high/low)
- Cache: refresh on each daily scan, hold intraday
- Test: fetch_chain("NVDA") returns both DataFrames with gamma column populated

**`src/eigenview/data/news.py`**
- Alpha Vantage News & Sentiment API (free tier: 25 calls/day)
- Finnhub news API (free tier)
- Deduplicates across sources by URL hash
- Returns: list of {headline, summary, timestamp, source, url, ticker}
- Rate limit handling: exponential backoff, fail gracefully
- Test: fetch_news("NVDA", lookback_days=3) returns ≥1 article, no duplicate URLs

**`src/eigenview/data/calendar.py`**
- Earnings dates: yfinance.Ticker.calendar
- Macro events: Finnhub economic calendar
- Returns: list of {event_type, date, ticker_or_macro, days_from_now}
- Test: get_catalysts("NVDA") returns next earnings date within 90 days

**`src/eigenview/data/macro.py`** *(PULSE addition — new to original plan)*
- SqueezeMetrics DIX + GEX: scrape https://squeezemetrics.com/monitor/dix — returns daily DIX (float) and GEX (float)
- VIXCentral term structure: scrape https://vixcentral.com — returns {m1, m2, m3, m4, m5, m6, contango_m1m2_pct}
- CFTC COT: download weekly from https://www.cftc.gov/dta/public/newcot/deafut.txt — parse managed money net long for CL (crude oil), GC (gold), ES (S&P 500 futures)
- Cache: DIX/VIX daily, COT weekly
- Test: fetch_macro() returns dict with all 8 fields populated, handles source downtime gracefully

**`src/eigenview/data/storage.py`**
SQLite schema. Tables:
```sql
prices (ticker, date, open, high, low, close, volume, timeframe)
chains (ticker, snapshot_date, strike, expiry, call_put, bid, ask, volume, oi, iv, delta, gamma)
news (id, ticker, headline, summary, url_hash, source, timestamp, fetched_at)
catalysts (ticker, event_type, event_date, days_from_now, updated_at)
macro_daily (date, dix, gex_index, vix_m1, vix_m2, vix_m3, vix_contango_pct)
cot_weekly (week_ending, instrument, net_long_pct, net_long_contracts)
picks (id, date, ticker, score, setup_type, entry_low, entry_high, stop, conviction, thesis, created_at)
dormant_bets (id, ticker, contract, original_date, strike, expiry, original_premium, current_oi, original_oi)
```
Write helpers: upsert_prices(), upsert_chain(), upsert_news(), write_pick()
Read helpers: get_prices(), get_chain(), get_latest_macro()
Schema migration: auto-creates tables on first run

**`src/eigenview/cli.py`** — Phase 1 commands only:
```
eigenview fetch <ticker>       # runs all fetchers for one ticker, writes to DB, prints summary
eigenview fetch-macro          # runs macro fetcher, writes DIX/VIX/COT to DB
eigenview status               # prints DB row counts and latest timestamps per table
```

**`tests/data/`** — one test file per module:
- test_prices.py, test_chains.py, test_news.py, test_calendar.py, test_macro.py, test_storage.py
- Use pytest-vcr cassettes for HTTP calls (record once, replay offline)
- Required tests per module: happy path, no-data (empty response), stale data (>24h), malformed input

**Phase 1 does NOT include:**
- Factor modules (Phase 2)
- FastAPI server (Phase 2 / 3)
- Any AI calls (Phase 4)
- Any UI changes (Phase 4)

---

## PHASE 2 — Factor Modules (one module = one file = one PR)

Build and test each independently. Each returns a FactorResult. Do not advance until each has passing tests.

**`src/eigenview/factors/macro_regime.py`** — Gate 0
Input: macro_daily row from DB
Output: FactorResult with score (0–10), regime ("GREEN"/"YELLOW"/"RED"), narrative
Scoring: per formula in signal stack section above

**`src/eigenview/factors/technical.py`** — Gate 1
Input: prices DataFrame (90 days daily + 5 days 1h)
Dependencies: pandas_ta (computes all indicators in 3 lines)
Output: FactorResult with pattern, confidence, trend_direction, key_levels

**`src/eigenview/factors/gex.py`** — Gate 2
Input: chains dict from DB
Output: FactorResult with regime, gamma_flip, call_wall, put_wall, net_gex

**`src/eigenview/factors/flow.py`** — Factor 1
Input: chains dict (for V/OI, premium, aggressive side) + dark pool prints (FINRA data)
Output: FactorResult with largest_sweep, dark_pool_cluster_price, flow_direction

**`src/eigenview/factors/dormant.py`** — Factor 2
Input: historical chains from DB (dormant_bets table), current chains, catalysts
Output: FactorResult with activation_probability, original_bet details, narrative
V1: rule-based scorer (6 signals × weights)
Note: Fires meaningfully only after 30+ days of chain data in DB — start storing chains on Day 1

**`src/eigenview/factors/sentiment.py`** — Factor 3
Input: news list, catalysts
AI calls: MATERIAL/NOISE filter (Claude API), FinBERT sentiment direction (local)
Novelty: sentence-transformers MiniLM (local, free, ~80MB download)
Output: FactorResult with novelty_z, sentiment_direction, catalyst_proximity, top_headline

---

## PHASE 3 — Synthesis Engine

**`src/eigenview/synthesis/gate.py`**
qualify_pick() function — gate logic as specified above
conviction() function — 1–5 score

**`src/eigenview/synthesis/ranker.py`**
rank_picks() — sorts qualified picks by conviction, dormant bonus, IV rank

**`src/eigenview/cli.py`** — add:
```
eigenview daily-scan [--universe S&P500|test5]   # runs full pipeline, writes picks to DB
```

**Acceptance:** daily-scan on 5-ticker test universe (NVDA AAPL TSLA META AMD) produces output in <30s. Top picks make sense given market conditions.

---

## PHASE 4 — Wire Wireframe to Real Data (MVP UI)

**Do NOT build the module framework yet.** Wire the wireframe monolith directly to the API.

**`src/eigenview/api/`** — FastAPI endpoints (subset for MVP):
```
GET /api/market/regime          → macro regime score + signal breakdown
GET /api/picks                  → today's ranked picks list
GET /api/pick/{ticker}          → full pick detail (factors + entry/stop)
GET /api/pick/{ticker}/factors  → factor results for detail view
GET /api/chart/{ticker}         → OHLCV for price chart
POST /api/chat                  → SSE stream → Claude API → token-by-token response
```

**`web/index.html`** — wire wireframe to these endpoints:
1. Replace hardcoded market context cells with /api/market/regime data
2. Replace hardcoded pick cards with /api/picks data
3. Wire pick click → /api/pick/{ticker} → populate detail view
4. Wire chat input → POST /api/chat → SSE stream → render tokens
5. Wire price chart placeholder → TradingView Lightweight Charts + /api/chart/{ticker}

**GEX overlay on chart:** add gamma_flip, call_wall, put_wall as horizontal lines via TradingView createPriceLine()

**MVP done when:** Morning scan produces real picks. Clicking a pick shows real factor data. AI chat answers "why this pick?" with the actual numbers. Theme toggle still works.

---

## MODULAR EXTRACTION (after MVP works)

After MVP is validated, extract into proper module framework per docs/02-modules.md. Sequence:
1. Extract pick-cards.js (cleanest, least dependencies)
2. Extract market-context.js
3. Extract ai-chat.js (needs SSE)
4. Extract price-chart.js (needs TradingView)
5. Extract factor-strip.js + tabs
6. Add template switcher
7. Add module framework (mount/unmount/resize)
8. Add 5 preset templates
9. Add custom canvas / drag-drop

**This is NOT Phase 1 or MVP work.** Don't do it earlier.

---

## TECH STACK (locked)

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Finance + ML ecosystem |
| Pkg mgr | uv | Fast, Claude Code native |
| Framework | FastAPI | Lightweight, async, SSE support |
| Frontend | Vanilla HTML/JS/CSS | No build toolchain, wireframe v2 is the starting point |
| Charting | TradingView Lightweight Charts | Free, pro-grade |
| Storage | SQLite | Zero-config, local |
| Data (free) | yfinance + Alpha Vantage free + Finnhub free + SqueezeMetrics scrape + VIXCentral scrape + CFTC public data | All free tier, no paid dependency for Phase 1 |
| ML (local) | scikit-learn, sentence-transformers MiniLM | Local inference, no API cost |
| LLM | Anthropic Claude API (claude-sonnet-4-6) | Thesis + chat + MATERIAL/NOISE filter |
| Scheduling | Windows Task Scheduler | Native, no infra |

---

## REPO LAYOUT

```
eigenview/
├── CLAUDE.md                          ← THIS FILE — read every session
├── README.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── docs/                              ← handoff docs — read all on first session
│   ├── 01-vision.md through 12-engineering-standards.md
│   └── wireframes/
│       ├── wireframe-v1.html          ← reference only
│       └── wireframe-v2.html          ← VISUAL SOURCE OF TRUTH — open in browser before any UI work
├── src/
│   └── eigenview/
│       ├── data/                      ← Phase 1
│       │   ├── prices.py
│       │   ├── chains.py
│       │   ├── news.py
│       │   ├── calendar.py
│       │   ├── macro.py               ← PULSE addition
│       │   └── storage.py
│       ├── factors/                   ← Phase 2
│       │   ├── macro_regime.py        ← PULSE addition (Gate 0)
│       │   ├── technical.py
│       │   ├── gex.py
│       │   ├── flow.py
│       │   ├── dormant.py
│       │   └── sentiment.py
│       ├── synthesis/                 ← Phase 3
│       │   ├── gate.py
│       │   └── ranker.py
│       ├── api/                       ← Phase 4
│       │   └── routes.py
│       ├── llm/                       ← Phase 4
│       │   ├── thesis.py
│       │   ├── chat.py
│       │   └── prompts/               ← prompt templates as .md files
│       │       ├── thesis.md
│       │       ├── material_noise.md
│       │       └── chat_system.md
│       └── cli.py
├── web/
│   └── index.html                     ← wireframe-v2 as starting point, wired to API in Phase 4
├── tests/
│   ├── data/                          ← test_prices.py, test_chains.py, etc.
│   ├── factors/
│   ├── synthesis/
│   └── fixtures/                      ← VCR cassettes + canned data
└── data/                              ← SQLite DB lives here (gitignored)
```

---

## DEPENDENCIES & CONFIG

See `pyproject.toml` for the dependency list and `.env.example` for required API keys / config slots. Do not duplicate them here.

---

## SESSION START CHECKLIST (every session)

1. Read this file (CLAUDE.md)
2. First session ever: read all docs in `docs/` in order (01 through 12), then open wireframe-v2.html in a browser
3. Check `docs/07-decisions.md` for anything locked since last session
4. Run `git log --oneline -10` to see what was last done
5. Run `uv run pytest -q` to confirm tests still pass
6. Ask "what's the goal of this session?" if not obvious from context

---

## ENGINEERING PROCESS — 5-STEP LEAN

**feature/** branches (new behavior): all 5 steps.
**fix/** branches (confirmed bug/typo/config): steps 1, 4, 5 only.

1. **Propose** — Claude reads codebase + git log. Writes proposal in chat: what, how, out-of-scope. User approves before any code.
2. **Branch + PR** — `git checkout -b feature/<name>`. Open draft PR immediately (`gh pr create --draft`).
3. **Tests first** — write failing tests before touching `src/`. Commit tests. Confirm they fail.
4. **Implement** — write `src/` code. Run full test suite locally. Must pass before pushing.
5. **Review + Merge** — push and open the PR **automatically** when a unit is committed; never ask permission to push or PR (user-locked 2026-05-30). Then wait for CI green. **User merges — no self-merge on master.** Auto applies to push + PR only, never to merge.

### Rules
- Never edit `src/` on master
- Never `git commit --no-verify`
- Integration tests hit real data — no mocks, no cassettes, no synthetic fixtures
- One module = one file = one PR

---

## CRITICAL RULES — NEVER BREAK

1. **Wireframe v2 is the visual source of truth.** When building UI, match it. Don't redesign.
2. **Macro regime gate always runs first.** No pick logic runs if Gate 0 is RED.
3. **TA + GEX are hard gates.** No pick qualifies without both firing.
4. **One module = one file = one PR.** Don't mix factor work with data work with UI work.
5. **Tests before scoring logic.** Every factor module ships with a test file.
6. **Never display AI-generated options math without independent validation.** Recalculate R:R from stated strikes/debits in a rules layer before showing in UI.
7. **Dormant-bet chain data starts accumulating Day 1.** Even though dormant.py won't fire for 30 days, write chains to DB from the first daily scan.
8. **Update CLAUDE.md and docs/07-decisions.md** when non-obvious decisions lock.
9. **AI failures degrade gracefully.** Missing thesis falls back to template. Missing chat shows retry. Never blocks picks from displaying.
10. **Phase sequence is not optional.** Data layer → factors → synthesis → API + UI → AI wiring. Out-of-order builds create debugging nightmares.

---

## WHERE TO LOOK WHEN…

| Question | File |
|---|---|
| Product vision and differentiators | docs/01-vision.md |
| All UI modules and data contracts | docs/02-modules.md |
| Factor math and data sources | docs/03-factors.md |
| UI layout templates (JSON) | docs/04-templates.md |
| Full tech stack and API surface | docs/05-architecture.md |
| Original 10-phase build plan | docs/06-build-plan.md |
| All locked decisions | docs/07-decisions.md |
| Design tokens, colors, type, spacing | docs/09-design-system.md |
| Interactions, flows, keyboard nav | docs/10-ux-patterns.md |
| AI prompts, costs, fail-open logic | docs/11-ai-spec.md |
| Code standards, test patterns, git | docs/12-engineering-standards.md |
| Visual source of truth | docs/wireframes/wireframe-v2.html |
| PULSE macro signal specs | This file (signal stack section above) |

---

## DECISIONS LOG ADDITIONS (April 2026 — this merge)

**2026-04-29 · PULSE + EigenView merged**
Decision: Merge PULSE macro signal layer into EigenView. PULSE's macro regime gate (Gate 0) added as pre-step before all EigenView pick logic. PULSE's commodity/futures signals added as optional module. EigenView architecture, build plan, wireframe, and design system unchanged.
Rationale: EigenView had no macro regime awareness — individual picks could fire in a Sep-Apr type meltdown. PULSE's gate closes this critical gap. Cost: +12 hours to existing 15-20 hour build plan. New files: data/macro.py, factors/macro_regime.py. Data sources: SqueezeMetrics (free), VIXCentral (free), CFTC (free).

**2026-04-29 · MVP scope locked**
Decision: MVP = macro regime gate + 3-5 picks/day + LLM thesis + wireframe v2 wired to real data + AI chat. Dormant-bet radar, novelty embeddings, futures instruments, template switcher, module framework all deferred to post-MVP.
Rationale: Prove data pipeline → scoring → AI thesis → UI works before building surrounding product. Dormant-bet needs 30 days of chain data anyway.

**2026-04-29 · Modular extraction deferred**
Decision: Build MVP as wired monolith (wireframe → FastAPI). Extract into proper module framework only after MVP is validated.
Rationale: Module framework is infrastructure, not product. Building it before the product works creates rework risk.

**2026-04-29 · Macro regime scoring thresholds calibrated**
Decision: DIX bullish threshold = 43% (not 45%). Breadth healthy threshold = 50% above 50dma (not 55%).
Rationale: 45%/55% thresholds produced RED on mixed-signal conditions that historically were YELLOW (pre-rally coiled states). Looser thresholds correctly classify those as YELLOW with caution flag rather than blocking all picks.

**2026-05-29 · max_picks cap REMOVED everywhere**
Decision: No cap on the number of picks. Removed the `[: settings.max_picks]` trim from the ranker, deleted the `max_picks` config field, removed `MAX_PICKS` from `.env.example` and this file, and updated the synthesis spec. DAILY now shows every ticker that passes the gate.
Rationale: User directive — the dashboard must show exactly what the scan returns, never an artificial top-N. Curated short-list framing is dropped; ranking order is preserved (conviction → dormant → gex), only the trim is gone.

**2026-05-29 · Dashboard list semantics locked (Glass Velvet wiring)**
- **DAILY** = today's final picks (passed the full gate: macro OK, TA firing, GEX firing, ≥2 soft factors). No cap.
- **WEEKLY** = picks from the prior 7 days, today excluded. A ticker in today's DAILY is excluded from WEEKLY. WEEKLY shows each ticker once (its most recent prior alert). "Today wins."
- **ALL** = every scanned ticker where TA OR dormant fired (signal matrix). No cap. Matrix endpoint filter changed from `ta>0` to `ta>0 OR dormant>0` to match this.
- **SCAN button** triggers the full pipeline async (download → factors → gate → rank → thesis → save), UI stays live, animated progress bar + engine status text (no true %), polls status, auto-refreshes when done, surfaces the engine's 4h-cooldown message honestly.
- **No fallback** to old scan dates, no invented client-side thresholds, no caps, no fake data. Today is empty until a scan runs — honest state.
Rationale: User-locked over a multi-round clarification. Full detail in docs/13-dashboard-spec.md.

---

## TA MODULE — ARCHITECTURE DECISIONS (from trading-architecture.md, merged 2026-05-04)

### 21-Setup Taxonomy

Four strategy categories. Category determines weekly context required, stop rules, and valid exits.

| Category | Thesis | Weekly required (long) | Noise filter |
|---|---|---|---|
| **Trend Continuation** | Established trend, price pulls back, resumes | Bullish (EMA8>21, RSI 45–65, ADX >15) | Volume must decline on pullback |
| **Breakout** | Price compressed, expansion follows with volume | Not bearish | Volume must confirm expansion |
| **Reversal** | Trend extended to exhaustion, first structural break | Extended (RSI >65 for bearish rev, <35 for bullish) | Requires divergence OR structural break, not just RSI alone |
| **Mean Reversion** | Price deviated from equilibrium, statistical pull back | Non-trending (ADX <20, flat EMAs) | Not valid if ADX >25 |

#### Trend Continuation setups

| Setup name | Detection | Libraries |
|---|---|---|
| `pullback_in_trend` | Daily bullish EMA stack, RSI at 40th pct, price > EMA21×0.99 < EMA50×1.08, vol declining | pandas_ta (EMA, RSI, ADX) |
| `pullback_deep` | Daily bullish, RSI 32–50, price touches EMA50, vol declining | pandas_ta |
| `pullback_to_structure` | Price tests prior swing high (now support) or prior breakout level | scipy argrelextrema |
| `flag_continuation` | Impulse move → 5–10 bar tight range, BB contracting, vol declining | pandas_ta squeeze_pro ON |
| `rally_in_downtrend` | Weekly bearish, RSI bounce to 43–62, price near EMA21 from below (short) | pandas_ta |

#### Breakout setups

| Setup name | Detection | Libraries |
|---|---|---|
| `breakout` | Close above N-bar swing high, vol >1.5× avg | scipy argrelextrema, pandas_ta |
| `breakdown` | Close below N-bar swing low, vol >1.5× avg (short) | same |
| `compression_break` | squeeze_pro ON→OFF, momentum positive, vol surge | pandas_ta squeeze_pro |
| `compression_break_down` | squeeze_pro ON→OFF, momentum negative (short) | pandas_ta squeeze_pro |
| `base_breakout` | 20+ bar low-vol contraction, price within 3% of 50-day high | pandas_ta |
| `base_breakdown` | Same inverted (short) | pandas_ta |
| `ema_reclaim` | Was below EMA50, closes above it vol >1.1× | pandas_ta |
| `ema_rejection` | Was above EMA50, closes below it (short) | pandas_ta |
| `bos_bullish` | Break of Structure: closes above last swing high in structure | smartmoneyconcepts bos_choch() |
| `bos_bearish` | Break of Structure: closes below last swing low (short) | smartmoneyconcepts bos_choch() |

#### Reversal setups

| Setup name | Detection | Libraries |
|---|---|---|
| `bullish_reversal` | RSI bull divergence + vol spike + weekly RSI <35 | pandas_ta (RSI div: custom) |
| `bearish_reversal` | RSI bear divergence + vol spike + weekly RSI >65 (short) | pandas_ta |
| `overbought_reversal` | Daily trend bullish, RSI >68, vol down day, weekly RSI >65 (short) | pandas_ta |
| `oversold_bounce` | RSI <32, reversal candle, above EMA200 | pandas_ta |
| `failed_breakdown` | Dipped below EMA21, recovered above with vol >1.5× | pandas_ta |
| `failed_breakout` | Exceeded N-bar high, reversed below with vol (short) | scipy + pandas_ta |
| `choch_bullish` | Change of Character: first close above prior swing high in downtrend | smartmoneyconcepts bos_choch() |
| `choch_bearish` | Change of Character: first close below prior swing low in uptrend (short) | smartmoneyconcepts bos_choch() |

#### Mean Reversion setups

| Setup name | Detection | Libraries |
|---|---|---|
| `bb_mean_reversion_long` | Price at lower BB, ADX <20, weekly ADX <20 | pandas_ta (BB, ADX) |
| `bb_mean_reversion_short` | Price at upper BB, ADX <20 (short) | pandas_ta |
| `ema200_snap_long` | Price >15% below EMA200, weekly RSI <35 | pandas_ta |
| `ema200_snap_short` | Price >15% above EMA200, weekly RSI >70 (short) | pandas_ta |

**Total: 21 setups.** Additions over original 15: pullback_deep, pullback_to_structure, flag_continuation, bos_bullish, bos_bearish, choch_bullish, choch_bearish, bb_mean_reversion long/short, ema200_snap long/short.

---

### Library-First Strategy

Replace hand-coded detection with maintained libraries wherever possible.

| Need | Library | Action |
|---|---|---|
| All indicators (EMA, RSI, ADX, ATR, BB, MACD) | `pandas_ta` | In deps — keep |
| Compression state | `pandas_ta.squeeze_pro()` | Replace hand-coded ATR squeeze |
| Swing levels (SPH/SPL) | `scipy.signal.argrelextrema` | swingtrend not on PyPI; use scipy (same output) |
| BOS / CHoCH / FVG | `smartmoneyconcepts` PyPI | Add to deps |
| SuperTrend trailing stop | `pandas_ta.supertrend()` | In deps |
| Chandelier exit | NJiHin/TA_Chandelier port | ~30 lines, not reliably in pandas_ta stable |
| RSI divergence | Custom (no library) | Keep existing |

---

### Stop / Target / R:R Formulas

**Initial stop placement by category:**

| Category | Long stop | Short stop |
|---|---|---|
| Trend Continuation | Below pullback swing low (last SPL before entry) | Above rally swing high |
| Breakout | Below breakout level (prior resistance = new support) | Above breakdown level |
| Reversal | Below reversal candle wick low | Above reversal candle wick high |
| Mean Reversion | entry − 1.5×ATR14 | entry + 1.5×ATR14 |

ATR sizing: `stop = max(logical_stop, entry − 1.0×ATR14)`. Shorts use 1.25×ATR14 minimum (volatility asymmetry).

```python
stop_long  = max(swing_low * 0.995, entry_low - atr)
stop_short = min(swing_high * 1.005, entry_high + atr * 1.25)
```

**Target (measured move) by category:**

| Category | Target method |
|---|---|
| Trend Continuation | Prior swing high (from argrelextrema) |
| Breakout | `breakout_level + (breakout_level - base_low)` |
| Reversal | 50% or 61.8% Fibonacci retracement of prior move |
| Mean Reversion | EMA20 or BB midline |

**R:R minimum:** target / (entry − stop) ≥ 3.0 (R:R floor; below = downgraded). Setups below 3.0 are downgraded in conviction (not eliminated).

**Trailing stop methods (display-only, chart overlays):**

| Method | Formula | Best for |
|---|---|---|
| SuperTrend | `pandas_ta.supertrend(length=7, multiplier=3.0)` | Trending moves (primary) |
| Chandelier exit | `highest_high(22) - 3×ATR(22)` | Trending moves, tighter |
| EMA trail | Trail under EMA21 | Trend continuation |
| EMA50 trail | Trail under EMA50 | Longer swing holds |

Trail activates only after price moves ≥1 ATR in favor. Before that: use initial stop.

---

### Rolling Percentile Strategy (replaces hardcoded thresholds)

All 50+ literal threshold numbers in `technical.py` replaced with ticker-specific rolling percentiles over 90 days. Rationale: population-average thresholds misfire on high-vol tickers (too often) and low-vol tickers (never). Adaptive thresholds calibrate to each stock's own regime.

```python
rsi_oversold   = np.percentile(rsi_90d,  20)   # was: 32
rsi_overbought = np.percentile(rsi_90d,  80)   # was: 68–72
adx_trending   = np.percentile(adx_90d,  65)   # was: 20–25
vol_surge      = np.percentile(vol_90d,  70)   # was: 1.5× avg
vol_light      = np.percentile(vol_90d,  35)   # was: 0.8× avg
atr_contracted = np.percentile(atr_90d,  30)   # was: 0.65–0.7× avg
```

Exception: ADX gate for pullback keeps absolute floor of 15 (prevents false firing in compression).

Evidence: Clenow (2013) + Carver (2015) quantify +0.15–0.25 Sharpe improvement from adaptive vs fixed thresholds on equity long/short books.

---

### 5-State Weekly Classifier

Weekly context computed by resampling daily prices — no new data source needed.

```python
weekly_df = daily_df.resample('W-FRI').agg({'open':'first','high':'max','low':'min','close':'last','volume':'sum'}).dropna()
weekly_df.ta.ema(length=10, append=True)
weekly_df.ta.ema(length=20, append=True)
weekly_df.ta.adx(length=14, append=True)
weekly_df.ta.rsi(length=14, append=True)
```

States: `BULLISH | BULLISH_EXTENDED | NEUTRAL | BEARISH_WEAK | BEARISH_STRONG`

---

### Multi-Timeframe (MTF) Matrix

Weekly state gates which setup categories are valid for that stock that day.

| Weekly state | Condition | Valid long setups | Valid short setups |
|---|---|---|---|
| **Bullish** | EMA8>21, RSI 45–65, ADX >15 | Trend Continuation, Breakout | None |
| **Bullish extended** | RSI >70 OR ADX >35 | Bearish Reversal only | Bearish Reversal |
| **Neutral / sideways** | ADX <20, EMAs flat | Breakout (compression), Mean Reversion | Breakdown, Mean Reversion |
| **Bearish weak** | EMA8<21 recently, RSI 40–55 | Mean Reversion, Failed Breakdown | Trend Continuation (short), Breakdown |
| **Bearish strong** | EMA8<21, RSI <45, ADX >20 | Bullish Reversal only | Trend Continuation (short), Breakdown |
| **Bearish extended** | RSI <30 OR ADX >35 | Bullish Reversal only | None (no new shorts at extreme) |

---

### Signal Persistence — `signal_triggers` Table

Every daily scan writes to this table (add to storage.py schema):

```sql
CREATE TABLE signal_triggers (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    scan_date   TEXT NOT NULL,
    setup_type  TEXT NOT NULL,
    direction   TEXT NOT NULL,    -- 'long' | 'short'
    entry_low   REAL,
    entry_high  REAL,
    stop        REAL,
    target      REAL,
    rr_ratio    REAL,             -- target / (entry - stop)
    confidence  REAL,
    fired_at    TEXT,             -- ISO datetime of bar that fired
    valid_until TEXT              -- scan_date + 5 trading days
);
```

Also add to `signal_bench` for future GBT training:
```sql
forward_return_5d  REAL,
forward_return_20d REAL,
indicator_state    TEXT   -- JSON snapshot of all indicator values at signal time
```

Signal freshness: Fresh (<2h) / Valid (2–8h) / Stale (>8h) — displayed as badge on pick card.

---

### Chart Toggles

Persistent in localStorage per ticker.

| Toggle | Default |
|---|---|
| EMA 21 | ON |
| EMA 50 | ON |
| EMA 200 | ON |
| BB | OFF |
| Signals (historical markers) | ON |
| SuperTrend | OFF |

---

### LLM Role in TA Pipeline (confirmed scope)

LLM is NOT a pattern classifier. Confirmed waste of effort:
- CNN/LSTM on raw OHLCV — doesn't beat rules in rigorous backtests (Jiang, Kelly & Xiu, JoF 2023)
- LLM for TA pattern confirmation — 500–2000ms latency, $5–25/scan, zero edge over rules
- LLM for chart image analysis — April 2026 benchmark: coin-flip on direction, 0.46% on pattern naming

LLM correct scope (downstream only): thesis generation, material/noise news filter, chat.

Future (180+ days, needs training data): GBT on `(indicator_state_vector → pattern_label)` can learn non-linear interactions. Start collecting `indicator_state` + `forward_return` columns in `signal_bench` from Day 1 of scanning.

---

### TA Decisions Log (2026-05-04)

| Date | Decision |
|---|---|
| 2026-05-04 | Per-stock GEX as hard gate confirmed novel — no open-source equivalent |
| 2026-05-04 | Claude vision ruled out for pattern detection — April 2026: 57% direction accuracy, 0.46% pattern naming |
| 2026-05-04 | 21-setup taxonomy approved (draft) |
| 2026-05-04 | SuperTrend as primary trail (pandas_ta confirmed in package) |
| 2026-05-04 | Chandelier exit as secondary trail — port ~30 lines from Pine |
| 2026-05-04 | swingtrend not on PyPI; scipy.signal.argrelextrema used instead |
| 2026-05-04 | Rolling 40th-percentile RSI replaces hardcoded 38–57 range for pullback detection |
| 2026-05-04 | TA Stage 1 pullback_in_trend: 15/15 tests passing (2.07s) |
