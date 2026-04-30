# 01 — Vision & Differentiators

## The problem

Every options tool today produces *individual factors*. SpotGamma for GEX, Unusual Whales for flow, Alpha Vantage for sentiment, Trade Ideas for technical scans. No product stitches them together into a **curated ready-set-go pick list** with thesis.

Worse, none systematically track the setup where a large bet was placed months ago, nothing happened, and then near catalyst the stock actually moves — the "dormant whale activation" pattern. This exists as occasional substack posts and manual hunts on Unusual Whales, never as a scored factor.

## The product

**EigenView** produces 3–5 curated options trade ideas per day, each with:
- Direction + structure (calls / puts / spreads / calendar)
- LLM-written thesis (why this, why now, what kills it)
- Factor firing report (which of 5 factors aligned, at what magnitude)
- Historical hit rate for the specific pattern
- Trigger price + invalidation price

The user opens the dashboard in the morning and sees the curated feed. No scanning. No configuring. Chat with the AI if anything is unclear.

## The 5 factors

Only picks where **TA + GEX both fire and at least 2 of the remaining 3 align** make the list:

1. **Technical Analysis** — trend + momentum + volatility state + levels + ML pattern classifier
2. **GEX / Dealer positioning** — regime (short/long gamma), call wall, put wall, gamma flip
3. **Options flow quality** — fresh OI, aggressive side, premium size, skew shift
4. **Dormant-bet radar** — ML classifier on large long-dated bets activating
5. **Catalyst + Novelty sentiment** — event proximity + LLM-embedding novelty score

## Differentiators vs. competing products

| Need | EigenView | Tradytics | Unusual Whales | InsiderFinance | SpotGamma |
|---|---|---|---|---|---|
| Options flow | ✓ | ✓ | ✓✓ | ✓ | — |
| Dark pool | Planned | ✓ | ✓ | ✓ | — |
| GEX / dealer | ✓ | partial | partial | partial | ✓✓ |
| Technical analysis | ✓ (integrated) | ✓ (separate) | — | ✓ | — |
| News sentiment | ✓ (novelty-weighted) | — | partial | ✓ | — |
| **Dormant-bet radar** | ✓✓ (only us) | — | — | — | — |
| **Curated pick list** | ✓✓ | partial (Trady Flow) | — | partial (Top Tickers) | — |
| **LLM thesis per pick** | ✓✓ (only us) | — | — | — | — |
| Multi-factor gate logic | ✓✓ (only us) | — | — | — | — |

## What we don't do (by design)

- No raw data dashboards with filter panels
- No "build your own scanner"
- No backtesting (v1)
- No execution / broker integration (v1)
- No real-time tick streaming (v1 — end-of-day scoring on 15-min delayed data)
- No crypto, futures, FX (US equities/options only)

## Success criteria for v1

1. Daily run produces 3–5 picks automatically
2. Each pick has a coherent LLM thesis a trader can act on
3. Dormant-bet radar surfaces at least one activation per week with plausible reasoning
4. Dashboard renders in <2s on local machine
5. User can ask the AI "why this pick?" and get a genuinely useful answer
6. Five preset templates + custom canvas work
7. Theme toggle works
