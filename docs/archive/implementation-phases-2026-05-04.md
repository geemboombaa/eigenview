# EigenView Implementation Phases
**Version:** 0.1
**Last updated:** 2026-05-04
**Rule:** No phase closes without screenshot or test output. No claims.

---

## Principle

Build one thing completely. Prove it works end-to-end. Then multiply.

Never claim "fixed" without Playwright screenshot or pytest output attached.

---

## Phase 0 — Sample case + acceptance criteria
**Status:** IN PROGRESS
**Deliverable:** Spec document. Zero implementation code.

### Sample case

**Ticker:** NVDA
**Setup type:** `pullback_in_trend`
**Why this one:** Most common setup in trending market. Visually verifiable. Clear pass/fail. Exercises every layer.
**Date:** 2024-04-16 — NVDA pulling back to EMA21 after Feb earnings run. Price at EMA21 -0.3%, RSI=51, ADX=28, vol_ratio=0.77. Classic.

*(Original spec said 2024-01-16 — corrected after data check: Jan 16 had RSI=76, stock was extended not pulling back.)*

### Acceptance criteria (written before any code)

**Backend — `technical.py`**
- [x] `detect_pattern(nvda_daily_df, nvda_weekly_df, '2024-04-16')` returns `pattern='pullback_in_trend'`
- [x] `confidence >= 0.6`
- [x] `detail.trend == 'bullish'`
- [x] `detail.weekly_trend == 'bullish'`
- [x] `detail.rsi` value is between 38 and 57
- [x] `detail.adx >= 15`
- [x] `detail.vol_ratio < 1.5` (volume declining on pullback)
- [x] `detail.swing_low` is a float (swing level computed)
- [x] `detail.weekly_state` in ('BULLISH', 'BULLISH_EXTENDED')
- [x] Same function on 2024-01-04 (NVDA during compression, ADX=14) does NOT return `pullback_in_trend`

**API — `/api/picks`**
- [ ] Response contains: `setup_type, direction, entry_low, entry_high, stop, conviction`
- [ ] `structure.description` present and non-empty
- [ ] `structure.legs` present and non-empty (not just type)
- [ ] `signal_fired_at` present and ISO datetime parseable
- [ ] `factors.technical.firing == true`
- [ ] `factors.technical.detail` contains all 8 fields factor-strip reads

**UI — Pick card**
- [ ] `.card-setup-name` text == "Pullback to Support"
- [ ] `.card-rec` text starts with "◆" and contains the structure description
- [ ] `.btn-pin` visible at all times (opacity = 1, computed width > 0)
- [ ] `signal_fired_at` timestamp text visible on card (not in actions area)
- [ ] R:R ratio visible (target / (entry - stop))

**UI — Factor strip TA checklist**
- [ ] TA dot is green (`#22c55e` background)
- [ ] Clicking TA dot opens checklist
- [ ] Checklist shows exactly 5 checks for `pullback_in_trend`
- [ ] Check "Uptrend intact" shows ✓ and displays "Bullish" (from `d.trend`)
- [ ] Check "RSI in dip zone" shows ✓ and displays actual RSI number
- [ ] Check "Volume light on pullback" shows ✓ and displays actual vol_ratio
- [ ] No check shows hardcoded ✓ — all driven from `detail` data
- [ ] "TA · No Pattern" does NOT appear when pattern fired

**Chart**
- [ ] EMA21 line visible (green)
- [ ] EMA50 line visible (blue)
- [ ] Entry zone: 2 green dashed horizontal lines
- [ ] Stop: 1 red dashed horizontal line
- [ ] Arrow marker at signal bar (arrowUp, green)
- [ ] EMA21 toggle button: click → EMA21 disappears. Click again → reappears.
- [ ] Signals toggle: click → arrow marker disappears. Click again → reappears.

**Playwright proof files**
- [ ] `tests/ui/proof/phase0_card.png` — full card visible
- [ ] `tests/ui/proof/phase0_ta_checklist.png` — TA checklist open
- [ ] `tests/ui/proof/phase0_chart.png` — chart with EMA lines, entry/stop, marker
- [ ] `tests/ui/proof/phase0_chart_toggles.png` — EMAs toggled off

---

## Phase 1 — Backend: classify one setup correctly
**Status:** COMPLETE
**Scope:** `technical.py` changes for `pullback_in_trend` only.

### Steps (in order)
1. Create NVDA OHLCV fixture: `tests/fixtures/nvda_daily_2024.csv`, `tests/fixtures/nvda_weekly_2024.csv` — real data, saved to file, no API call in test
2. Write `tests/factors/test_technical_pullback.py` FIRST — all assertions from Phase 0 spec
3. Run test — confirm it FAILS (expected)
4. Rebuild `pullback_in_trend` detection in `technical.py`:
   - Replace hardcoded vol/RSI/ADX thresholds with rolling percentiles
   - Replace swing_high/low calculation with `swingtrend` library
   - Implement 5-state weekly context classifier
5. Run test — confirm it PASSES
6. Add 3 more known NVDA pullback dates — all must pass
7. Add 2 dates where pullback should NOT fire — assert `no_pattern`

### Exit criteria
```
pytest tests/factors/test_technical_pullback.py -v
# All tests green. Output pasted here.
```

**Actual output (2026-05-04):**
```
15 passed, 1 warning in 2.07s
```
All 15 Phase 1 acceptance tests pass. Full factors suite: 45/45 green.

**Implementation notes:**
- `swingtrend` not on PyPI; replaced with `scipy.signal.argrelextrema` (same output, available)
- Rolling RSI threshold: `rsi <= rsi_p40` (40th percentile of 90-day RSI) replaces hardcoded 38-57 range. Adaptive to stock's regime — in a high-RSI bull run, RSI=47 IS the dip zone.
- ADX: kept absolute floor of 15 (no rolling percentile for ADX gate — prevents false firing in compression)
- 5-state weekly classifier added: BULLISH / BULLISH_EXTENDED / NEUTRAL / BEARISH_WEAK / BEARISH_STRONG based on weekly EMA8/EMA21 relationship and RSI>70 extension flag
- `detect_pattern(daily_df, weekly_df, as_of_date)` is new public function. `score_technical()` unchanged for backward compat.

---

## Phase 2 — API: contract test
**Status:** PENDING
**Scope:** `/api/picks` serialization only.

### Steps
1. Write `tests/api/test_picks_contract.py` FIRST
   - Hit live server with known DB state (or inject via test fixture)
   - Assert every field from Phase 0 acceptance criteria is present
   - Assert `structure.legs` is not None and not empty string
   - Assert `signal_fired_at` is present
2. Run test — confirm failures
3. Fix `picks.py` serialization until all pass
4. No other API changes

### Exit criteria
```
pytest tests/api/test_picks_contract.py -v
# All tests green.
```

---

## Phase 3 — UI: card + factor strip
**Status:** PENDING
**Scope:** Pick card display + TA checklist for one setup.

### Steps
1. Write `tests/ui/pullback_card.spec.js` FIRST with all assertions from Phase 0
2. Run — shows current failures, screenshots saved
3. Fix UI code (pick-cards.js, factor-strip.js) until test passes
4. Screenshot saved to `tests/ui/proof/`

### Exit criteria
```
npx playwright test tests/ui/pullback_card.spec.js
# All assertions pass. Screenshot saved.
```

---

## Phase 4 — SPEC + AUDIT tabs in Help page
**Status:** PENDING
**Scope:** 2 new tabs in the existing HELP overlay.

### What gets built
- SQLite table: `spec_notes (id, spec_id TEXT, note TEXT, created_at TEXT)`
- `GET /api/spec/ta` — returns spec JSON (pattern list, conditions per pattern, required fields)
- `POST /api/spec/notes` — saves a note against a spec_id (your annotations)
- `GET /api/audit/ta` — reads technical.py + factor-strip.js, returns findings JSON
- Two new tabs in `help-page.js`: SPEC and AUDIT

### SPEC tab content
- One section per setup type
- For each setup: category, weekly requirement, detection conditions, expected detail fields
- Each item has a note field (editable, persisted to SQLite)
- Phase 0: shows `pullback_in_trend` only. Expands in Phase 6.

### AUDIT tab content
- "RUN AUDIT" button → hits `/api/audit/ta`
- Returns table: `[file, line, check, status (PASS/FAIL/WARN), detail]`
- Audit checks:
  - Every TA_CHECKS pattern in factor-strip.js has a matching pattern in technical.py
  - Every field read by factor-strip.js TA_CHECKS exists in technical.py detail dict
  - No hardcoded `true`/`false` in TA_CHECKS conditions
  - All 50 thresholds replaced with percentile calls (post Phase 1)
  - Weekly context has 5 states defined

### Exit criteria
```
npx playwright test tests/ui/spec_audit_tabs.spec.js
# SPEC tab renders. AUDIT tab renders with table. Screenshots saved.
```

---

## Phase 5 — Signal persistence + chart markers + toggles
**Status:** PENDING

### DB change
```sql
CREATE TABLE signal_triggers (
    id          INTEGER PRIMARY KEY,
    ticker      TEXT NOT NULL,
    scan_date   TEXT NOT NULL,
    setup_type  TEXT NOT NULL,
    direction   TEXT NOT NULL,
    entry_low   REAL,
    entry_high  REAL,
    stop        REAL,
    target      REAL,
    rr_ratio    REAL,
    confidence  REAL,
    fired_at    TEXT,
    valid_until TEXT
);
```

Also add to `signal_bench` (for future GBT training):
```sql
ALTER TABLE signal_bench ADD COLUMN forward_return_5d  REAL;
ALTER TABLE signal_bench ADD COLUMN forward_return_20d REAL;
ALTER TABLE signal_bench ADD COLUMN indicator_state    TEXT; -- JSON snapshot
```

### Chart changes
- `GET /api/chart/{ticker}/signals` — returns historical triggers for ticker
- price-chart.js: load signals on chart load, render via `createSeriesMarkers()`
- Add toggle toolbar: EMA21 | EMA50 | EMA200 | BB | SIGNALS | SUPERTREND
- `series.applyOptions({ visible: false })` on toggle. State in localStorage.

### Exit criteria
```
npx playwright test tests/ui/chart_signals.spec.js
# Markers visible. Toggles work. Screenshots saved.
```

---

## Phase 6 — Expand to all 21 setups
**Status:** PENDING (starts only after Phases 1–5 complete for pullback_in_trend)

For each setup type, in priority order:

1. `compression_break` / `compression_break_down` — uses squeeze_pro replacement
2. `breakout` / `breakdown` — uses swingtrend replacement
3. `choch_bullish` / `choch_bearish` — new, smartmoneyconcepts
4. `bos_bullish` / `bos_bearish` — new, smartmoneyconcepts
5. `bullish_reversal` / `bearish_reversal` — tighten weekly gate
6. `oversold_bounce` / `overbought_reversal`
7. `failed_breakdown` / `failed_breakout`
8. `ema_reclaim` / `ema_rejection`
9. `base_breakout` / `base_breakdown`
10. `rally_in_downtrend`
11. `pullback_deep`, `pullback_to_structure`, `flag_continuation` (new)
12. `bb_mean_reversion_long/short`, `ema200_snap_long/short` (new, if mean reversion in scope)

For each: write historical fixture + test FIRST. Fix code. Test passes. Move to next.

### Exit criteria
```
pytest tests/factors/ -v
# All setup tests green.
```

---

## Phase 7 — Full audit clean
**Status:** PENDING

- AUDIT tab shows all 21 setups with no FAIL rows
- SPEC tab shows full taxonomy
- All Playwright tests pass
- Full `pytest` suite passes

### Exit criteria
```
pytest -v && npx playwright test
# Both fully green.
# Screenshot of AUDIT tab showing all passes.
```

---

## Timeline estimate

| Phase | Estimated sessions | Blocking dependency |
|---|---|---|
| 0 | Done (this session) | Approval |
| 1 | 1 session | Phase 0 approved |
| 2 | 0.5 session | Phase 1 |
| 3 | 1 session | Phase 2 |
| 4 | 1 session | Phase 3 |
| 5 | 1 session | Phase 4 |
| 6 | 3–4 sessions (21 setups) | Phase 5 |
| 7 | 0.5 session | Phase 6 |

---

## What's on hold until 180 days of scan data

- GBT confidence calibration model (needs labeled pattern + forward return data)
- Pattern success rate display on cards (% of this setup type that reached target)
- Backtest summary per pattern

Data collection starts in Phase 5 (`indicator_state` + `forward_return` columns in `signal_bench`). Nothing to build — just write the data. Train when ready.
