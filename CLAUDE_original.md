# EigenView — Project Instructions for Claude Code

You are the build agent for **EigenView**, a curated daily options-idea dashboard for US liquid-options stocks. This file is your north star. Read it on every fresh session. Keep it updated as decisions lock.

## What EigenView is

A single-page dashboard that produces **3–5 ranked options trade ideas per day** by fusing 5 factors that no existing product combines:
1. Technical Analysis (trend + momentum + volatility state + levels + ML pattern classification)
2. GEX / Dealer positioning (regime + call/put walls + gamma flip)
3. Options flow quality (fresh OI, aggressive side, premium, skew shift)
4. **Dormant-bet radar** — differentiator, ML classifier that flags large long-dated positions activating
5. Catalyst + Novelty sentiment — LLM-embedding novelty vs. ticker baseline

Hard gate for a pick: **TA + GEX must fire + at least 2 of {flow, dormant, catalyst/novelty} must align.** Everything else is watchlist.

## What it is NOT

- Not a scanner with filters
- Not a data dump of raw flow
- Not a backtesting platform (v1)
- Not a broker integration (v1)
- Not configurable to the point of overwhelming the user

## User

Single user, solo trader, Windows native. Swing + short-dated US liquid options only.

## Product principles (in order)

1. **Curated over comprehensive.** 5 picks > 50 filtered rows.
2. **Explainability is a feature, not a footnote.** Every pick has a written thesis. AI chat can explain any term, any firing factor, in plain English.
3. **Module-first UI.** Every panel is a self-contained module. UI = composition. 5 preset templates + custom canvas.
4. **TA and GEX are gates, not filters.** If either fails, no pick regardless of other signals.
5. **Novelty, not volume.** Sentiment is weighted by unusualness relative to rolling baseline, not noise count.
6. **Dormant-bet radar is the moat.** No competitor does this. Quality here determines differentiation.

## Tech stack (locked unless user overrides)

- **Language:** Python 3.11+
- **Package manager:** uv (fast, modern)
- **Backend framework:** FastAPI (lightweight, async-ready)
- **Frontend:** Vanilla HTML/JS/CSS, module framework of our own (no React)
- **Charting:** TradingView Lightweight Charts (free, pro-grade)
- **Data layer:** yfinance + openbb + Alpha Vantage (free) + Finnhub (free)
- **Paid bootstrap (optional):** historicaloptiondata.com for dormant-bet backfill
- **ML:** scikit-learn for pattern classifier, HuggingFace transformers for FinBERT + embeddings
- **Scheduler:** Windows Task Scheduler (local)
- **Storage:** SQLite (local, single file), upgrade path to Postgres
- **Version control:** Git (local), GitHub optional

## Non-negotiables

- Never use localStorage/sessionStorage in any frontend artifact — use in-memory or backend state.
- All secrets in `.env`, never committed.
- All factor modules are independently testable — each has its own `test_<factor>.py`.
- All LLM calls are logged with input/output for reproducibility.
- Hot-path functions (factor scoring) must have sub-second execution per ticker on a 200-ticker universe.

## Repo layout (initialize this)

```
eigenview/
├── CLAUDE.md                    # this file
├── README.md
├── pyproject.toml               # uv-managed
├── .env.example
├── .gitignore
├── docs/                        # from handoff — read ALL of these
│   ├── 01-vision.md             # what & why & differentiators
│   ├── 02-modules.md            # 21 modules, data contracts, sizes
│   ├── 03-factors.md            # 5 factors with math + data sources
│   ├── 04-templates.md          # 5 preset layouts as JSON
│   ├── 05-architecture.md       # tech stack, API, data flow
│   ├── 06-build-plan.md         # 10 phases with acceptance criteria
│   ├── 07-decisions.md          # locked decisions log
│   ├── 08-open-questions.md     # resolved (kept for history)
│   ├── 09-design-system.md      # colors, type, spacing, components
│   ├── 10-ux-patterns.md        # interactions, flows, keyboard
│   ├── 11-ai-spec.md            # where AI shows up, prompts, tests
│   ├── 12-engineering-standards.md  # code, test, git standards
│   └── wireframes/              # VISUAL SOURCE OF TRUTH
│       ├── wireframe-v1.html    # initial card-based design
│       └── wireframe-v2.html    # locked design — base UI on this
├── src/
│   └── eigenview/
│       ├── data/                # fetchers (prices, chains, news)
│       ├── factors/             # one module per factor
│       │   ├── technical.py
│       │   ├── gex.py
│       │   ├── flow.py
│       │   ├── dormant.py
│       │   └── sentiment.py
│       ├── synthesis/           # gate logic + ranker
│       ├── llm/                 # thesis generation, chat, novelty scoring
│       ├── api/                 # FastAPI endpoints
│       ├── scheduler/           # daily run orchestrator
│       └── cli.py
├── web/
│   ├── index.html
│   ├── modules/                 # one JS/CSS pair per module
│   └── templates/               # preset layouts
├── tests/
├── data/                        # sqlite, cached chains, etc (gitignored)
└── scripts/                     # one-off maintenance
```

## Workflow

- **One factor = one module = one PR.** Don't mix.
- **Tests before scoring logic.** Every factor module ships with a test file that locks its contract.
- **CLAUDE.md gets updated** whenever a non-obvious decision locks. Don't let it drift.
- **Small commits** with context-aware messages. Prefer more PRs over bigger ones.
- **Ask the user** before: changing tech stack choices, adding paid data sources, choosing between two non-trivial approaches (e.g. ML model choices).

## Build order (stick to this)

See `docs/06-build-plan.md`. Current phase: **Phase 0 — setup.**

## Open questions (blocking)

See `docs/08-open-questions.md`. Do not advance past Phase 1 without answers.

## Session start checklist

1. Read this file (CLAUDE.md).
2. On **first session ever:** read all 12 docs in order (01 through 12). They are the source of truth for everything.
3. **Open `docs/wireframes/wireframe-v2.html` in a browser** before doing any UI work — it is the visual source of truth.
4. Check `docs/07-decisions.md` for anything locked since last session.
5. Check git log for what was last done.
6. Ask "what's the goal of this session?" if not obvious.

## Where to look when…

| Question | File |
|---|---|
| What does this product do, and why? | `docs/01-vision.md` |
| What modules exist, with what data contracts? | `docs/02-modules.md` |
| How is factor X computed? | `docs/03-factors.md` |
| What does template X look like? | `docs/04-templates.md` + wireframes |
| What's the tech stack / API surface? | `docs/05-architecture.md` |
| What's the build order? | `docs/06-build-plan.md` |
| Why was decision X made? | `docs/07-decisions.md` |
| What color is X? What font? What spacing? | `docs/09-design-system.md` |
| How does the user interact with X? | `docs/10-ux-patterns.md` |
| Where does AI show up? Prompt for X? | `docs/11-ai-spec.md` |
| What's the test/code/git standard? | `docs/12-engineering-standards.md` |
| What does X actually look like? | `docs/wireframes/wireframe-v2.html` |

## Critical rules — never break these

1. **Wireframe v2 is the visual source of truth.** When designing UI, match the wireframe. Don't improvise visual decisions.
2. **Use design tokens from `docs/09-design-system.md`.** Never hardcode colors, type, or spacing.
3. **TA + GEX are hard gates.** No pick qualifies without both firing.
4. **Curated, not configurable.** Default templates have no filter panels. Filtering happens via chat NL commands or category nav.
5. **Every factor module is independently testable.** Tests exist before implementation is "done".
6. **Update CLAUDE.md and `docs/07-decisions.md`** whenever a non-obvious decision locks. Drift is a bug.
7. **AI failures degrade gracefully.** Never block a pick because the LLM is down — see `docs/11-ai-spec.md` fail-open section.
