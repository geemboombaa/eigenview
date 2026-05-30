# SESSION HANDOFF — 2026-05-29 (macro rebuild + sentiment)

Paste the "PROMPT FOR NEXT SESSION" block below into a fresh session.

## State
- Branch: `fix/macro-sources` (8 commits ahead of master). **PR #135 open.** All pushed.
- Tests: 264+ green. Semgrep stub-audit clean. ML deps installed (torch 2.11, transformers 5.7, sentence-transformers, vaderSentiment, finnhub).
- Server: `uv run uvicorn eigenview.api.main:app --port 8000` → http://localhost:8000/dashboard/
- Today (2026-05-29): macro GREEN 10/10 (all real). Full 506-scan runs clean. **DAILY = 0 picks** (sentiment/flow too sparse to clear ≥2-soft gate).

## DONE this session (committed)
1. Macro sources rebuilt — VIX (yfinance ^VIX/^VIX3M), DIX (FINRA daily file, dollar-weighted), GEX (native Σ net_gex over S&P500 chains), COT (CFTC Socrata). All free, no Databento. `data/macro.py`.
2. Honest NO DATA regime + de-hardcoded thresholds → `config.py`. `factors/macro_regime.py`, `api/routes/market.py`.
3. DAILY trickle-in (picks write per scan chunk). `synthesis/scanner.py`.
4. UI glam layer (`web/dashboard/glam.css` + `glam.js`, 6 effects, revertable — see docs/16).
5. Favorite ★ tap-target fix (`glass.css`).
6. **Sentiment factor → FinBERT-tone** (`factors/sentiment_model.py` + rewritten `factors/sentiment.py`). Benchmarked 3 models (`scripts/bench_sentiment.py`). VADER fallback. Validated on real news (NVDA 299 articles → net +0.40 bullish). Real-model test passes.
7. Docs: 14 (data sources), 15 (sentiment+OSS), 16 (UI changelog), 17 (thresholds-to-validate), decisions log.

## CRITICAL HONESTY — unvalidated thresholds (user flagged as "made up")
These are **arbitrary guesses, no data/backtest**:
- `sentiment_fire_strength = 0.45` — set this session, no calibration. Today nothing fires (NVDA 0.40 / AAPL 0.38 / TSLA 0.16 all < 0.45).
- `min_rr_ratio = 3.0` — user CONFIRMED keep 3.0 (was conflicting with CLAUDE.md TA spec's 2.0 — update spec to 3.0).
- macro weights 3/2/3/2, conviction tiers, entry/stop fracs — all heuristic. See docs/17.
- Proper fix later: calibrate against `signal_bench`/`forward_returns` (tables exist, unused).

## NEXT STEPS (priority order — user wants end-to-end pipeline + real picks on dashboard)
1. **News-refresh job (decoupled)** — standalone CLI + Windows Task Scheduler, **intraday + pre-market**. Finnhub primary (60/min, bulk ~600 names) + Alpha Vantage for picks subset (free=25/day, throttles — do NOT use AV for bulk). `fetch_news` already exists in `data/news.py`. Goal: keep `news` table fresh so sentiment fires.
2. **Tune `sentiment_fire_strength`** — likely ~0.30 so real bullish/bearish names fire. Decide with user; record reasoning in docs/17. (Or defer to calibration.)
3. **Fresh full 506-scan** (download=false) → confirm sentiment fires + DAILY picks appear (trickle-in live). Browser-verify.
4. **UI: dead-simple "Trade Ticket" main view — MOCKUP APPROVED to build.** Mobile-first cards: ticker, BUY/SELL, call/put strike + SL, R:R ladder (target/entry/stop to scale), conviction glyph. Dense table stays as "Pro/ALL" view. Honest score reps (macro = 4 flags not /10; dorm = "X/7 signals" not %; flow = badge not bar; GEX = label only — gex.py strength 0.1/0.3 is hardcoded, de-hardcode/drop). Build mockup HTML first → approve → wire (per design-first rule).
5. **CLAUDE.md cleanup (user request)** — project `CLAUDE.md` (the CONFLUENCE file) is bloated with old/irrelevant content. User wants the cruft removed (keep only what's current + true). Also set `min_rr` reasoning to 3.0 there. Audit the whole file; cut stale phase-0/build-plan duplication, old open-questions already resolved, anything not reflecting current state.

## WATCH-OUTS
- Sentiment model loads once (~14s) on first `classify()` — blocks event loop once during scan. OK.
- `pyproject.toml` still lists `vcrpy`/`pytest-vcr` (global rule bans cassettes) — pre-existing, flag/remove.
- Windows console = cp1252; keep narratives ASCII (no unicode arrows) to avoid CLI/log crashes.
- `gex.py` GEX *strength* is a hardcoded constant (0.1 long / 0.3 flip) — only the regime label is real. Fix under "honest representations".

---

## PROMPT FOR NEXT SESSION (paste this)
```
Continue EigenView on branch fix/macro-sources (PR #135). Read docs/SESSION-HANDOFF-2026-05-29-macro-sentiment.md, docs/17-thresholds.md, docs/14-data-sources.md first.

Context: macro sources rebuilt + FinBERT-tone sentiment factor built & validated (real news, NVDA net +0.40 bullish). DAILY still 0 because news goes stale and sentiment_fire_strength=0.45 (arbitrary) is too strict.

Priority = get the end-to-end pipeline producing real DAILY picks on the dashboard:
1. Build the decoupled news-refresh job (Finnhub bulk + AV picks, intraday + pre-market) so the news table stays fresh.
2. Tune sentiment_fire_strength (record real reasoning, not a guess) OR start populating signal_bench for calibration.
3. Run a fresh 506-symbol scan (download=false), confirm sentiment fires and picks trickle into DAILY live; browser-verify zero console errors.
4. UI mockup APPROVED: build a real HTML mockup of a dead-simple mobile-first "Trade Ticket" main view (ticker, BUY/SELL, call/put strike+SL, R:R ladder, conviction glyph; dense table stays as Pro/ALL). Use honest score representations (macro=4 flags, dorm=X/7, flow=badge, GEX=label). Get approval, then wire.
5. Clean up project CLAUDE.md — remove old/bloated/resolved content; keep only current truth; set min_rr reasoning to 3.0.

Honesty rules (global CLAUDE.md): no fake data, no stubs, no hardcoded thresholds (config + documented reason + user validation), reuse OSS before building, validate on real data before claiming done. Many current thresholds are unvalidated guesses — treat as such.
```
