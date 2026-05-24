# Next Session — Scanner Wiring + Full Project Audit

Paste this as the opening prompt for the next session.

---

## Context (what the last session did, 2026-05-24)

**Switched the data feed to Databento.** Deleted the old free/yfinance + Supabase data and reloaded from Databento:
- `scripts/databento_load.py` — equities (EQUS.MINI, 2yr daily + 90d 1h) + option-chain snapshot (OPRA.PILLAR, monthly expiries today→2028, ~500 SP500+NDX tickers). Loaded into SQLite `data/eigenview.db` (`prices`, `chains`). News/catalysts left on the existing free tier (Alpha Vantage + Finnhub).
- Key in `.env` as `DATABENTO_KEY` (gitignored). **This key was pasted in chat — rotate it.**
- Two-step design is deliberate: one cheap full-universe snapshot (~$28) to find the watchlist, then a tiny targeted history pull (~$2.68) for only the watched contracts.

**Built the dormant→activation two-layer model:**
- Layer 1 — dormant screen (`scripts/find_dormant.py` + `src/eigenview/factors/dormant.py`): finds big sleeping bets, relative-to-ticker size, isolated, long-dated. Output = watchlist (`dormant_bets` table, ~700). Static score = quality RANK only (no longer the fire gate).
- Layer 2 — activation engine (`src/eigenview/factors/activation.py`): compares each watched contract's DORMANT BASELINE (median over ~110d) vs RECENT (last 10d). Fires on a big jump in OI / volume / IV / option price / underlying move. Per-contract history pulled by `src/eigenview/data/databento_history.py` into `contract_history` table. Run via `scripts/run_activation.py --target <date> [--rescore]`.
- Thresholds (in `activation.py`): OI +50% & +1000 contracts · volume 10x · IV +10pts · premium doubled · underlying ±10% on 1.5x volume.

**Verified result (2026-05-22 session, 5/23 was a Saturday):** 75 tickers activated. Strongest (all 4 signals): PANW, DELL, MRVL, ZS, MU. Output: `data/activation_2026-05-22.xlsx`.

**Bugs fixed:** $0-premium (now IV-marked via `dormant.mark_price`); OI-carry-forward in `scanner._identify_dormant_bets` (was keyed on `original_date == today`, so OI change was always zero). `config.py` gained `databento_key`. 196 factor/synthesis tests pass.

---

## TASK 1 — Finish wiring the live app (`src/eigenview/synthesis/scanner.py`)

The morning scan is NOT yet on the new data and does NOT call activation. Currently:
- `_fetch_live()` still uses `yf.download` for prices → switch to reading the `prices` table (Databento 2yr daily).
- `get_chain()` still yfinance; scanner reads `Chain` where `snapshot_date == date.today()` → the Databento snapshot is dated 2026-05-23, so it finds nothing. Fix to read the LATEST snapshot.
- `score_dormant()` returns the static quality score as "activation_probability" → integrate the real activation engine: for each watched bet, read `contract_history`, call `score_activation()`, fire on activation (not static threshold).
- Add a daily step that refreshes `contract_history` for the watchlist (thin Databento pull) before scoring.
- Keep TA/GEX/flow/sentiment/macro intact — only change the data source + dormant/activation path.
- **Verify in the running FastAPI app** (start server, hit `/api/picks`, check a real pick), not just unit tests.

## TASK 2 — Rewire data feed off Supabase, project-wide

Audit every file for Supabase / old-data-source references and remove them; everything should read from SQLite (`data/eigenview.db`) + Databento.
- `.env` still has `SUPABASE_URL` / `SUPABASE_SECRET_KEY` (stale — project migrated off). `config.py` still declares `supabase_url`/`supabase_secret_key`.
- Grep for: `supabase`, `yfinance`/`yf.`, `get_chain`, `_fetch_live`, any hardcoded API hosts.
- Confirm `data/prices.py`, `data/chains.py`, `data/macro.py`, `data/news.py`, `data/calendar.py` either use Databento/free-tier correctly or are flagged.
- Produce a table: file → what it reads from now → what it should read from → action.

## TASK 3 — Full code audit (tabulated)

Audit ALL source + test files for:
1. **Fake/synthetic data** — cassettes, mocks of HTTP/DB, hand-crafted DataFrames/fixtures, hardcoded JSON responses (banned per global CLAUDE.md).
2. **Hardcoded logic** — magic numbers, hardcoded ticker lists, literal thresholds that should be config/percentile.
3. **Logic mistakes** — like the two found this session (day-over-day vs baseline; OI carry-forward keyed on today; underlying baseline over 2yr not windowed). Look for similar window/baseline/aggregation bugs.
4. **Fake/trivial test stubs** — `assert True`, `pass` bodies, `NotImplementedError`, tests that don't hit real data.
5. **Identify additional audit dimensions** and audit them too (e.g., error-handling gaps, unwired/orphan code, premium/greeks correctness, gate logic).

Run the semgrep stub audit from global CLAUDE.md as a seed:
```
$semgrep = "C:\Users\v_per\AppData\Local\Python\pythoncore-3.14-64\Scripts\semgrep.exe"
& $semgrep --config "C:\Users\v_per\.claude\audit-stubs.yaml" "C:\Users\v_per\Claude\Projects\Eigenview" --text --exclude="*.min.js" --exclude="dist" --exclude="node_modules"
```

**Deliverable:** one tabulated report — file · category · issue · severity · fix. Use subagents to parallelize across `data/`, `factors/`, `synthesis/`, `api/`, `tests/`.

## Start-of-session checklist
- `git log --oneline -5`, confirm the Databento branch is merged (or merge it).
- `uv run pytest -q`
- Read `src/eigenview/factors/activation.py` + `scripts/run_activation.py` to reload the activation model.
