# CONFLUENCE — Merged Project Instructions for Claude Code
# (EigenView + PULSE macro layer · Updated April 2026)

You are the build agent for **EigenView**, a curated daily options + futures intelligence dashboard. This file is your north star. Read it on every fresh session. Keep it updated as decisions lock.

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
Output = top 3–10 qualifying instruments per day
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

## PHASE 0 — Already Done (repo scaffold)
Repo exists at: `C:\Users\v_per\OneDrive\Documents\Claude\Projects\Tradingview\eigenview-handoff`
Wireframes at: `C:\Users\v_per\OneDrive\Documents\Claude\Projects\Tradingview\eigenview-wireframe-v2.html`

**Phase 0 remaining tasks:**
- [ ] Create `src/eigenview/` directory structure (see repo layout below)
- [ ] Create `pyproject.toml` with uv dependencies
- [ ] Create `.env.example` with all required API key slots
- [ ] Copy wireframe-v2.html into `web/index.html` as starting point
- [ ] First commit: "phase-0: scaffold + handoff docs"

**API keys needed (Phase 1 blockers):**
```
ALPHA_VANTAGE_KEY=        # free at alphavantage.co — news + sentiment
FINNHUB_KEY=              # free at finnhub.io — news + earnings calendar
ANTHROPIC_API_KEY=        # for thesis generation + chat (Phase 4+)

# These are FREE — no key needed:
# yfinance — no key, just pip install
# SqueezeMetrics DIX+GEX — public page scrape
# VIXCentral — public page scrape
# CFTC COT reports — public data download
```

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

## PYPROJECT.TOML DEPENDENCIES (Phase 1 minimum)

```toml
[project]
name = "eigenview"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "yfinance>=0.2.40",
    "pandas>=2.0",
    "pandas-ta>=0.3.14b",
    "py_vollib>=1.0.1",
    "requests>=2.31",
    "beautifulsoup4>=4.12",   # for SqueezeMetrics + VIXCentral scraping
    "anthropic>=0.25",
    "fastapi>=0.110",
    "uvicorn>=0.29",
    "pydantic-settings>=2.0",
    "structlog>=24.0",
    "tenacity>=8.2",          # retry logic for API calls
    "typer>=0.12",            # CLI framework
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-vcr>=1.0",        # HTTP cassettes for tests
    "httpx>=0.27",            # for FastAPI test client
]

[project.optional-dependencies]
ml = [
    "scikit-learn>=1.4",
    "sentence-transformers>=2.7",   # local MiniLM embeddings
    "transformers>=4.40",           # FinBERT
    "torch>=2.2",                   # required by transformers
]
```

---

## .ENV.EXAMPLE

```
# Required for Phase 1
ALPHA_VANTAGE_KEY=your_key_here        # free: alphavantage.co/support/#api-key
FINNHUB_KEY=your_key_here              # free: finnhub.io/register

# Required for Phase 4 (AI features)
ANTHROPIC_API_KEY=your_key_here        # anthropic.com/api

# Optional overrides
DB_PATH=data/eigenview.db
LOG_LEVEL=INFO
UNIVERSE=SP500+NDX                     # or: test5 (NVDA AAPL TSLA META AMD)
DAILY_SCAN_HOUR=8                      # pre-market scan hour (ET)
MAX_PICKS=10
MACRO_REGIME_GREEN_THRESHOLD=7
MACRO_REGIME_RED_THRESHOLD=3
```

---

## SESSION START CHECKLIST (every session)

1. Read this file (CLAUDE.md)
2. First session ever: read all docs in `docs/` in order (01 through 12), then open wireframe-v2.html in a browser
3. Check `docs/07-decisions.md` for anything locked since last session
4. Run `git log --oneline -10` to see what was last done
5. Run `uv run pytest -q` to confirm tests still pass
6. Ask "what's the goal of this session?" if not obvious from context

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
Decision: Phase 1 (data) must be complete before Phase 2 (factors). Phase 2 must be complete before Phase 3 (synthesis). Never mix layers.
Rationale: Data failures are impossible to debug in factor code. Factor failures are impossible to debug in synthesis code. Strict sequencing = faster debugging.
