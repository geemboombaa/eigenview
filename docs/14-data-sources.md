# Data Sources — what feeds each signal, and from where

Living document. Update whenever a source is added, changed, or breaks.
Last updated: 2026-05-29 (macro-sources rebuild — `fix/macro-sources`).

## Principles
- **Free + self-owned over paid + scraped.** Prefer public files/APIs and native computation over third-party scrapes that break or get paywalled.
- **No fake data.** A source that fails writes NULL → the consuming factor returns `NO DATA` (honest), never a guessed value.
- **Document proxies.** Where a free proxy substitutes for a paid/literal series (e.g. VIX constant-maturity indices vs VX futures), say so explicitly here.

---

## Macro regime (Gate 0) — `data/macro.py` → `macro_daily`, scored in `factors/macro_regime.py`

Regime score 0–10. Thresholds: GREEN ≥7, RED ≤3 (`config.py`). RED blocks long picks.

| Signal | Pts | Source | Endpoint / method | Key? | Freshness | Notes |
|---|---|---|---|---|---|---|
| **VIX level** (`vix_m1`<20) | +2 | yfinance | `^VIX` daily close | no | daily | Spot VIX (30-day). |
| **VIX contango** (`vix_contango_pct`>0) | +2 | yfinance | `^VIX3M` vs `^VIX`; `contango_pct=(VIX3M−VIX)/VIX×100` | no | daily | **Proxy:** `vix_m2`=`^VIX3M` (3-mo constant-maturity index), not the literal 2nd-month VX future. Standard free term-structure proxy; sign = contango/backwardation. |
| **DIX** (`dix`>0.43) | +3 | FINRA (computed) | Daily short-volume file → dollar-weighted DPI over S&P 500 | no | daily (T-1) | See DIX section below. Native reconstruction of SqueezeMetrics DIX. |
| **GEX** (`gex_index`>0) | +3 | Native (existing chains) | Σ component dealer gamma across S&P 500 chains in DB | no | as of latest chain snapshot | See GEX section. **Aggregate-component** GEX, not SPX-index GEX — documented difference. Stale until chains refresh. |

`spx_breadth_pct` column exists but is **not used** in scoring (legacy from PULSE spec).

### VIX — yfinance constant-maturity indices
- `^VIX` = 30-day implied vol (spot). `^VIX3M` = 93-day. Both are CBOE indices, free via yfinance, no key.
- Replaced the dead VIXCentral HTML scrape (page went JS/ajax-rendered; `var contango_data` regex permanently stale).
- `vix_m1`=^VIX, `vix_m2`=^VIX3M, `vix_m3`=None (no free 6-mo needed for scoring).

### DIX — reconstructed from FINRA, not scraped
- **Why:** SqueezeMetrics DIX page is now paywalled (Signup/Login/Plans); free `hist.json` returns 404.
- **Input:** FINRA Daily Short Sale Volume file — `https://cdn.finra.org/equity/regsho/daily/CNMSshvol{YYYYMMDD}.txt`, free, no key. Pipe-delimited: `Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market`. Walk back from today to the latest published trading day.
- **Formula** (SqueezeMetrics "Short Is Long" white paper): per-stock dark-pool indicator `DPI_i = ShortVolume_i / TotalVolume_i`; dollar-weighted across S&P 500 members →
  `DIX = Σ(close_i × ShortVolume_i) / Σ(close_i × TotalVolume_i)`.
  `close_i` from `prices` table (latest), membership from `universe_membership.in_sp500=1`.
- **Fidelity note:** uses consolidated `CNMS` file. SqueezeMetrics uses the per-TRF (off-exchange) files `FNYX/FNSQ/FNQC`. CNMS is a close approximation; swap to TRF files for exact parity if needed.
- **Ref impl:** github.com/jensolson/Dark-Pool-Buying.

### GEX — native aggregate from option chains we already hold
- **Why:** SqueezeMetrics GEX paywalled; no SPY/SPX chain in DB (only mis-scaled `ES`), and Databento pull is out of scope.
- **Method:** for each S&P 500 member with a gamma-populated chain at the latest `chains.snapshot_date`, run existing `factors/gex.py::score_gex(chain, spot)` → `net_gex`; sum across members; `gex_index = Σ net_gex / 1e9` (billions of $ dealer gamma per 1% move). Spot from latest `prices` close.
- **Difference from SqueezeMetrics:** they measure SPX-index-option GEX; this is **total S&P 500 component** dealer gamma. Both are real dealer-gamma measures; sign (long/short gamma) is the scored signal. Documented, not equivalent.
- **Staleness:** reflects the latest chain snapshot in DB (no live pull). Refreshes when chains are next downloaded.
- **Ref methodology:** SqueezeMetrics 2017 GEX white paper; github.com/jensolson/SPX-Gamma-Exposure.

### COT — CFTC Socrata API (futures module, not Gate 0)
- **Why:** legacy `cftc.gov/dta/public/newcot/deafut.txt` returns 404.
- **Source:** `https://publicreporting.cftc.gov/resource/6dca-aqww.json` (Legacy Futures-Only COT), free, no key.
- **Query:** `$where=upper(market_and_exchange_names) like '%E-MINI S&P 500%'`, `$order=report_date_as_yyyy_mm_dd DESC`, `$limit=1`.
- **Fields:** `noncomm_positions_long_all`, `noncomm_positions_short_all` → `net_long_pct = longs/(longs+shorts)×100`. Writes `cot_weekly`.
- **Note:** `cot_es_net_long_pct` is **not** used in the Gate 0 regime score — feeds the (future) futures module only.

---

## Per-stock factors (Gate 1/2 + soft) — existing, unchanged here
| Factor | File | Source |
|---|---|---|
| Technical (TA) | `factors/technical.py` | `prices` (Databento daily OHLCV) |
| GEX (per-stock) | `factors/gex.py` | `chains` (Databento option chains + computed greeks) |
| Flow | `factors/flow.py` | `chains` (V/OI, premium, side) — dark-pool cluster from spec NOT implemented |
| Dormant | `factors/dormant.py`, `activation.py` | `chains`, `contract_history` (Databento) |
| Sentiment | `factors/sentiment.py` | `news` (Alpha Vantage + Finnhub), `catalysts` |

## News / sentiment (Part-2 rebuild pending — see docs/SESSION-NEXT-AUDIT.md)
| Source | Endpoint | Key? | Limit |
|---|---|---|---|
| Alpha Vantage News & Sentiment | `alphavantage.co` | yes (free) | 25 calls/day |
| Finnhub company news | `finnhub.io` | yes (free) | rate-limited |
- Current scorer = keyword bull/bear counts + catalyst proximity. **Open proposal:** FinBERT/VADER/MiniLM — see Part-2 research (separate doc/section, pending).

## Universe
| List | Source |
|---|---|
| S&P 500 / NDX-100 membership | `data/universe.py` → `universe_membership` table |

## Flow factor — OSS data research (2026-05-29; decision PENDING, build on hold)
The spec's dark-pool-cluster detection has **no free real-time source**:
- **Paid only** for real-time options flow / dark-pool prints: FlowAlgo ($149–199/mo), Unusual
  Whales API, InsiderFinance. GitHub repos (`erikmaday/unusual-whales-mcp`, `SweepCast/Unusual-Options`)
  are **wrappers around these paid APIs**, not free data.
- **Free but delayed:** FINRA ATS / off-exchange weekly (T+1–2 weeks), Quiver Quantitative (limited).
  Swing-usable, not intraday.
- **Already have, free:** our Databento option chains → V/OI, premium, aggressive-side (current
  `factors/flow.py` uses these). The *missing* piece is only the dark-pool **print cluster**.
- **Recommendation:** keep current chain-based flow; the dark-pool cluster either stays descoped
  or uses FINRA-ATS-delayed (swing horizon). No good free real-time option. **User deciding later.**

---

## Known dead / removed sources (do not re-add without checking)
| Source | Status | Replaced by |
|---|---|---|
| VIXCentral HTML scrape | JS-rendered, regex stale | yfinance `^VIX`/`^VIX3M` |
| SqueezeMetrics `hist.json` / DIX page | 404 / paywalled | FINRA-computed DIX, native GEX |
| CFTC `newcot/deafut.txt` | 404 | CFTC Socrata API `6dca-aqww.json` |
