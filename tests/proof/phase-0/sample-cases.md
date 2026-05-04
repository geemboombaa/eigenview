# Sample Cases — 2026-05-04

Data pulled via yfinance. Indicators computed via pandas_ta. All values are from real market data.

---

## Case 1: pullback_in_trend — NVDA 2024-04-16 (FIRE)

- close: $87.37
- EMA21: $87.66
- price vs EMA21: -0.33% (hugging EMA21 from below — textbook pullback touch)
- RSI: 51.1 (in range 38–57)
- ADX: 27.6 (>=15 — trend is active)
- vol_ratio: 0.80 (<1.5 — quiet pullback, no panic)
- **VERDICT: QUALIFIES** — all four conditions pass cleanly

Notes: NVDA was in a confirmed uptrend after the Jan–Mar 2024 AI rally. The April pullback brought price back to EMA21 with subdued volume and mid-range RSI. Strong candidate for pullback_in_trend classification.

---

## Case 1 anti: pullback_in_trend — NVDA 2024-01-04 (NO FIRE)

- close: $47.97
- RSI: 48.4 (mid-range — not a problem by itself)
- ADX: 14.5 (below 15 — no active trend, price is in compression/consolidation)
- **VERDICT: CORRECTLY EXCLUDED** — ADX gate fails; this is compression, not a trend pullback

Notes: Early January 2024 NVDA was coiled before the breakout. ADX 14.5 correctly identifies the absence of trend — a pullback_in_trend label here would be wrong. This is the anti-case.

---

## Case 2: compression_break — META 2023-04-27 (FIRE)

- close: $236.70
- prev close: $207.77
- price change on break day: +13.93% (earnings-driven gap + continuation)
- BB width on break day: 0.1226
- BB width percentile (day before): 0.074 (bottom 7.4% — extreme squeeze)
- vol_ratio: 3.13 (3x average volume — strong institutional participation)
- RSI: 74.5 (momentum confirming breakout direction)
- ADX: 41.1 (trend accelerating rapidly post-break)
- **VERDICT: QUALIFIES** — squeeze confirmed (prior BB width_pct = 0.074), vol surge = 3.13x, clean upside break

Squeeze period context (5 trading days before break):

| Date       | Close  | BB Width | vol_ratio |
|------------|--------|----------|-----------|
| 2023-04-20 | 211.41 | 0.1115   | 0.82      |
| 2023-04-21 | 211.23 | 0.1056   | 0.91      |
| 2023-04-24 | 211.13 | 0.1013   | 0.83      |
| 2023-04-25 | 205.93 | 0.0941   | 1.01      |
| 2023-04-26 | 207.77 | 0.0782   | 2.08      |

Notes: META reported Q1 2023 earnings on 2023-04-26 after close, with the break occurring on 2023-04-27. The 5-day squeeze (bands narrowing from 0.1115 to 0.0782) is clearly visible. The break day vol at 3.13x confirms conviction. This is a clean, verifiable compression_break example with real data.

---

## Case 3: bullish_reversal — QQQ 2022-10-13 (FIRE)

- close: $263.10 (intraday low: $248.85 — massive intraday reversal)
- price change: +2.35% (closed well off the lows)
- RSI: 39.5 (recovering from oversold — prior day RSI was 32.6)
- RSI divergence: price made lower low (257.07 → 248.85 intraday), RSI made higher low (32.55 → 39.5) — textbook positive divergence
- vol_ratio: 1.63 (elevated volume on the reversal candle)
- ADX: 36.5 (strong prior downtrend — exhaustion reversal context)
- **VERDICT: QUALIFIES** — RSI divergence confirmed, vol elevated, price closed strongly above open

Swing low context (5 trading days before):

| Date       | Close  | Low    | RSI  | vol_ratio |
|------------|--------|--------|------|-----------|
| 2022-10-06 | 273.80 | 273.48 | 43.3 | 0.81      |
| 2022-10-07 | 263.37 | 262.04 | 36.2 | 1.07      |
| 2022-10-10 | 260.74 | 258.03 | 34.6 | 0.89      |
| 2022-10-11 | 257.16 | 255.47 | 32.6 | 0.99      |
| 2022-10-12 | 257.07 | 256.37 | 32.6 | 0.76      |
| 2022-10-13 | 263.10 | 248.85 | 39.5 | 1.63      |

Notes: This is the famous October 2022 CPI reversal day. QQQ opened down hard on a hot CPI print, hit 248.85 intraday (new bear market low), then reversed and closed at 263.10. RSI made a higher reading (39.5) while price made a lower low (248.85 vs prior lows) — a clear positive divergence. Vol at 1.63x confirmed institutional accumulation. This day marked the Q4 2022 relief rally. Ideal bullish_reversal specimen.

---

## Summary Table

| Case | Ticker | Date | Pattern | RSI | ADX | vol_ratio | BB_pct_prior | Qualifies |
|------|--------|------|---------|-----|-----|-----------|--------------|-----------|
| 1 | NVDA | 2024-04-16 | pullback_in_trend | 51.1 | 27.6 | 0.80 | — | YES |
| 1-anti | NVDA | 2024-01-04 | (compression) | 48.4 | 14.5 | — | — | NO (ADX<15) |
| 2 | META | 2023-04-27 | compression_break | 74.5 | 41.1 | 3.13 | 0.074 | YES |
| 3 | QQQ | 2022-10-13 | bullish_reversal | 39.5 | 36.5 | 1.63 | — | YES |
