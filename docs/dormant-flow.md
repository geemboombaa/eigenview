# Dormant-Bet Flow — Filter → Score → Fire

How the dormant radar decides a sleeping options position is "waking up". Stages
run in order; a ticker must clear each to reach the next.

## Stage 1 — Liquidity gate  (`scanner._score_ticker`)

Sum the open interest (OI) across all of a ticker's option contracts in the latest
chain snapshot. If aggregate OI is below `settings.dormant_min_ticker_oi`, the
ticker is `NOT_LIQUID`: no candidates are tracked, nothing is scored, it can never
fire. Its options are too thin to read positioning.

## Stage 2 — Candidate filter  (`_identify_dormant_bets` → `is_dormant_candidate`)

Walk every contract in the chain. Keep one only if ALL are true:

1. **Long-dated** — expiry ≥ today + `dormant_min_dte` (20) days.
2. **Big for this ticker** — dollar-delta (|delta| × OI × 100 × spot) ≥ floor, where
   floor = max($1M, the ticker's own 80th-percentile dollar-delta). Top ~20% of the
   ticker's book AND at least $1M.
3. **Not deep ITM** — |delta| ≤ `dormant_deep_itm_delta` (0.85). Deep ITM = a stock
   substitute, not a directional bet.
4. **Real position** — contract OI ≥ `scanner_min_oi` (500).

Survivors are written to the `dormant_bets` watchlist (key: ticker + contract +
original_date).

## Stage 3 — Score + fire  (`score_dormant_from_history`)

For each tracked bet, pull its per-day history from `contract_history`
(daily OI / volume / close / IV per contract).

- **Has ≥ `activation_min_history` (30) days of history** → run the **activation
  engine** (`score_activation`). It compares the sleeping BASELINE (older part of the
  window) to the RECENT window (last `activation_recent_days` = 10 days) and counts
  triggers:
  - **OI jump** — current OI ≥ 75% above baseline AND ≥ 1,000 more contracts.
  - **Volume surge** — a recent day ≥ 10× baseline average volume AND ≥ 1,000.
  - **IV jump** — IV ≥ 10 vol-points above baseline.
  - **Underlying move** — stock moved ≥ 15% in the bet's direction on ≥ 1.5× volume.

  **Fires when ≥ 2 triggers** hit. Strength = triggers ÷ 4.

- **No bet has enough history** → `ACCUMULATING`, does **not** fire. (Structure alone
  — big + long-dated — is near-universal and must never fire on its own.)

Final firing = activation fired AND strength ≥ `dormant_firing_threshold` (0.5).

## Stage 4 — Static rubric (vestigial)  (`score_bet_v2`)

Computes a structural quality number (size percentile / cheap IV / catalyst /
time-left / long-dated, max 7). It is used only as a ranking/info value for a tracked
candidate. **It no longer fires anything** — only the activation engine fires.

> Once `contract_history` covers all liquid tickers (via the targeted Databento
> pull), Stage 4 has no remaining purpose and should be removed: every liquid bet
> will have history, so activation always runs.

## Coverage dependency

Activation can only run on contracts that have daily history in `contract_history`.
The targeted pull (`scripts/download_liquid_history.py`) fetches history for liquid
tickers' biggest bets so the radar can fire across the whole liquid universe, not
just the names already stored.

## Config knobs (all in `config.py`)

| Setting | Meaning |
|---------|---------|
| `dormant_min_ticker_oi` | Stage 1 liquidity floor (aggregate ticker OI) |
| `dormant_min_dte` | Stage 2 min days-to-expiry |
| `dormant_size_filter_pct` | Stage 2 bigness percentile (0.80) |
| `dormant_deep_itm_delta` | Stage 2 deep-ITM cutoff (0.85) |
| `scanner_min_oi` | Stage 2 per-contract OI floor (500) |
| `activation_min_history` | Stage 3 min history rows (30) |
| `activation_recent_days` | Stage 3 recent window (10) |
| `activation_oi_jump_pct` / `_oi_min_delta` | Stage 3 OI trigger |
| `activation_vol_mult` / `_vol_min` | Stage 3 volume trigger |
| `activation_iv_jump_abs` | Stage 3 IV trigger |
| `activation_und_move_pct` / `_und_vol_mult` | Stage 3 underlying trigger |
| `activation_min_triggers` | Stage 3 fire threshold (2) |
| `dormant_firing_threshold` | Stage 3 final strength gate (0.5) |
