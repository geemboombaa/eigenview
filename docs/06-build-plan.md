# 06 — Build Plan

10 sessions in Claude Code. Total estimated active build time: 15–20 hours spread over ~2 weeks.

Each phase must pass its acceptance criteria before advancing.

---

## Phase 0 — Setup (0.5 hr, one-time)

**Goal:** Claude Code installed, repo initialized, this handoff docs folder committed, first commit green.

**Tasks:**
- Install Claude Code Desktop (Windows native)
- Install Git for Windows, Node.js 18+, Python 3.11+
- Install uv: `irm https://astral.sh/uv/install.ps1 | iex`
- Create repo, copy `CLAUDE.md` + `docs/` into root
- Create `pyproject.toml`, `.env.example`, `.gitignore`
- First commit: "initial scaffold + handoff docs"

**Acceptance:** `claude` command opens in repo folder, CLAUDE.md is read on session start, `uv run python --version` works.

---

## Phase 1 — Data Layer (1 session, ~2 hrs)

**Goal:** working fetchers for prices, chains, news, catalog. Cached to SQLite.

**Modules to build:**
- `src/eigenview/data/prices.py` — yfinance wrapper, OHLCV with caching
- `src/eigenview/data/chains.py` — options chains with greeks
- `src/eigenview/data/news.py` — Alpha Vantage + Finnhub news
- `src/eigenview/data/calendar.py` — earnings, macro, FDA events
- `src/eigenview/data/storage.py` — SQLite schema + write/read helpers

**Acceptance:** CLI command `eigenview fetch <ticker>` pulls all data and writes to SQLite. Tests pass. <5s for single ticker.

---

## Phase 2 — Factor Modules (2 sessions, ~3 hrs)

### Session 2a — TA + GEX + Flow
- `factors/technical.py` — trend, momentum, vol, levels, pattern rule-based v1
- `factors/gex.py` — compute GEX from chain, walls, flip
- `factors/flow.py` — V/OI, premium, aggressive side detection

### Session 2b — Dormant + Sentiment
- `factors/dormant.py` — rule-based activation scorer (MVP before ML)
- `factors/sentiment.py` — catalyst lookup + novelty via embeddings + Claude filter

**Acceptance:** each factor module has its own test file, returns `FactorResult`. Running all 5 on a single ticker takes <2s.

---

## Phase 3 — Synthesis Engine (1 session, ~1 hr)

**Goal:** gate logic + ranker producing top 3–5 picks.

- `synthesis/gate.py` — qualify_pick logic
- `synthesis/ranker.py` — conviction + sort
- CLI: `eigenview daily-scan` runs end-to-end on universe, writes picks to DB

**Acceptance:** daily scan on 200-ticker universe completes in <5 min, produces coherent top 5.

---

## Phase 4 — Dashboard Shell (1 session, ~2 hrs)

**Goal:** FastAPI serves data, first template ("Standard") renders.

- `api/` — all endpoints from architecture doc
- `web/index.html` — module framework (canvas + grid + module loader)
- `web/modules/` — first 3 modules wired: `market-context`, `pick-cards`, `ai-chat` (stub)
- Template loader reads JSON layout config

**Acceptance:** `eigenview serve` starts local server, dashboard renders the Standard template with real data from Phase 3.

---

## Phase 5 — Module Library (2 sessions, ~4 hrs)

**Goal:** all 21 modules implemented.

### Session 5a — Feed + Detail modules
- `pick-list`, `pick-table`, `mini-chart-grid`
- `price-chart` with TradingView Lightweight Charts + GEX overlay
- `factor-strip`, `dormant-bet-panel`, `news-sentiment`, `suggested-structure`
- `history-hit-rate`, `related-setups`, `alert-setup`

### Session 5b — Workflow modules
- `closed-picks`, `journal`, `settings`
- `global-search`, `theme-toggle`, `category-nav`, `ask-about-this`

**Acceptance:** every module renders at every supported size. No module has external dependencies beyond its declared data contract.

---

## Phase 6 — Templates + Customizer (1 session, ~2 hrs)

**Goal:** 5 presets + drag-drop canvas.

- Implement Minimal, Standard, Pro Trader, Research, Focus layouts
- Template switcher in top bar
- Custom canvas with drag/resize/delete
- Save/load layouts to user settings

**Acceptance:** all 5 templates render. User can switch, customize, save, reload.

---

## Phase 7 — AI Chat + Explainability (1 session, ~2 hrs)

**Goal:** context-aware chat dock fully functional.

- Claude API integration with streaming (SSE)
- Context passing: selected pick, current template, recent navigation
- Suggested-prompt chips (context-sensitive)
- Natural-language commands: "show dormant firings", "filter earnings this week"
- Thesis regeneration on user feedback

**Acceptance:** user can ask "why this pick?" and get a coherent answer that references the actual factors firing. Natural-language filter commands work.

---

## Phase 8 — Scheduler + Alerts (1 session, ~1.5 hrs)

**Goal:** fully automated daily runs + alerts delivered.

- Windows Task Scheduler XML install
- Startup script: `eigenview daily-scan && eigenview notify`
- Alerts engine: price triggers, new pick notifications
- Notification channel: desktop toast (v1), optional email/Telegram (v2)

**Acceptance:** daily scan runs automatically at configured time. User gets notification when new picks land. One week of autonomous runs with no errors.

---

## Cross-cutting requirements (every phase)

- **Tests:** every factor and synthesis function has a unit test. Don't advance without green tests.
- **Logging:** every LLM call logs input/output/cost. Factor results logged per ticker.
- **Docs:** docstrings on every public function. Keep `docs/07-decisions.md` up to date.
- **Git:** atomic commits per logical change. Push at end of each session.

---

## Out of scope for v1 (future phases)

- Backtest lab
- Broker integration (paper/live trading)
- Real-time streaming (upgrade beyond 15-min delay)
- Multi-user / deployed web version
- Mobile app
- Dark pool data (requires paid feed)
- Crypto / futures
