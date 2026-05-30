# Walk-Forward Data-Pull Strategy (locked 2026-05-30)

Goal: keep the dormant watchlist's per-contract history current every day, cheaply,
with no hangs — without ever re-pulling the whole 180-day window again.

## The two pull shapes

1. **Incremental tail (daily, cheap).** `_refresh_watchlist_history` already pulls each
   contract from `last_stored_date + 1 → today`. After the one-time 180d backfill, the
   daily tail is a **1 trading day × ~1,047 symbols** request — pennies. Chunked the same
   way as the backfill (≤25 syms/call × ≤45d window, capped concurrency 3, per-call timeout).
2. **New-contract backfill (only on churn).** Each scan rebuilds `dormant_bets` from fresh
   chains, so the watchlist gains/loses names daily. A *new* entrant has no history → it gets
   the full 180d window-chunked backfill on its first appearance only. Expired/closed contracts
   drop out and are never pulled again.

## Daily cadence

| Time | Step | Pull? |
|---|---|---|
| Pre-market | `fetch-data` (prices/chains) | yfinance/free |
| Pre-market | rebuild watchlist from fresh chains (size screen) | local |
| Pre-market | `_refresh_watchlist_history` — incremental tail + any new-contract 180d | Databento (small) |
| Pre-market | `daily-scan --download` → factors → gate → rank → thesis → picks | — |
| Intraday | UI **Scan now** button | **`--no-download` (never pulls)** |
| Daily | DIX / VIX / macro | free scrapes |
| Weekly | CFTC COT | free |

## Cost control
- Incremental tails dominate the steady state ≈ pennies/day.
- 180d backfills fire **only** when the watchlist gains a name; gate any pull whose
  `estimate_cost` (metadata-only, free) exceeds a set ceiling before sending it.
- `on_conflict_do_nothing` makes every pull idempotent — safe to re-run.

## Why it can't hang again (root-caused 2026-05-30)
The failure axis was **window depth**, not symbol count: a 25-sym × 180d `get_range` timed
out where short windows always returned fast. Fix splits along **both** axes — symbol
sub-batches (`scanner_history_symbol_batch=25`) **and** date windows
(`scanner_history_window_days=45`) — each call bounded by `scanner_history_call_timeout_secs`
(120s), run at `scanner_history_fetch_concurrency=3`. A single slow/failed piece drops only
its own symbols×window and is logged; it never stalls the phase. All knobs in config.

## Forward safety net
Every scan writes chain snapshots, which feed the activation engine's **forward mode**
(≥2 points) independently of Databento. So even a contract with thin paid history still
matures into a real baseline as snapshots accrue — the radar is never blind.
