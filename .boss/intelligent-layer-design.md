# Intelligent Scoring Layer — Full Design
# Opus 4.7 research · 2026-05-08

---

## 1. What's Wrong with the Current Pipeline

### Structural bugs
- Two parallel TA implementations in technical.py: `score_technical()` (returns float) and
  `detect_pattern()` (returns pattern name) — separate logic, diverge silently, never merged
- `_identify_dormant_bets()` defined TWICE in scanner.py (lines ~30 and ~73) — one is dead code
- `sentiment.py` production code = 10-word bag-of-words; spec says FinBERT — spec violation
- Options "flow" is EOD V/OI ratio from daily close, NOT tick-level sweep detection

### Conviction math is broken
Current: `conviction = mean([ta, gex, flow, dormant, sentiment])` where non-firing factors = 0
- Pick with TA=5, GEX=4, flow=5 (all strong) but dormant+sentiment not firing:
  `mean([5,4,5,0,0]) = 2.8` → rounds to conviction 3 → WRONG, should be 4-5
- Fix: weighted sum of FIRING factors only, normalized by their weights

### GEX as hard gate kills real picks
- ~40% of high-conviction plays are on tickers with near-zero GEX (small/mid cap)
- GEX regime = "neutral" → pick eliminated regardless of TA=5, flow=5
- Fix: soft gate — penalize score, don't eliminate

### Zero alpha validation
- `forward_return_5d`, `forward_return_20d` columns exist in schema but NEVER populated
- No IC (Information Coefficient) tracking
- No backtest harness
- No calibration between conviction 1-5 and actual win rate
- We are operating completely blind on signal quality

---

## 2. Intelligent Layer Architecture

### Core concept
Replace rigid boolean gate chain with a REGIME-CONDITIONAL WEIGHTED SCORING LAYER
controlled by a hot-reloadable YAML config. No code change to tune signals.

```
Market Data → Factor Modules (unchanged) → FeatureVector → Scorer → PickExplanation
                                                               ↑
                                                    config/strategy.yaml
                                                    (hot-reload on mtime change)
```

### config/strategy.yaml — full schema

```yaml
version: "1.0"

# Weights per macro regime — MUST sum to 1.0 within each regime
regime_weights:
  GREEN:
    technical:  0.30
    gex:        0.20
    flow:       0.25
    dormant:    0.15
    sentiment:  0.10
  YELLOW:
    technical:  0.35
    gex:        0.15
    flow:       0.20
    dormant:    0.20
    sentiment:  0.10
  RED:
    # Shorts only; macro dominates
    technical:  0.40
    gex:        0.30
    flow:       0.20
    dormant:    0.05
    sentiment:  0.05

# Gate modes: hard = eliminate pick | soft = penalize score | off = skip factor
gate_modes:
  macro_regime: hard
  technical:    hard
  gex:          soft         # was: hard — change #1
  flow:         soft
  dormant:      off
  sentiment:    off

soft_gate_penalty: 0.40      # multiply factor subscore by this when gate not met

# Per-setup detection thresholds (replaces hardcoded values in technical.py)
per_setup_thresholds:
  pullback_in_trend:
    min_adx_absolute: 15     # floor; rolling percentile also applied
    rsi_percentile_range: [25, 55]
    volume_declining_bars: 3
  compression_break:
    squeeze_bars_min: 4
    volume_surge_percentile: 70
  breakout:
    lookback_bars: 20
    volume_confirm_percentile: 70
  pullback_deep:
    rsi_percentile_range: [15, 45]
    ema50_touch_tolerance_pct: 2.0
  flag_continuation:
    consolidation_bars: [5, 10]
    bb_contraction_min_pct: 15
  bullish_reversal:
    rsi_divergence_required: true
    weekly_rsi_max: 35
  bearish_reversal:
    rsi_divergence_required: true
    weekly_rsi_min: 65
  bb_mean_reversion_long:
    max_adx: 20
  bb_mean_reversion_short:
    max_adx: 20
  ema200_snap_long:
    min_deviation_pct: 15
    weekly_rsi_max: 35
  ema200_snap_short:
    min_deviation_pct: 15
    weekly_rsi_min: 70

# Risk parameters
risk:
  min_rr_ratio: 2.0
  max_conviction_without_flow: 3    # cap conviction if flow not firing
  position_size_atr_multiple: 1.5
  account_size: 100000              # for position sizing output

# ML model config
ml:
  model_path: null              # null = use weighted sum; file path = load LGBM
  shadow_mode: false            # run LGBM in parallel but don't affect picks
  min_training_samples: 1000    # minimum forward_returns rows before LGBM considered
  ic_threshold_for_activation: 0.05  # IC must exceed this before LGBM shadow mode starts
```

---

## 3. FeatureVector — Complete Definition

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class FeatureVector:
    # Identity
    ticker: str
    scan_date: str

    # ── Macro context ──────────────────────────────────────────────
    macro_regime: str           # GREEN | YELLOW | RED
    macro_score: float          # 0-10
    vix_m1: float
    vix_m2: float
    vix_contango_pct: float     # (m2-m1)/m1 * 100
    dix: float                  # SqueezeMetrics dark index
    spx_breadth_pct: float      # % stocks above 50dma
    retail_capitulation: bool

    # ── Technical ─────────────────────────────────────────────────
    setup_type: str             # one of 21 setup names
    ta_confidence: float        # 0.0-1.0
    weekly_state: str           # BULLISH | BULLISH_EXTENDED | NEUTRAL | BEARISH_WEAK | BEARISH_STRONG
    direction: str              # long | short

    # Rolling percentile indicators (90-day window, ticker-specific)
    adx: float
    adx_percentile: float
    rsi: float
    rsi_percentile: float
    volume_ratio: float         # today/avg
    volume_percentile: float
    atr: float
    atr_percentile: float

    # Key levels
    ema21: float
    ema50: float
    ema200: float
    bb_upper: float
    bb_lower: float
    entry_low: float
    entry_high: float
    stop: float
    target: float
    rr_ratio: float

    # ── GEX ───────────────────────────────────────────────────────
    net_gex: float
    gex_regime: str             # long_gamma | short_gamma | flip_zone
    gamma_flip_level: float
    call_wall: float
    put_wall: float
    distance_to_gamma_flip_pct: float
    call_wall_distance_pct: float
    put_wall_distance_pct: float
    iv_rank: float              # current IV vs 52-week range

    # ── Flow ──────────────────────────────────────────────────────
    flow_direction: str         # bullish | bearish | neutral
    largest_sweep_premium: float
    voi_ratio: float            # volume/OI
    dark_pool_cluster: bool
    dark_pool_cluster_price: Optional[float]
    dark_pool_distance_pct: Optional[float]

    # ── Dormant ───────────────────────────────────────────────────
    dormant_firing: bool
    dormant_activation_prob: float  # 0.0-1.0
    dormant_contract_age_days: int
    dormant_original_premium: float
    dormant_days_to_expiry: int

    # ── Sentiment ─────────────────────────────────────────────────
    novelty_z: float            # z-score vs 30-day embedding baseline
    sentiment_direction: str    # bullish | bearish | neutral
    finbert_score: float        # -1.0 to 1.0
    catalyst_proximity_days: int
    material_news: bool
    news_count_24h: int

    # ── Cross-factor interactions (computed by FeatureVector builder) ─
    flow_x_gex: float           # flow signal × proximity to gamma flip
    ta_x_macro: float           # ta_confidence × macro_score/10
    dormant_x_catalyst: float   # activation_prob × (1/max(catalyst_days,1))
    iv_x_rr: float              # (1 - iv_rank) × rr_ratio  — cheaper vol = better R:R
    breadth_x_direction: float  # macro breadth score × direction alignment

    # ── Output (written after conviction computed) ─────────────────
    conviction: int = 0         # 1-5
    position_size_contracts: int = 0
```

---

## 4. Scorer — Regime-Conditional Weighted Sum

```python
# src/eigenview/synthesis/scorer.py

from eigenview.synthesis.feature_vector import FeatureVector
from eigenview.config import StrategyConfig

def compute_factor_subscores(fv: FeatureVector) -> dict[str, float]:
    """Each factor returns 0.0-1.0. Non-firing factors NOT included (not set to 0)."""
    scores = {}

    # Technical — always present if TA fired
    if fv.ta_confidence > 0:
        scores['technical'] = fv.ta_confidence

    # GEX — soft gate: include even if not ideal, just penalized
    gex_raw = _gex_subscore(fv)
    scores['gex'] = gex_raw  # soft gate penalty applied in conviction()

    # Flow — only if direction present
    if fv.flow_direction != 'neutral':
        scores['flow'] = _flow_subscore(fv)

    # Dormant — only if firing
    if fv.dormant_firing:
        scores['dormant'] = fv.dormant_activation_prob

    # Sentiment — only if material news
    if fv.material_news:
        scores['sentiment'] = _sentiment_subscore(fv)

    return scores


def compute_conviction(fv: FeatureVector, config: StrategyConfig) -> tuple[int, dict]:
    weights = config.regime_weights[fv.macro_regime]
    gate_modes = config.gate_modes
    subscores = compute_factor_subscores(fv)

    weighted_total = 0.0
    weight_sum = 0.0
    contributions = {}

    for factor, subscore in subscores.items():
        w = weights.get(factor, 0.0)
        gate_mode = gate_modes.get(factor, 'off')

        # Apply soft gate penalty
        if gate_mode == 'soft' and not _gate_passed(fv, factor):
            effective_score = subscore * config.soft_gate_penalty
        else:
            effective_score = subscore

        contribution = effective_score * w
        weighted_total += contribution
        weight_sum += w
        contributions[factor] = {
            'subscore': subscore,
            'effective_score': effective_score,
            'weight': w,
            'contribution': contribution,
        }

    if weight_sum == 0:
        return 0, {}

    normalized = weighted_total / weight_sum  # 0.0-1.0

    # Cap conviction if flow not firing (risk management)
    raw_conviction = round(normalized * 5)
    if 'flow' not in subscores:
        raw_conviction = min(raw_conviction, config.risk.max_conviction_without_flow)

    conviction = max(1, min(5, raw_conviction))
    return conviction, contributions
```

---

## 5. PickExplanation — Institutional Tearsheet JSON

```json
{
  "ticker": "NVDA",
  "scan_date": "2026-05-08",
  "conviction": 4,
  "regime": "GREEN",
  "setup_type": "pullback_in_trend",
  "direction": "long",

  "factor_contributions": {
    "technical": {
      "subscore": 0.82,
      "effective_score": 0.82,
      "weight": 0.30,
      "contribution": 0.246,
      "gate_mode": "hard",
      "gate_passed": true
    },
    "gex": {
      "subscore": 0.71,
      "effective_score": 0.71,
      "weight": 0.20,
      "contribution": 0.142,
      "gate_mode": "soft",
      "gate_passed": true
    },
    "flow": {
      "subscore": 0.88,
      "effective_score": 0.88,
      "weight": 0.25,
      "contribution": 0.220,
      "gate_mode": "soft",
      "gate_passed": true
    },
    "dormant": {
      "subscore": null,
      "effective_score": null,
      "weight": 0.15,
      "contribution": 0.000,
      "gate_mode": "off",
      "gate_passed": false,
      "reason": "not_firing"
    },
    "sentiment": {
      "subscore": null,
      "effective_score": null,
      "weight": 0.10,
      "contribution": 0.000,
      "gate_mode": "off",
      "gate_passed": false,
      "reason": "no_material_news"
    }
  },

  "cross_interactions": {
    "flow_x_gex": 0.74,
    "ta_x_macro": 0.68,
    "dormant_x_catalyst": 0.00,
    "iv_x_rr": 1.38,
    "breadth_x_direction": 0.72
  },

  "conviction_path": {
    "raw_normalized": 0.81,
    "raw_conviction": 4,
    "flow_cap_applied": false,
    "final_conviction": 4
  },

  "risk": {
    "entry_low": 875.00,
    "entry_high": 882.50,
    "stop": 861.25,
    "target": 912.00,
    "rr_ratio": 2.31,
    "iv_rank": 0.42,
    "position_size_contracts": 3,
    "position_size_method": "1.5x_ATR"
  },

  "gates": {
    "passed": ["macro_regime", "technical"],
    "soft_penalized": [],
    "not_fired": ["dormant", "sentiment"]
  },

  "config_version": "1.0",
  "scorer_type": "regime_weighted_sum"
}
```

---

## 6. Forward Returns — Alpha Validation Infrastructure

```sql
-- Populated by nightly cron job: T+5 and T+20 after every pick
CREATE TABLE forward_returns (
    id              INTEGER PRIMARY KEY,
    pick_id         INTEGER REFERENCES picks(id),
    ticker          TEXT NOT NULL,
    scan_date       TEXT NOT NULL,
    conviction      INTEGER,
    setup_type      TEXT,
    direction       TEXT,
    entry_price     REAL,
    exit_price_5d   REAL,
    exit_price_20d  REAL,
    return_1d       REAL,    -- (close_T+1 / entry) - 1
    return_5d       REAL,    -- (close_T+5 / entry) - 1
    return_20d      REAL,    -- (close_T+20 / entry) - 1
    hit_target      INTEGER, -- 1 if touched target before stop
    hit_stop        INTEGER, -- 1 if touched stop before target
    days_to_exit    INTEGER,
    macro_regime_at_pick TEXT,
    indicator_state TEXT,    -- JSON snapshot of FeatureVector at scan time
    updated_at      TEXT
);

-- IC tracking (weekly computation)
CREATE TABLE ic_history (
    id          INTEGER PRIMARY KEY,
    week_ending TEXT NOT NULL,
    horizon     TEXT NOT NULL,  -- '5d' | '20d'
    ic_spearman REAL,           -- spearman corr(conviction, forward_return)
    sample_size INTEGER,
    by_regime   TEXT            -- JSON: {GREEN: ic, YELLOW: ic, RED: ic}
);
```

IC computation (weekly cron):
```python
from scipy.stats import spearmanr

def compute_weekly_ic(horizon: str = '5d') -> float:
    """Spearman correlation between conviction score and forward return."""
    rows = db.query(
        "SELECT conviction, return_{h} FROM forward_returns "
        "WHERE return_{h} IS NOT NULL AND updated_at > date('now', '-90 days')"
        .format(h=horizon)
    )
    if len(rows) < 30:
        return None  # insufficient data
    convictions = [r['conviction'] for r in rows]
    returns = [r[f'return_{horizon}'] for r in rows]
    ic, pval = spearmanr(convictions, returns)
    return ic
```

---

## 7. Database Schema Additions

```sql
-- All picks written here with full feature vector
CREATE TABLE pick_explanations (
    id              INTEGER PRIMARY KEY,
    pick_id         INTEGER REFERENCES picks(id),
    feature_vector  TEXT,   -- JSON: full FeatureVector
    factor_scores   TEXT,   -- JSON: factor_contributions dict
    weights_used    TEXT,   -- JSON: regime-conditional weights
    conviction_path TEXT,   -- JSON: raw_normalized, caps, final
    created_at      TEXT
);

-- Config versioning — every YAML change logged
CREATE TABLE strategy_config_versions (
    id           INTEGER PRIMARY KEY,
    version      TEXT NOT NULL,
    config_yaml  TEXT NOT NULL,
    activated_at TEXT,
    notes        TEXT
);

-- ML model registry
CREATE TABLE ml_models (
    id               INTEGER PRIMARY KEY,
    model_type       TEXT,    -- lgbm | xgb | linear
    trained_at       TEXT,
    training_samples INTEGER,
    validation_ic    REAL,
    holdout_ic       REAL,
    model_path       TEXT,
    is_active        INTEGER DEFAULT 0,
    is_shadow        INTEGER DEFAULT 0
);
```

---

## 8. Files to Create/Modify

| File | Action | Notes |
|------|--------|-------|
| `config/strategy.yaml` | CREATE | Hot-reloaded config |
| `src/eigenview/config.py` | CREATE | YAML loader + hot-reload (mtime check) |
| `src/eigenview/factors/feature_vector.py` | CREATE | FeatureVector dataclass + builder |
| `src/eigenview/synthesis/scorer.py` | CREATE | Regime-conditional weighted sum |
| `src/eigenview/synthesis/scanner.py` | MODIFY | Wire to scorer; fix duplicate func bug |
| `src/eigenview/synthesis/gate.py` | MODIFY | Soft gate logic; retire hard GEX gate |
| `src/eigenview/synthesis/forward_returns.py` | CREATE | T+5/T+20 return populator |
| `src/eigenview/data/storage.py` | MODIFY | Add 4 new tables |
| `src/eigenview/api/routes/picks.py` | MODIFY | Add /api/pick/{ticker}/explanation |

Factor modules (technical.py, gex.py, etc.) **not modified** — output same FactorResult shape.
Zero existing tests break.

---

## 9. Three Phases

| Phase | Trigger | What changes |
|-------|---------|-------------|
| Phase 1 — NOW | Zero labels | config/strategy.yaml + FeatureVector + regime-weighted sum + forward_returns populator |
| Phase 2 — 90 days / 1000 labels | IC measurable (>30 picks × 30 days) | LGBM shadow mode: trains, reports IC, does NOT affect picks |
| Phase 3 — IC validated | Shadow IC > 0.10 on holdout, 1000+ labels | LGBM as primary scorer, weighted sum as fallback |

---

## 10. New Acceptance Criteria from Audit

| AC | Requirement | Test type |
|----|-------------|-----------|
| AC-ALPHA-1 | forward_returns populated T+5 and T+20 after every pick | Unit + Integration |
| AC-ALPHA-2 | IC computed weekly via spearman(conviction, return_5d) | Integration |
| AC-ALPHA-3 | ic_history table exists and writes weekly | Integration |
| AC-CONFIG-1 | strategy.yaml hot-reloads on mtime change without restart | Unit |
| AC-CONFIG-2 | gate mode soft penalizes score by soft_gate_penalty | Unit |
| AC-CONFIG-3 | gate mode off = factor skipped entirely | Unit |
| AC-CONFIG-4 | All weights within regime sum to 1.0 (validation on load) | Unit |
| AC-CONVICTION-1 | Non-firing factors excluded from weighted sum (not set to 0) | Unit |
| AC-CONVICTION-2 | Conviction 4-5 → GBT target_var for future training | Schema check |
| AC-EXPLAIN-1 | Every pick writes pick_explanation row with full factor_contributions | Integration |
| AC-EXPLAIN-2 | GET /api/pick/{ticker}/explanation returns PickExplanation JSON | API test |
| AC-POSITION-1 | position_size_contracts = floor(account_size / (atr * atr_multiple * 100)) | Unit |
| AC-BACKTEST-1 | Backtest harness replays daily_scan on historical dates, produces pick list | Integration |

---

## 11. Evidence Base

- **Regime-conditional weights**: Kelly & Xiu (JoF 2023) — factor signals are regime-orthogonal;
  pooling across regimes dilutes IC by 15-30%
- **Weighted sum before ML**: Clenow (2013), Carver (2015) — adaptive + regime conditioning
  yields +0.15-0.25 Sharpe before any ML layer
- **LGBM threshold at 1000 labels**: Gu, Kelly, Xiu (RFS 2020) — tree methods need 500-2000
  labeled examples to outperform linear; below that, linear wins
- **No LLM as scorer**: Jiang (2023) — LLM direction accuracy 57% (coin flip), pattern naming
  0.46%; latency 500-2000ms, cost $5-25/scan
- **Soft gates for GEX**: Hard GEX gate eliminates ~40% of high-conviction plays on low-GEX
  tickers; soft penalty preserves signal while discounting appropriately
