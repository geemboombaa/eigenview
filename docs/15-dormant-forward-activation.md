# Dormant Activation — Forward-First Redesign (2026-05-30)

## Why this changed

The old activation engine was **lookback-only**: for each big sleeping options bet it
pulled the contract's past from Databento `contract_history`, called the older slice the
"dormant baseline" and the last 10 days "now," and fired on a baseline→recent jump.

**The data doesn't support that.** Databento EOD statistics are sparse per contract:
36,023 tracked contracts, **median 3 history rows each**, only 1,848 with ≥30 days. The
engine required 30 days → it could almost never score → most names sat in `ACCUMULATING`
(= "not enough history to judge"), which the pick gate read as "dormant did not fire."
Net effect: dormant was a near-dead gate starving the daily pick list.

## The redesign — forward-first, lookback where it exists

We already store a full options chain snapshot every scan (`chains` table, one row set per
`snapshot_date`). That is a forward-accumulating history we **own** — no Databento needed.

For each tracked dormant contract we now build ONE merged daily series from:
1. `contract_history` (Databento, past — used where it exists), and
2. `chains` snapshots for that exact contract across `snapshot_date` (our own, grows every scan).

Windowed to the last **30 days**, then:

| Series length (last 30d) | Mode | Behaviour |
|---|---|---|
| ≥ 30 points | **lookback** | baseline (older) vs recent (last 10d) — same as before |
| 2–29 points | **forward** | baseline = earliest points, recent = latest; compare with whatever we have |
| < 2 points (just discovered) | — | `ACCUMULATING` (genuinely can't compare yet — resolves on the next scan) |

Both modes run the **same trigger logic**; only the baseline/recent split differs. The
recent window auto-shrinks for short series (`recent = min(10, max(1, L//2))`) so the
baseline is never empty.

`ACCUMULATING` now means "discovered, fewer than 2 snapshots so far" — a one-scan transient,
**not** "no Databento history." DORMANT = scored, nothing fired. ACTIVE = fired.

## Activation triggers (realistic thresholds, all in config)

Fire when **≥2 of 4** trip (`activation_min_triggers`):

| Signal | Fires when | Config |
|---|---|---|
| OI accumulation | current OI ≥ **+30%** above baseline **and** ≥ **+500** contracts | `activation_oi_jump_pct=0.30`, `activation_oi_min_delta=500` |
| Volume burst | a recent day ≥ **3×** baseline avg **and** ≥ **500** | `activation_vol_mult=3.0`, `activation_vol_min=500` |
| IV jump | IV ≥ **+5 vol points** above baseline | `activation_iv_jump_abs=0.05` |
| Underlying move | stock ≥ **+5%** in the bet's direction on ≥ **1.4×** volume | `activation_und_move_pct=0.05`, `activation_und_vol_mult=1.4` |

Old thresholds (75% OI / 10× vol / 15% move / 10 IV pts) required two near-extreme events at
once and almost never fired. Nothing is hardcoded — every number is `settings.activation_*`.

Window/sizing knobs: `activation_lookback_days=30`, `activation_recent_days=10`,
`activation_forward_min=2`, `activation_min_history=30` (the lookback/forward boundary).

## FUTURE — deep look-back (parked)

The richer design — at discovery, reach **6+ months** back to find exactly when the position
was opened and replay activation across its whole life — is **deferred until a denser
per-contract data source exists** (Databento EOD statistics are too sparse). When we have
daily OI/volume/IV per contract going back months, restore the full lookback and keep the
forward path as the fallback. Tracked here so it isn't lost.

## Files

| Concern | File |
|---|---|
| Trigger math + baseline/recent split | `factors/activation.py::score_activation` |
| Merge contract_history + chain snapshots, label ACTIVE/DORMANT/ACCUMULATING | `factors/dormant.py::score_dormant_from_history` |
| Chain-snapshot series read | `factors/dormant.py::_chain_snapshot_series` |
| Thresholds | `config.py` (`activation_*`) |
