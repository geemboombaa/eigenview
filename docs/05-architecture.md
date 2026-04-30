# 05 — Architecture

## High-level flow

```
         ┌──────────────────────────────────────────────────────┐
         │                  Scheduler (daily)                   │
         │            Windows Task Scheduler → CLI              │
         └──────────────────────────┬───────────────────────────┘
                                    ▼
┌────────────────────────────────────────────────────────────────┐
│                       Data Layer (fetch + cache)               │
│  ─────────────────────────────────────────────────────────     │
│  yfinance  │  Alpha Vantage  │  Finnhub  │  EDGAR  │  OptStrat │
└────────────┬───────────────────────────────────────────────────┘
             ▼
┌────────────────────────────────────────────────────────────────┐
│                       Factor Modules (parallel)                │
│   technical │ gex │ flow │ dormant │ sentiment                 │
│   each → FactorResult                                          │
└────────────┬───────────────────────────────────────────────────┘
             ▼
┌────────────────────────────────────────────────────────────────┐
│                         Synthesis Engine                       │
│   Gate check (TA + GEX required, 2+ of remaining 3)            │
│   → Conviction scoring → Ranking → Top 3–5                     │
└────────────┬───────────────────────────────────────────────────┘
             ▼
┌────────────────────────────────────────────────────────────────┐
│                          LLM Layer                             │
│   Thesis generator · Structure suggester · Chat responder      │
└────────────┬───────────────────────────────────────────────────┘
             ▼
┌────────────────────────────────────────────────────────────────┐
│                     Storage (SQLite local)                     │
│   picks · factors · news · dormant_bets · closed_picks         │
└────────────┬───────────────────────────────────────────────────┘
             ▼
┌────────────────────────────────────────────────────────────────┐
│              FastAPI server → Vanilla JS dashboard             │
│              Module framework + 5 preset templates             │
└────────────────────────────────────────────────────────────────┘
```

## Tech stack summary

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Ecosystem for finance + ML |
| Pkg mgr | uv | Fastest, modern, Claude Code has it built-in |
| Framework | FastAPI | Lightweight, async, auto docs |
| Frontend | Vanilla HTML/JS/CSS | No build toolchain, module architecture simple |
| Charting | TradingView Lightweight Charts | Free, pro-grade candles, overlays work well |
| Storage | SQLite | Zero-config, upgrade to Postgres if deployed |
| Data | yfinance + AV + Finnhub | Free tier viable for MVP |
| ML | scikit-learn, transformers | Standard; FinBERT for sentiment direction |
| LLM | Anthropic Claude API | Already in use via Claude Code |
| Scheduling | Windows Task Scheduler | Native, no infra |

## API surface (FastAPI endpoints)

```
GET  /api/market/context               → market regime
GET  /api/categories/counts            → counts per category
GET  /api/picks?category=<cat>         → ranked picks list
GET  /api/pick/{ticker}                → full pick detail
GET  /api/pick/{ticker}/factors        → factor results
GET  /api/pick/{ticker}/dormant        → dormant bet detail
GET  /api/pick/{ticker}/news           → filtered news + novelty
GET  /api/pick/{ticker}/structure      → suggested options structure
GET  /api/pick/{ticker}/history        → historical hit rates
GET  /api/pick/{ticker}/related        → related setups
GET  /api/chart/{ticker}?tf=<tf>       → OHLCV for chart
GET  /api/picks/closed                 → closed picks archive
POST /api/alerts                       → create alert
GET  /api/search?q=<query>             → search ticker/factor
POST /api/chat                         → chat (SSE stream)
GET  /api/layouts                      → user's saved layouts
POST /api/layouts                      → save layout
```

## Daily run sequence

1. **T-30min before market open** (or whatever schedule locks):
   - Fetch universe of ~200 tickers
   - Parallel: fetch chains, prices, news for all
   - Compute factors per ticker (parallelized)
   - Run synthesis gate → ranked top 5
   - LLM thesis + structure for each qualifying pick
   - Write to SQLite
2. Dashboard reads from SQLite on load, no live compute unless user forces refresh
3. During market: chat + alerts + intraday refresh (optional, v2)

## Caching strategy

- Prices: 15-min cache, overnight refresh
- Chains: refresh on each daily run, cache intraday
- News: refresh every 4 hours during market hours
- Historical chain data (dormant-bet radar): write-once, never refresh
- LLM responses: cache thesis per pick-per-day (regeneration is expensive)

## Security

- API keys in `.env` only, never committed
- No external access in v1 — FastAPI binds to `127.0.0.1` only
- SQLite DB stays local
- If ever deployed: auth + HTTPS + per-user isolation required before that happens
