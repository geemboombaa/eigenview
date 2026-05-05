import os
os.environ['PYTHONUTF8'] = '1'
import sys
sys.path.insert(0, r'C:\Users\v_per\Claude\Projects\Eigenview\src')
import numpy as np
import pandas as pd
from eigenview.factors.technical import detect_pattern

# ── Debug CHoCH bullish: why does bos_bearish fire first? ──────────────────
print("=== CHoCH Bullish vs BOS Bearish order issue ===")
n = 150
prices = np.zeros(n)
prices[0:20]   = np.linspace(100, 85, 20)
prices[20:30]  = np.linspace(85, 92, 10)
prices[30:50]  = np.linspace(92, 78, 20)
prices[50:60]  = np.linspace(78, 86, 10)
prices[60:80]  = np.linspace(86, 72, 20)
prices[80:90]  = np.linspace(72, 80, 10)
prices[90:110] = np.linspace(80, 66, 20)
prices[110:120]= np.linspace(66, 95, 10)
prices[120:150]= np.linspace(95, 105, 30)

dates = pd.date_range("2021-01-01", periods=n, freq="B")
opens = prices.copy()
highs = np.maximum(opens, prices) * 1.015
lows  = np.minimum(opens, prices) * 0.985
daily = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': prices, 'volume': np.ones(n)*1e6}, index=pd.DatetimeIndex(dates))

# Weekly: bearish_weak
w_close = np.linspace(100, 70, 25)
w_dates = pd.date_range("2021-01-01", periods=25, freq="W-FRI")
weekly = pd.DataFrame({'open': w_close, 'high': w_close*1.02, 'low': w_close*0.98, 'close': w_close, 'volume': np.ones(25)*5e6}, index=pd.DatetimeIndex(w_dates))

r = detect_pattern(daily, weekly)
print(f"Pattern: {r['pattern']}, Confidence: {r['confidence']}")
print(f"weekly_state: {r['detail'].get('weekly_state')}")
print(f"detail keys: {list(r['detail'].keys())}")

# ── Debug EMA200 snap long ──────────────────────────────────────────────────
print()
print("=== EMA200 snap long debug ===")
n2 = 250
prices2 = np.zeros(n2)
prices2[:200] = np.linspace(80, 120, 200)
prices2[200:248] = np.linspace(120, 88, 48)
prices2[248] = 87.0
prices2[249] = 90.0
opens2 = prices2.copy()
opens2[249] = 87.5
highs2 = np.maximum(opens2, prices2) * 1.01
lows2  = np.minimum(opens2, prices2) * 0.99
vols2  = np.full(n2, 1_000_000, dtype=float)
dates2 = pd.date_range("2020-01-01", periods=n2, freq="B")
daily2 = pd.DataFrame({'open': opens2, 'high': highs2, 'low': lows2, 'close': prices2, 'volume': vols2}, index=pd.DatetimeIndex(dates2))

w_n = 60
w_close2 = np.zeros(w_n)
w_close2[:50] = np.linspace(80, 120, 50)
w_close2[50:] = np.linspace(120, 85, 10)
w_dates2 = pd.date_range("2020-01-01", periods=w_n, freq="W-FRI")
weekly2 = pd.DataFrame({'open': w_close2, 'high': w_close2*1.02, 'low': w_close2*0.98, 'close': w_close2, 'volume': np.ones(w_n)*5e6}, index=pd.DatetimeIndex(w_dates2))

r2 = detect_pattern(daily2, weekly2)
print(f"Pattern: {r2['pattern']}, Confidence: {r2['confidence']}")
print(f"weekly_state: {r2['detail'].get('weekly_state')}")
print(f"adx: {r2['detail'].get('adx')}")
print(f"rsi: {r2['detail'].get('rsi')}")

# Now manually compute EMA200
import pandas_ta as ta
ddf2 = daily2.copy()
ddf2.index = ddf2.index.tz_localize(None)
ddf2.ta.ema(length=200, append=True)
ddf2.ta.adx(length=14, append=True)
ema200_val = float(ddf2['EMA_200'].iloc[-1])
adx_val = float(ddf2['ADX_14'].iloc[-1])
close_val = float(ddf2['close'].iloc[-1])
print(f"EMA200={ema200_val:.3f}, Close={close_val:.3f}")
print(f"Deviation: {(close_val/ema200_val - 1)*100:.2f}%")
print(f"ADX={adx_val:.2f}")

# ADX p40
adx_series = ddf2['ADX_14'].dropna().tail(63).values
adx_p40 = float(np.percentile(adx_series, 40)) if len(adx_series) >= 10 else 20.0
print(f"ADX p40={adx_p40:.2f}, ADX > p40? {adx_val > adx_p40}")

# Weekly RSI
wdf2 = weekly2.copy()
wdf2.index = wdf2.index.tz_localize(None)
as_of = ddf2.index[-1]
wdf2_filt = wdf2[wdf2.index <= as_of].copy()
wdf2_filt.ta.rsi(length=14, append=True)
wkly_rsi = wdf2_filt.iloc[-1].get('RSI_14')
print(f"Weekly RSI: {wkly_rsi}")

# Up day check
print(f"Up day: close={close_val} > open={opens2[-1]}? {close_val > opens2[-1]}")

# What pattern fired?
print(f"Full result detail: {r2['detail']}")
