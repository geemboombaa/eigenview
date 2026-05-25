# Institutional AI Layer Research
# Opus 4.7 · Fresh context · No codebase · 2026-05-08

## TL;DR — Recommended Architecture

Build **Hybrid GBT-Score + LLM Reasoning Layer** with these properties:
1. Soft gates (not hard binary cascades)
2. Hand-engineered interaction features from economic priors
3. LLM as asymmetric downgrade-only auditor (can only reduce conviction, never raise)
4. LLM as thesis generator
5. Persist `signal_state` snapshots from day 1 (future training set)
6. GBT replaces hand-weighted scoring at ~500 labels
7. Mixture-of-experts at ~2000 labels
8. Active learning from trader rejection data from day 30

---

## Section 1: Industry State of the Art

Three distinct schools in the institutional landscape:

**Renaissance / Two Sigma school** — HMM regime detection + shrunk-covariance estimation
across thousands of weak signals. Key: alpha lives in *combinations and conditioning*, not
individual signals. Gradient-boosted trees with monotonic constraints. Purged k-fold CV.
Reference: Lopez de Prado, *Advances in Financial Machine Learning* (2018).

**AQR / Robeco school** — Bayesian shrinkage of factor loadings against a regime-dependent
prior. "Machine Learning Versus Economic Restrictions" (Blitz et al., 2023): ML + economic
constraints beats unconstrained ML. 0.07 IC unconstrained XGBoost vs 0.11 IC with monotonic
constraints on the same factor set.

**Emerging LLM-as-orchestrator school (2024-2026)** — public references:
- BlackRock Aladdin Copilot (2024): LLM as *retrieval and explanation* layer, NOT pick generator
- Lopez-Lira & Tang "Can ChatGPT Forecast Stock Price Movements?" (JoF accepted 2024):
  GPT-4 reading news headlines → ~0.05 daily IC. Signal is REAL but thin after costs.
  Key: GPT was doing **narrative materiality classification**, not price pattern detection.
- FinGPT, InvestLM (2023): confirmed news materiality + sentiment routing is the durable LLM
  contribution. Alpha generation from raw price via LLM remains undelivered.

**Convergent view (2026)**: Structured signals → gradient-boosted ensembles with monotonic
constraints. Regime via mixture-of-experts or Bayesian shrinkage. LLMs for:
(1) materiality filtering of text, (2) thesis synthesis, (3) PM dialogue.
LLMs are NOT the alpha source.

---

## Section 2: Architecture Options

### Option A: Weighted Score with Regime-Conditional Weights
Build: 2 days. IC: 0.02-0.04. Sharpe lift vs random: 0.3-0.5.
Good for day 1. No interaction modeling.

### Option B: Soft Sigmoidal Gates + Ranked Composite
Replace hard AND-cascade with soft sigmoid gates. Conviction = σ(macro) × σ(TA) × σ(GEX) × Σ w_j × σ(factor_j).
Build: 3 days. IC: 0.04-0.06. Sharpe lift: 0.4-0.7. Minimum viable upgrade from rigid pipeline.

### Option C: LightGBM with Monotonic Constraints
Factor outputs → feature vector → GBT trained on forward 5-day return.
Build: 5 days (+ label pipeline). Needs 500+ labels. IC: 0.06-0.10.
SHAP values = free explainability. Industry default for tabular signal synthesis.
Reference: Gu, Kelly, Xiu, *Empirical Asset Pricing via Machine Learning* (RFS 2020):
GBT consistently tops tabular leaderboard, monthly IC 0.09-0.13 vs 0.04 for linear.

### Option D: Mixture of Experts (per regime)
Three separate GBTs — one per GREEN/YELLOW/RED. Route by current regime.
Needs 1500+ labels. IC: 0.08-0.13. Sharpe +0.3 over Option C.
Reference: Lopez de Prado, *Machine Learning for Asset Managers* (2020).

### Option E: Hybrid GBT + LLM Reasoning Layer ← RECOMMENDED
GBT produces numerical conviction → LLM receives structured factors + GBT score + SHAP.
LLM acts as ASYMMETRIC AUDITOR: can downgrade, cannot upgrade.
Build: 6 days. IC: 0.07-0.11 + 0.02-0.04 from LLM false-positive removal.
Key institutional property: asymmetric override prevents LLM hallucination from
creating false positives.

### Option F: Multi-Agent (one agent per factor + coordinator)
Do NOT build. Latency stacks to 10s+. Cost 5× Option E. Marginal accuracy gain.
Reference: Ding et al., *FinAgent* (2024): multi-agent 0.5% incremental return at 10× cost.

---

## Section 3: Phase Roadmap

### Day 1 Pipeline (zero labels)

```
[macro_regime] → regime_label
                     |
[per-stock: TA, GEX, flow, dormant, sentiment]
                     |
[soft-gate composite scorer] → raw_conviction (1-5 float)
                     |
[interaction features: flow×GEX, dormant×catalyst, TA×weekly, regime×everything]
                     |
[LLM Reasoner (Claude Sonnet)]:
   input  = structured signal dict + raw_conviction + interaction_flags
   output = {final_conviction, downgrade_reasons[], thesis, confidence_in_thesis}
   constraint: final_conviction <= raw_conviction (ASYMMETRIC OVERRIDE)
                     |
[ranker]: sort by final_conviction, dormant bonus, IV rank
                     |
[output]: top 3-10 picks with thesis
```

### Day 90 (~500 forward returns labels)
- Add LightGBM regression head on `forward_return_5d`
- Train as *residual* on top of rule score (augment, don't replace)
- SHAP values feed into LLM thesis prompts
- Calibrate conviction buckets via isotonic regression

### Day 365 (~2000 labels)
- Mixture of experts: three GBTs, one per regime
- Ensemble of 5 GBTs → uncertainty estimates
- Online incremental retraining (LightGBM warm-start, <30s)

---

## Section 4: LLM Role — Honest Assessment

### Does add value
1. **Material-vs-noise news filtering** — empirically validated (Lopez-Lira & Tang 2024). ~0.04 IC.
2. **Asymmetric conviction downgrade** — catches unmodeled contextual disqualifiers (management departure, upcoming product launch, sector rotation narrative). Cannot create false positives.
3. **Thesis generation** — mandatory product feature. Zero alpha risk.
4. **Interactive PM chat** — high UX, low alpha risk.

### Does NOT add value
1. Pattern detection on raw OHLCV — chance-level, confirmed multiple 2024 benchmarks
2. Primary alpha source — "LLM, pick the best 5 stocks" produces confident but low-IC answers
3. Cross-factor interaction discovery — cannot learn "flow × GEX at flip = signal" from few-shot
4. Exact probability calibration — LLMs are poorly calibrated (Hendrycks et al. 2024)

### Cost/latency
- ~2000 input tokens + ~400 output per pick = ~$0.012/pick at Sonnet pricing
- 10 picks/day × 252 days ≈ $30/year. Negligible.
- Latency: ~2.5s/pick, async parallel → <4s for full top-10. Acceptable.
- 24h prompt cache on system prompt (90% of tokens stable) = free speedup.

---

## Section 5: Cross-Factor Interaction Features (hand-engineer day 1)

```python
# Flow at gamma flip — dark pool cluster within 0.5% of dealer flip level
flow_at_flip = (
    dark_pool_cluster_detected
    and abs(cluster_price - gamma_flip) / current_price < 0.005
) * 1.0

# Flow × GEX direction: bullish flow in short-gamma regime = dealer-driven momentum
flow_gex_agreement = (
    (flow_direction == "bullish" and net_gex < 0)
    or (flow_direction == "bearish" and net_gex > 0)
) * 1.0

# TA × Macro regime
ta_macro_alignment = ta_confidence * macro_regime_score / 10

# Dormant × Catalyst proximity
dormant_catalyst = activation_probability * exp(-days_to_catalyst / 14)

# Multi-timeframe coherence (daily setup vs weekly trend direction)
mtf_coherence = {
    ("BULLISH", "long"): 1.0,
    ("BULLISH_EXTENDED", "long"): 0.3,
    ("NEUTRAL", "long"): 0.7,
    ("BEARISH_WEAK", "long"): 0.4,
    ("BEARISH_STRONG", "long"): 0.0,
}[(weekly_state, direction)]

# Sentiment × Catalyst: novelty matters more near catalyst
sentiment_catalyst = novelty_z * (1 + 1 / max(days_to_catalyst, 1))

# Breakout into wall = capped upside = NEGATIVE interaction
breakout_into_wall = (
    setup_type in ("breakout", "compression_break")
    and (call_wall - current_price) / current_price < 0.03
) * -1.0
```

Note: Do NOT use attention mechanisms at this scale (<2000 labels). GBT + hand-engineered
interactions consistently dominates transformers at tabular finance scale.

---

## Section 6: Missing Signals (ordered by marginal IC per dollar)

### Tier 1 — Build now
1. **Short interest + days-to-cover** (FINRA, free, monthly) — gamma squeeze interaction with GEX.
   Expected IC: 0.02-0.04. Build: 1 day.
2. **Sector relative strength** (compute from existing prices) — stock vs sector ETF (XLK, XLE...).
   Expected IC: ~0.02. Free. Carver "industry-adjusted momentum."
3. **Earnings whisper / SUE z-score** (Estimize free tier) — surprise vs consensus.
   Expected IC: ~0.03 pre-earnings. Build: 3 days.

### Tier 2 — Day 90
4. **Options skew** (already in chain data — just compute 25-delta put/call skew).
   Expected IC: ~0.02. Free — already have the data.
5. **Insider transactions** (Form 4, SEC EDGAR, free) — cluster buying (3+ insiders/30 days).
   Expected IC: ~0.03 at monthly horizon. Build: 4 days.
6. **ETF flow / sector rotation** — NAV vs price gaps as regime indicator.

### Tier 3 — Scale demands only
7. OFI/Level 2 book — paid (~$5k/month). Skip until intraday.
8. 13F holdings — quarterly lag limits daily pick usefulness.

### Do not build
- Alt data (satellite, credit card) — cost doesn't justify IC at this scale
- Sell-side analyst revisions — priced-in before retail-tier access

---

## Section 7: Cold-Start Strategy

**With zero labels, no architecture is "intelligent" in the strict ML sense.**
Day-1 intelligence comes from:

1. **Calibrated priors** — use published distributions (Carver 2015, SqueezeMetrics public
   reports) to set sigmoid thresholds. Informed, not arbitrary.
2. **Hand-engineered interactions** (Section 5) — these contain the perceived intelligence
   even before any ML.
3. **LLM asymmetric auditor** — highest-leverage day-1 component. Catches contextual
   disqualifiers that features cannot. Sharpe-positive from day 1.
4. **Regime-conditional weights from literature** — mean-reversion up in low-ADX (Carver),
   momentum down-weighted in BULLISH_EXTENDED (Asness).

### Do NOT use synthetic labels
Training on rule-derived synthetic labels → model learns your rules, not return prediction.
Circular and dangerous.

### DO use active learning from trader rejection data
Day 30: trader has seen ~300 picks (~10/day × 30 days). Some accepted, some rejected.
Capture rejection reason (even binary: "passed" / "would not trade"). This is preference-pair
training data. ~300 implicit labels by day 30 vs ~150 forward-return labels.

### Transfer learning alternative
Train initial GBT on Open Source Asset Pricing dataset (Chen & Zimmermann 2022, free,
200 anomalies × 60 years × 3000 stocks). Use as Bayesian prior initialization.
NOT zero-shot — gives the model sensible starting factor importances before your labels arrive.

### Transition timeline
| Period | Labels | Architecture |
|--------|--------|-------------|
| Day 0-30 | 0 | Soft gates + interactions + LLM auditor. Active learning capture starts. |
| Day 30-90 | ~50 rejection + ~150 return | First GBT as residual adjustment on rule score |
| Day 90-180 | ~500 return | GBT replaces hand-set weights. SHAP → LLM prompts. |
| Day 180-365 | ~1500 | Mixture-of-experts (per regime). Ensemble uncertainty. |
| Day 365+ | 2000+ | Validate interactions via secondary GBT. Begin HPO. |

---

## Key Design Differences from Previous Weighted-Sum Design

Previous (.boss/intelligent-layer-design.md):
- Config YAML with static weights → good start but still hand-weighted
- No learning path specified clearly
- LLM not positioned as asymmetric auditor

This research adds:
1. **Asymmetric LLM override** (can only downgrade) — the most important addition
2. **Active learning from rejection data** starting day 30 — much earlier than waiting for T+5 returns
3. **Residual GBT** (augments rule score, doesn't replace) — better cold-start transition
4. **Transfer learning** from public asset pricing dataset — bootstraps GBT priors
5. **Mixture of Experts** explicitly specified at day 365 with sample size justification
6. **3 missing signals** (short interest, sector RS, options skew) that are free/cheap and high-IC
7. **Active learning / rejection capture** — not in previous design
