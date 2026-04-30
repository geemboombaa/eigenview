# 03 — Factor Specifications

Each factor is an independently-testable Python module in `src/eigenview/factors/`. Each produces a normalized score + firing state + narrative for a given ticker.

## Common output contract

```python
@dataclass
class FactorResult:
    factor_id: str                # 'technical' | 'gex' | 'flow' | 'dormant' | 'sentiment'
    firing: bool                  # did the factor qualify
    strength: float               # 0.0 to 1.0
    label: str                    # short display label e.g. "COMPRESSION BREAK"
    detail: dict                  # factor-specific structured data
    narrative: str                # one-sentence AI/template narrative
```

---

## Factor 1 — Technical Analysis (`technical.py`)

**Signals computed:**
- Trend: 20 / 50 / 200 EMA stack, ADX(14), higher-high / higher-low structure detection
- Momentum: RSI(14) + divergence detection, MACD signal cross
- Volatility state: ATR(14), Bollinger bandwidth, compression detection (bandwidth < 10th percentile over 90 days)
- Volume: OBV trend, VWAP deviation, volume profile POC / HVN / LVN
- Levels: swing highs/lows over 60 days, prior week/month open

**Pattern classifier:** shallow sklearn model (or rule-based for MVP) labels setup as one of:
`compression_break | breakout | pullback_in_trend | flag | double_top | double_bottom | head_shoulders | vcp | exhaustion | range`

**Firing condition:** pattern classifier confidence > 0.6 AND trend context aligns with pattern direction.

**Data source:** `yfinance` for OHLCV + `pandas_ta` for indicators.

**Multi-timeframe rule:** weekly trend direction must not contradict daily setup (e.g. daily breakout against weekly downtrend = weaker firing).

---

## Factor 2 — GEX / Dealer Positioning (`gex.py`)

**Signals computed:**
- Net dealer gamma exposure across all strikes/expiries (aggregated $ per 1% move)
- Gamma flip level (price where GEX changes sign)
- Call wall (strike with heaviest positive gamma)
- Put wall (strike with heaviest negative gamma)
- Regime flag: `short_gamma` | `long_gamma` | `flip_zone`

**Formula (simplified):**
```
GEX(strike) = gamma(strike) * OI(strike) * 100 * spot² * 0.01
Net GEX = Σ (calls' GEX - puts' GEX)
```

Uses Black-Scholes gamma from `py_vollib`. Sign convention: assume all calls are dealer-short, all puts are dealer-short (standard retail GEX assumption; documented in code).

**Firing condition:** regime flag is `short_gamma` (for long directional picks) OR `long_gamma` with price between walls (for premium-selling picks).

**Data source:** options chain from `yfinance` or `openbb`. For production, swap to Polygon/Tradier paid.

**Key output for UI:** call wall, put wall, gamma flip as chart overlay levels.

---

## Factor 3 — Options Flow Quality (`flow.py`)

**Signals computed:**
- New OI detection: today's volume / existing OI ratio ≥ 3.0 = new position
- Premium size: notional $ traded per contract
- Aggressive side: trade at ask = bullish for calls / bearish for puts; at bid = opposite
- Sweep detection: same contract hit across multiple exchanges within seconds
- IV skew shift: 25-delta skew change day-over-day

**Firing condition:** at least one contract meets premium > $500K, V/OI ≥ 3, aggressive side = direction of pick.

**v1 limitation:** free-tier data is delayed 15 min and doesn't include exchange-by-exchange prints, so sweep detection is approximate. Flag this in the factor's `narrative`.

**Data source:** free tier: `yfinance` chain snapshots. Paid upgrade: OptionStrat API or Polygon.

---

## Factor 4 — Dormant-Bet Radar (`dormant.py`) ⭐ DIFFERENTIATOR

**Concept:** Large long-dated options positions opened 30–180 days ago that haven't yet played out in the direction of the bet. When they approach a catalyst AND current flow aligns AND stock hasn't yet moved to the bet thesis, score activation probability high.

**Input universe:** all options contracts with:
- Opening date 30–180 days ago
- Original DTE at opening ≥ 90 days
- Premium paid ≥ $500K
- V/OI at opening indicated new position (≥ 3:1)

**Features for activation classifier:**
1. Days since opening
2. Current DTE remaining
3. Stock move since opening (% toward bet strike)
4. OI retention (% of original OI still open)
5. Days to nearest catalyst (earnings, FDA, macro)
6. Today's flow alignment with bet direction (binary)
7. IV rank today vs IV rank at opening
8. Price proximity to gamma flip / walls
9. Sector regime (short-gamma / long-gamma)
10. Baseline ticker volatility

**Model:** sklearn gradient boosting classifier (or logistic regression for MVP).

**Training data:** backfilled historical options data. Labels: did the stock move ≥ 15% in bet direction within 30 days of catalyst? MVP can use rule-based scoring until we have training data.

**Firing condition:** activation probability ≥ 0.6.

**Data source (hardest):**
- MVP: [historicaloptiondata.com](https://historicaloptiondata.com/) — cheap paid bootstrap for ~1 year of history
- Alternative: scrape OptionStrat historical flow archives
- Long-term: Polygon Options Historical API

**Why this wins:** no competitor does this. It's the hardest data problem but the highest differentiation.

---

## Factor 5 — Catalyst + Novelty Sentiment (`sentiment.py`)

**Part A — Catalyst proximity:**
- Earnings date within 30 days
- Known macro events (Fed, CPI, NFP, FDA PDUFA)
- Ex-dividend, conference, product launch from EDGAR / Finnhub calendar

**Part B — Novelty-weighted sentiment:**
- Fetch news from Alpha Vantage + Finnhub + (optional) RSS sources
- Embed each article with sentence-transformers `all-MiniLM-L6-v2`
- Build rolling 30-day baseline embedding centroid per ticker
- For each new article: novelty = `1 - cosine_similarity(article_embedding, baseline_centroid)`
- Novelty z-score = (novelty - mean_novelty_90d) / std_novelty_90d
- Sentiment score (direction): FinBERT or Claude classification

**LLM filter:** before scoring, filter out noise (analyst rating reshuffles, dividend announcements, boilerplate) using LLM. Only material items are scored.

**Firing condition:**
- Catalyst within 30 days AND novelty z ≥ 1.5 AND sentiment direction aligns with pick direction
- OR catalyst within 7 days regardless of sentiment

**Data source:** Alpha Vantage News & Sentiment API (free tier) + Finnhub news + EDGAR for filings.

---

## Synthesis gate logic (in `synthesis/`)

```python
def qualify_pick(ta: FactorResult, gex: FactorResult, flow: FactorResult,
                 dormant: FactorResult, sentiment: FactorResult) -> bool:
    # Hard gates
    if not ta.firing or not gex.firing:
        return False
    # Need at least 2 of remaining 3
    remaining = sum([flow.firing, dormant.firing, sentiment.firing])
    return remaining >= 2

def conviction(factors: list[FactorResult]) -> int:
    # 1-5 based on count + strengths
    firing_count = sum(f.firing for f in factors)
    avg_strength = mean(f.strength for f in factors if f.firing)
    return min(5, firing_count + round(avg_strength))
```

Synthesis output is ranked by conviction descending, then by dormant-bet activation (bonus for differentiator), then by IV rank (cheaper vol = better R:R).

Output: **top 3–5** qualified picks per daily scan.
