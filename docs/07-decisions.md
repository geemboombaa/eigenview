# 07 — Decisions Log

Running log of locked decisions. Format: date · topic · decision · rationale.

Update this file in Claude Code whenever a non-obvious decision locks.

---

## 2026-04-24 · Project vision

**Decision:** Build a curated multi-factor options-idea dashboard (3–5 picks/day) with a dormant-bet radar as the core differentiator.

**Rationale:** Deep research confirmed that while products exist for individual factors (Tradytics, Unusual Whales, SpotGamma, InsiderFinance, MenthorQ), none combine them into a curated pick list with dormant long-dated bet activation as a scored layer. Gap is real.

---

## 2026-04-24 · Factor stack locked at 5

**Decision:** Technical Analysis, GEX / Dealer Positioning, Options Flow, Dormant-Bet Radar, Catalyst+Novelty Sentiment. Not 8.

**Rationale:** 8 was overkill. 5 keeps each factor high-signal. TA and GEX are hard gates; at least 2 of remaining 3 must align.

---

## 2026-04-24 · Universe scope

**Decision:** US-listed liquid options only. Min avg volume 1M, min OI per contract 500. No OTC. No crypto/futures/FX.

**Rationale:** User trades US equities swing + short-dated. Data quality collapses below liquidity thresholds.

---

## 2026-04-24 · Output is a curated dashboard, not a configurable scanner

**Decision:** No filter panels, no "build your own scan," no raw data tables (except as optional module). Dashboard shows 3–5 picks with thesis + explainability.

**Rationale:** The synthesis is the product. Existing tools show data; EigenView shows conclusions.

---

## 2026-04-24 · Module-first UI architecture

**Decision:** Every panel is an independent module. 5 preset templates + custom canvas. User picks a layout; modules compose.

**Rationale:** User feedback: v2 wireframe was cluttered. Module-first lets different user types (minimal vs. pro) see what fits them without a bloated default.

---

## 2026-04-24 · Tech stack

**Decision:** Python 3.11+ / FastAPI / Vanilla HTML+JS / SQLite / uv / TradingView Lightweight Charts.

**Rationale:** Solo user, local-first, no build toolchain friction. React not worth the overhead. FastAPI scales later if ever deployed.

---

## 2026-04-24 · Build environment

**Decision:** Migrate from Cowork to Claude Code Desktop (native Windows).

**Rationale:** Multi-module project with local data pipelines and scheduled jobs. Cowork sandbox adds friction; user already hit Windows pain points.

---

## 2026-04-24 · V1 excludes backtest

**Decision:** No backtesting module in v1.

**Rationale:** User explicitly descoped. Focus v1 on picks + dashboard + explainability. Backtest lab is Phase 9+.

---

## 2026-04-24 · Starting universe

**Decision:** S&P 500 + Nasdaq-100 combined (~540 unique tickers; ~400 after liquidity gate of ≥1M avg volume + ≥500 OI). Expand later if needed.

**Rationale:** User wants broad coverage of large-cap US equities with liquid options. S&P + Nasdaq-100 captures both broad-market and tech-heavy names. Combined universe is the sweet spot between coverage and scan speed.

---

## 2026-04-24 · Data budget for MVP

**Decision:** Free tier only for v1 (yfinance + Alpha Vantage free + Finnhub free). Add paid historical-options bootstrap (historicaloptiondata.com ~$20–50/mo) once MVP is validated.

**Rationale:** Validate the product concept before spending on data. Dormant-bet radar will use rule-based scoring in v1 (no ML training); upgrade to ML-trained activation classifier once paid historical data is added.

**Impact:** Dormant-bet radar in v1 is rule-based and less precise than the ML version it will become in v1.1. Document this limitation in the UI ("heuristic mode" badge on dormant-bet detections until training data is available).

---

## 2026-04-24 · Daily run schedule

**Decision:** Single daily scan at 08:00 ET (pre-market, 1.5h before open) for v1. Add 17:00 ET post-close scan later if useful.

**Rationale:** User trades swing + short-dated, so pre-market setup is primary. Post-close review can be added without architectural change.

---

## 2026-04-24 · Alert channels (default, pending explicit confirmation)

**Decision (default):** Dashboard + Windows desktop toast notifications for v1. Email, Telegram, Discord are extensibility targets for v2 — alert engine will be channel-agnostic so adding them is a plugin.

**Rationale:** Toast is native on Windows (no infra). Dashboard is always-on. Other channels require setup friction not worth v1 scope.

---

## All blocking questions resolved — ready to start Phase 0.
