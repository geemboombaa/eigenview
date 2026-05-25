# EigenView — Claude Code Instructions
# (EigenView + PULSE merged · April 2026)

Read every session. Update when decisions lock.

---

## PRODUCT

Morning dashboard → short ranked list of instruments to act on today. Each pick: score, setup type, entry zone, stop, plain-English thesis. Macro regime gate runs first — if RED, no long picks. Not a scanner, not a data dump. Local Windows only (v1).

**NOT in v1:** backtesting, broker integration, real-time ticks, multi-user, filter panels, configurability.

---

## SIGNAL STACK

**Gate 0 — Macro Regime** (PULSE): SPX GEX regime, VIX M1/M2 term structure, DIX >43%=bullish, SPX breadth >50% above 50dma, retail capitulation bonus. Score 0–10. GREEN ≥7 / YELLOW 4–6 / RED ≤3 (no longs).

**Gate 1 — TA** (hard gate): EMA stack, ADX, RSI, ATR, BB, volume profile, swing levels. Pattern confidence >0.6 AND weekly trend not contradicting daily.

**Gate 2 — Per-Stock GEX** (hard gate): net dealer gamma, gamma flip, call wall, put wall, regime flag.

**Factor 1 — Flow:** V/OI ≥3 + premium >$500K + aggressive side + dark pool cluster (3+ prints in ±0.5% band).

**Factor 2 — Dormant-Bet Radar** (THE moat): large long-dated positions (30–180 days old, ≥$500K, ≥90 DTE) scored for activation near catalyst. V1: rule-based. V2: sklearn GBT.

**Factor 3 — Sentiment:** novelty embedding z-score, FinBERT direction, LLM MATERIAL/NOISE filter, catalyst proximity.

**Factor 4 — Macro Timing** (conviction bonus, not gate): VIX backwardation score, DIX trend, retail capitulation.

**Futures** (optional): ES/NQ via GEX + CTA flip. CL/GC via OVX/GVZ + COT + curve shape.

**GATE LOGIC:** Qualifies when Gate 0+1+2 all fire AND ≥2 of {Flow, Dormant, Sentiment} fire. Conviction 1–5. Rank by conviction DESC → dormant bonus → IV rank. Output top 3–10/day.

---

## MVP SCOPE (locked 2026-04-29)

1. Macro regime gate → GREEN/YELLOW/RED every morning
2. 3–5 picks/day with TA + GEX + flow OR sentiment
3. Score + setup + entry zone + stop per pick
4. LLM thesis (2–3 sentences) per pick
5. Wireframe v2 wired to real data
6. AI chat (SSE, grounded to pick data)

Deferred: dormant-bet radar (needs 30d chain history — store from Day 1), novelty embeddings, futures, template switcher, module framework, alerts, archive.

---

## PHASES

### Phase 0 — Done
Scaffold exists. Wireframe at `docs/wireframes/wireframe-v2.html` = visual source of truth.

### Phase 1 — Data Layer
Goal: clean data in SQLite. Acceptance: `eigenview fetch NVDA` writes all tables, tests pass.

- `data/prices.py` — yfinance OHLCV daily+1h, SQLite cache (15-min TTL intraday, overnight daily)
- `data/chains.py` — yfinance options chain, py_vollib greeks (delta/gamma), IV rank
- `data/news.py` — Alpha Vantage + Finnhub, deduped by URL hash, exponential backoff
- `data/calendar.py` — yfinance earnings, Finnhub macro calendar
- `data/macro.py` — SqueezeMetrics DIX/GEX scrape, VIXCentral term structure, CFTC COT download
- `data/storage.py` — SQLite auto-create. Tables: prices, chains, news, catalysts, macro_daily, cot_weekly, picks, dormant_bets, signal_triggers, signal_bench. Helpers: upsert_*/get_*/write_pick().
- `cli.py` — `eigenview fetch <ticker>`, `eigenview fetch-macro`, `eigenview status`
- `tests/data/` — one real-API test per module. NO cassettes, NO mocks.

API keys: see `.env.example`. Keys needed: ALPHA_VANTAGE_KEY, FINNHUB_KEY (Phase 1), ANTHROPIC_API_KEY (Phase 4). Free (no key): yfinance, SqueezeMetrics, VIXCentral, CFTC.

### Phase 2 — Factor Modules (one module = one file = one PR)

- `factors/macro_regime.py` — Gate 0. Input: macro_daily row. Output: FactorResult(score 0–10, regime, narrative).
- `factors/technical.py` — Gate 1. Input: 90d daily + 5d 1h prices. Output: FactorResult(pattern, confidence, trend_direction, key_levels).
- `factors/gex.py` — Gate 2. Input: chains dict. Output: FactorResult(regime, gamma_flip, call_wall, put_wall, net_gex).
- `factors/flow.py` — Factor 1. Input: chains + FINRA dark pool. Output: FactorResult(largest_sweep, dark_pool_cluster_price, flow_direction).
- `factors/dormant.py` — Factor 2. Input: dormant_bets table + current chains + catalysts. Output: FactorResult(activation_probability, original_bet, narrative). Meaningful only after 30d of chain data.
- `factors/sentiment.py` — Factor 3. Input: news + catalysts. AI: MATERIAL/NOISE (Claude API) + FinBERT + MiniLM novelty. Output: FactorResult(novelty_z, sentiment_direction, catalyst_proximity, top_headline).

### Phase 3 — Synthesis
- `synthesis/gate.py` — qualify_pick(), conviction() 1–5
- `synthesis/ranker.py` — rank by conviction → dormant bonus → IV rank
- `cli.py` add: `eigenview daily-scan [--universe S&P500|test5]` → picks to DB in <30s

### Phase 4 — Wire UI (MVP monolith — NO module framework yet)
- `api/` endpoints: GET /api/market/regime, /api/picks, /api/pick/{ticker}, /api/pick/{ticker}/factors, /api/chart/{ticker}, POST /api/chat (SSE). Full contracts: `docs/05-architecture.md`.
- `web/index.html`: wire regime/picks/pick-detail/chat/chart to endpoints. GEX overlay via TradingView createPriceLine().
- MVP done: real picks every morning, factor data on click, AI chat answers "why this pick?", theme toggle works.

### Modular Extraction (after MVP validated)
Extract JS modules in order: pick-cards → market-context → ai-chat → price-chart → factor-strip → template switcher → module framework → presets → custom canvas. NOT Phase 1 work.

---

## TECH STACK (locked)

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Pkg mgr | uv |
| Framework | FastAPI (async, SSE) |
| Frontend | Vanilla HTML/JS/CSS |
| Charting | TradingView Lightweight Charts |
| Storage | SQLite + aiosqlite |
| Data | yfinance, Alpha Vantage free, Finnhub free, SqueezeMetrics scrape, VIXCentral scrape, CFTC public |
| ML | scikit-learn, sentence-transformers MiniLM (local) |
| LLM | claude-sonnet-4-6 |
| Scheduling | Windows Task Scheduler |

---

## REPO LAYOUT

```
eigenview/
├── CLAUDE.md
├── pyproject.toml / .env.example
├── docs/                    ← 01–12 handoff docs; wireframes/wireframe-v2.html = VISUAL SOURCE OF TRUTH
├── src/eigenview/
│   ├── data/                ← prices, chains, news, calendar, macro, storage
│   ├── factors/             ← macro_regime, technical, gex, flow, dormant, sentiment
│   ├── synthesis/           ← gate, ranker
│   ├── api/                 ← routes/
│   ├── llm/                 ← thesis, chat, prompts/
│   └── cli.py
├── web/index.html           ← wireframe-v2 wired to API
├── tests/                   ← data/, factors/, synthesis/, fixtures/ (real DB only)
└── data/                    ← SQLite DB (gitignored)
```

---

## DEPENDENCIES + ENV

Deps: see `pyproject.toml`. Core: yfinance, pandas, pandas-ta, py_vollib, requests, beautifulsoup4, anthropic, fastapi, uvicorn, pydantic-settings, structlog, tenacity, typer, pytest, pytest-asyncio, httpx. ML extras: scikit-learn, sentence-transformers, transformers, torch. **pytest-vcr BANNED.**

Env: see `.env.example`. Key vars: DB_PATH, LOG_LEVEL, UNIVERSE (SP500+NDX or test5), DAILY_SCAN_HOUR (8), MAX_PICKS (10), MACRO_REGIME_GREEN_THRESHOLD (7), MACRO_REGIME_RED_THRESHOLD (3).

---

## SESSION START

1. Read this file
2. First session: read `docs/` 01–12, open wireframe-v2.html in browser
3. Check `docs/07-decisions.md` for locked decisions
4. `git log --oneline -10`
5. `uv run pytest -q`
6. Ask goal if not obvious

**On feature branches — run first:** `gh pr list --head $(git branch --show-current) --state open --json labels --jq '.[0].labels[].name'`
- `status:ci-failing` → read BOSS_FIX_REQUEST → fix → commit → push → wait CI green
- `status:needs-human-debug` → tell user, stop
- `status:yellow-flags-pending` → note, remind at step 27

---

## 29-STEP ENGINEERING PROCESS

Full reference: `docs/engineering-process.html` (v1.1). No deviations.

**Tiers:** `feature/` = full 29 steps. `fix/` = lightweight (skip 5–14). Both need branch + PR + human merge.

**Tracking:** Step 5 → copy `.boss/PROCESS-TEMPLATE.md` → `.boss/CURRENT-STEP.md`. Update after every step.

**Phase 0 — Research (1–4)**
1. User describes need
2. Claude reads codebase + docs + git log — NO code
3. Claude writes proposal: what/how/out-of-scope
4. **[MANUAL GATE]** User approves

**Phase 1 — Lock Requirements (5–8)**
5. Claude writes `spec.md` + `design.md` (GIVEN/THEN ACs) → `.boss/`
6. `pre-build-gate.ps1` — blocks `src/`+`tests/` edits unless on feature branch + open PR + no `gate:awaiting-step21`
7. Claude creates GitHub issue with GIVEN/THEN ACs + AC1/AC2 labels
8. Claude opens draft PR (`gh pr create --draft`)

**Phase 2 — Test Stubs Red (9–12)**
9. Test stubs only — names must contain AC1/AC2/REQ — no implementation
10. `git commit` → pre-commit (RED): stubs must FAIL; passing stubs = blocked
11. `stop-gate.ps1`: dirty `src/` check (instant) → then test suite if clean
12. `auto-push.ps1` pushes

**Phase 3 — CI Audit (13–19)**
13. GitHub Actions `ac-audit.yml` triggers
14. CI: AST scan for AC/REQ in test names + trivial test detection
15. CI: fetch issue body, fail if no GIVEN/THEN/AC labels
16. CI: Claude API audits spec + ACs + design + stubs (zero project context)
17. CI: posts audit as PR comment, uploads report artifacts
18. CI: sets `phase:red` + `gate:awaiting-step21` labels (blocks src/ edits)
19. **[MANUAL GATE]** User reads CI audit, approves or returns with gaps

**Phase 4 — Design Review (20–21)**
20. Claude writes `.boss/design-review.md` — A-Z implementation checklist, gaps
21. **[MANUAL GATE]** User removes `gate:awaiting-step21` label (GitHub UI). If returned: back to step 5.

**Phase 5 — Implementation (22–29)**
22. Claude implements `src/` — pre-build-gate confirms: open PR + no gate label
23. `git commit` → pre-commit (GREEN): all tests pass, coverage ≥75%
24. `stop-gate.ps1`: dirty src/ check → tests if clean
25. `auto-push.ps1` → GitHub Actions `test.yml`: pytest + coverage + Playwright
26. `ac-audit.yml` post-implementation audit
27. **[MANUAL GATE]** User reviews: green CI + clean audit + AC coverage complete
28. **[MANUAL GATE]** User merges PR (≥1 approval + CI green required)
29. CI re-runs on master

**Process rules:**
- Never `git commit --no-verify`
- Never edit `src/` on master
- Never remove `gate:awaiting-step21` — only human at step 21
- `fix/` only for confirmed bugs/typos/config — NOT new behavior
- Enforcement tests → `tests/integration/enforcement/` (excluded from default pytest)
- Implementation complete only when `tests/integration/test_<feature>.py` AND `tests/ui/` both added
- All integration tests hit LIVE real data — no synthetic fixtures, no cassettes
- Auto-fix RED: max 3 attempts; after 3 → `status:needs-human-debug`, Claude stops
- YELLOW flags (`@pytest.mark.data_dependent`): Claude does NOT fix, explains to human at step 27

---

## CRITICAL RULES

1. Wireframe v2 = visual source of truth. Match it. Don't redesign.
2. Gate 0 (macro) always runs first. RED = no longs regardless of individual signals.
3. TA + GEX = hard gates. Both must fire.
4. One module = one file = one PR. No mixing.
5. Tests before scoring logic. Every factor ships with test file.
6. Never display AI-generated options math without independent R:R validation.
7. Dormant-bet chain data accumulates Day 1.
8. Update CLAUDE.md + `docs/07-decisions.md` when decisions lock.
9. AI failures degrade gracefully — never block picks.
10. Phase sequence mandatory: Data → Factors → Synthesis → API+UI → AI.

---

## WHERE TO LOOK

| Question | File |
|---|---|
| Vision + differentiators | docs/01-vision.md |
| UI modules + data contracts | docs/02-modules.md |
| Factor math + sources | docs/03-factors.md |
| Tech stack + API surface | docs/05-architecture.md |
| Locked decisions | docs/07-decisions.md |
| Design tokens | docs/09-design-system.md |
| UX patterns + keyboard nav | docs/10-ux-patterns.md |
| AI prompts + costs | docs/11-ai-spec.md |
| Code standards + test patterns | docs/12-engineering-standards.md |
| Visual source of truth | docs/wireframes/wireframe-v2.html |

---

## DECISIONS LOG

**2026-04-29 · PULSE merged:** Gate 0 added. Futures as optional module. +12h to build plan. New files: data/macro.py, factors/macro_regime.py.

**2026-04-29 · MVP locked:** macro regime + 3-5 picks + LLM thesis + wireframe v2 + AI chat. All else deferred.

**2026-04-29 · Monolith first:** Build MVP wired monolith. Module framework only after MVP validated.

**2026-04-29 · Thresholds:** DIX bullish = 43% (not 45%). Breadth healthy = 50% above 50dma (not 55%). Phase sequence mandatory.

---

## TA MODULE — ARCHITECTURE (merged 2026-05-04)

### 21-Setup Taxonomy

| Category | Weekly required (long) | Noise filter |
|---|---|---|
| Trend Continuation | Bullish (EMA8>21, RSI 45–65, ADX >15) | Volume declines on pullback |
| Breakout | Not bearish | Volume confirms expansion |
| Reversal | Extended (RSI >65 bearish rev / <35 bullish) | Divergence OR structural break required |
| Mean Reversion | Non-trending (ADX <20, flat EMAs) | Not valid if ADX >25 |

**Trend Continuation:** `pullback_in_trend` (RSI@p40, price>EMA21×0.99<EMA50×1.08, vol↓), `pullback_deep` (RSI 32–50, EMA50 touch), `pullback_to_structure` (swing high now support), `flag_continuation` (5–10 bar tight range, squeeze ON), `rally_in_downtrend` (short).

**Breakout:** `breakout`/`breakdown` (swing high/low + vol>1.5×avg), `compression_break`/`_down` (squeeze ON→OFF + vol surge), `base_breakout`/`_down` (20+ bar low-vol contraction), `ema_reclaim`/`_rejection` (EMA50 cross), `bos_bullish`/`_bearish` (smartmoneyconcepts BOS).

**Reversal:** `bullish_reversal`/`bearish_reversal` (RSI divergence + vol spike), `overbought_reversal`/`oversold_bounce`, `failed_breakdown`/`failed_breakout`, `choch_bullish`/`choch_bearish` (smartmoneyconcepts CHoCH).

**Mean Reversion:** `bb_mean_reversion_long`/`_short` (BB edge, ADX <20), `ema200_snap_long`/`_short` (>15% deviation).

**Total: 21 setups.**

### Libraries

| Need | Library |
|---|---|
| All indicators | `pandas_ta` |
| Compression | `pandas_ta.squeeze_pro()` |
| Swing levels | `scipy.signal.argrelextrema` (swingtrend not on PyPI) |
| BOS/CHoCH | `smartmoneyconcepts` |
| SuperTrend | `pandas_ta.supertrend()` |
| Chandelier | ~30-line Pine port |
| RSI divergence | Custom |

### Stop / Target / R:R

**Stop by category:**
- Trend Continuation: below pullback swing low / above rally swing high
- Breakout: below breakout level / above breakdown level
- Reversal: below/above reversal candle wick
- Mean Reversion: entry ±1.5×ATR14

ATR floor: long `max(swing_low×0.995, entry−atr)`, short `min(swing_high×1.005, entry+atr×1.25)`. Implementation in `technical.py`.

**Target:** Trend Cont → prior swing high; Breakout → `level + (level − base_low)`; Reversal → 50%/61.8% fib; Mean Rev → EMA20 or BB midline.

**R:R minimum ≥ 2.0.** Below 2.0 = conviction downgrade (not eliminated).

**Trailing stops (display-only):** SuperTrend primary `(length=7, mult=3.0)`, Chandelier secondary `highest(22)−3×ATR(22)`, EMA21/EMA50 trail. Activates after ≥1 ATR in favor.

### Rolling Percentile Thresholds

Replaces all hardcoded literals in `technical.py`. Per-ticker 90-day rolling: rsi_oversold=p20, rsi_overbought=p80, adx_trending=p65, vol_surge=p70, vol_light=p35, atr_contracted=p30. ADX absolute floor 15 for pullback gate.

### Weekly Classifier

Resample daily → weekly (W-FRI). Compute EMA10, EMA20, ADX14, RSI14. States: `BULLISH | BULLISH_EXTENDED | NEUTRAL | BEARISH_WEAK | BEARISH_STRONG`.

### MTF Matrix

| Weekly state | Valid long | Valid short |
|---|---|---|
| Bullish (EMA8>21, RSI 45–65, ADX >15) | Trend Continuation, Breakout | None |
| Bullish extended (RSI >70 OR ADX >35) | Bearish Reversal only | Bearish Reversal |
| Neutral (ADX <20, flat EMAs) | Breakout, Mean Reversion | Breakdown, Mean Reversion |
| Bearish weak (EMA8<21, RSI 40–55) | Mean Reversion, Failed Breakdown | Trend Cont (short), Breakdown |
| Bearish strong (EMA8<21, RSI <45, ADX >20) | Bullish Reversal only | Trend Cont (short), Breakdown |
| Bearish extended (RSI <30 OR ADX >35) | Bullish Reversal only | None |

### Signal Persistence

`signal_triggers` table (in `storage.py`): ticker, scan_date, setup_type, direction, entry_low/high, stop, target, rr_ratio, confidence, fired_at, valid_until (scan_date +5 trading days). `signal_bench` adds forward_return_5d/20d + indicator_state JSON for future GBT training. Freshness: Fresh <2h / Valid 2–8h / Stale >8h.

### Chart Toggles (localStorage per ticker)

EMA21 ON, EMA50 ON, EMA200 ON, BB OFF, Signals ON, SuperTrend OFF.

### LLM in TA

LLM is NOT a pattern classifier — CNN/LSTM, LLM confirmation, chart vision all ruled out (2026 benchmarks: coin-flip direction, 0.46% pattern naming). LLM scope: thesis generation, MATERIAL/NOISE filter, chat only.

### Open Questions

- Q1: Mean reversion setups in v1?
- Q2: Trail — display-only vs executable?
- Q3: R:R threshold 2.0 fixed or configurable?
- Q4: valid_until — flat 5d or extend if still in zone?
- Q5: BOS replace or supplement breakout?
- Q6: scipy.argrelextrema as swingtrend replacement — lock?

### TA Decisions (2026-05-04)

- Per-stock GEX as hard gate: no OSS equivalent exists
- Claude vision ruled out: 57% direction, 0.46% pattern accuracy
- 21-setup taxonomy approved (draft)
- SuperTrend primary trail, Chandelier secondary
- scipy.argrelextrema replaces swingtrend (not on PyPI)
- Rolling p40 RSI replaces hardcoded 38–57 for pullback
- pullback_in_trend: 15/15 tests passing (2.07s)
