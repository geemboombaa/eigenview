import os
os.environ['PYTHONUTF8'] = '1'
import sys
sys.path.insert(0, r'C:\Users\v_per\Claude\Projects\Eigenview\src')
import numpy as np
import pandas as pd
import pandas_ta as ta
from eigenview.factors.technical import detect_pattern

# ── Debug BB MR long ──────────────────────────────────────────────────────
print("=== BB MR Long fixture debug ===")
np.random.seed(42)
n = 150
prices = 100 + np.random.randn(n) * 0.3
prices[-10] = 98.0
prices[-9]  = 96.0
prices[-8]  = 94.5
prices[-7]  = 93.0
prices[-6]  = 91.5
prices[-5]  = 90.5
prices[-4]  = 89.5
prices[-3]  = 88.5
prices[-2]  = 87.5
prices[-1]  = 86.5
opens = prices.copy()
opens[-1] = 87.5

dates = pd.date_range("2021-01-01", periods=n, freq="B")
highs = np.maximum(opens, prices) * 1.015
lows  = np.minimum(opens, prices) * 0.985
daily = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': prices, 'volume': np.ones(n)*1e6}, index=pd.DatetimeIndex(dates))

np.random.seed(42)
w_close = 100 + np.random.randn(25) * 0.5
w_dates = pd.date_range("2021-01-01", periods=25, freq="W-FRI")
weekly = pd.DataFrame({'open': w_close, 'high': w_close*1.02, 'low': w_close*0.98, 'close': w_close, 'volume': np.ones(25)*5e6}, index=pd.DatetimeIndex(w_dates))

r = detect_pattern(daily, weekly)
print(f"Pattern: {r['pattern']}, Confidence: {r['confidence']}")
print(f"weekly_state: {r['detail'].get('weekly_state')}")
print(f"Detail extra keys: {[k for k in r['detail'] if k not in ('trend','weekly_trend','weekly_state','rsi','rsi_p40','adx','vol_ratio','swing_low','swing_high')]}")

# What BB values would be for this data?
ddf = daily.copy()
ddf.index = ddf.index.tz_localize(None)
ddf.ta.bbands(length=20, append=True)
ddf.ta.adx(length=14, append=True)
ddf.ta.rsi(length=14, append=True)
bbl_key = "BBL_20_2.0_2.0" if "BBL_20_2.0_2.0" in ddf.columns else "BBL_20_2.0"
bbu_key = "BBU_20_2.0_2.0" if "BBU_20_2.0_2.0" in ddf.columns else "BBU_20_2.0"
bbl = float(ddf.iloc[-1].get(bbl_key, float('nan')))
bbu = float(ddf.iloc[-1].get(bbu_key, float('nan')))
adx = float(ddf.iloc[-1].get('ADX_14', float('nan')))
rsi = float(ddf.iloc[-1].get('RSI_14', float('nan')))
print(f"Close={prices[-1]:.2f}, BBL={bbl:.2f}, BBU={bbu:.2f}")
print(f"ADX={adx:.2f}, RSI={rsi:.2f}")
adx_p35 = max(20.0, float(np.percentile(ddf['ADX_14'].dropna().tail(63).values, 35)))
rsi_p30 = float(np.percentile(ddf['RSI_14'].dropna().tail(63).values, 30))
print(f"ADX p35={adx_p35:.2f} (floored at 20), RSI p30={rsi_p30:.2f}")
print(f"close <= BBL*1.005: {prices[-1]} <= {bbl*1.005:.2f}? {prices[-1] <= bbl*1.005}")
print(f"ADX < p35: {adx:.2f} < {adx_p35:.2f}? {adx < adx_p35}")
print(f"RSI < p30: {rsi:.2f} < {rsi_p30:.2f}? {rsi < rsi_p30}")

print()
print("=== EMA200 snap long debug ===")
n2 = 350
prices2 = np.zeros(n2)
prices2[:300] = 100.0
prices2[300:348] = np.linspace(100, 78, 48)
prices2[348] = 77.0
prices2[349] = 80.0
opens2 = prices2.copy()
opens2[349] = 77.5
highs2 = np.maximum(opens2, prices2) * 1.01
lows2  = np.minimum(opens2, prices2) * 0.99
vols2  = np.full(n2, 1_000_000, dtype=float)
dates2 = pd.date_range("2020-01-01", periods=n2, freq="B")
daily2 = pd.DataFrame({'open': opens2, 'high': highs2, 'low': lows2, 'close': prices2, 'volume': vols2}, index=pd.DatetimeIndex(dates2))

w_n = 80
w_close2 = np.zeros(w_n)
w_close2[:65] = 100.0
w_close2[65:] = np.linspace(100, 72, 15)
w_dates2 = pd.date_range("2020-01-01", periods=w_n, freq="W-FRI")
weekly2 = pd.DataFrame({'open': w_close2, 'high': w_close2*1.02, 'low': w_close2*0.98, 'close': w_close2, 'volume': np.ones(w_n)*5e6}, index=pd.DatetimeIndex(w_dates2))

r2 = detect_pattern(daily2, weekly2)
print(f"Pattern: {r2['pattern']}, Confidence: {r2['confidence']}")
print(f"weekly_state: {r2['detail'].get('weekly_state')}")

# compute EMA200, ADX, weekly RSI manually
ddf2 = daily2.copy()
ddf2.index = ddf2.index.tz_localize(None)
ddf2.ta.ema(length=200, append=True)
ddf2.ta.adx(length=14, append=True)
ema200 = float(ddf2['EMA_200'].iloc[-1])
adx2 = float(ddf2['ADX_14'].iloc[-1])
close2 = float(ddf2['close'].iloc[-1])
deviation = (close2 / ema200 - 1) * 100
print(f"EMA200={ema200:.3f}, Close={close2:.3f}, Deviation={deviation:.2f}%")
print(f"ADX={adx2:.2f}")

adx_p40 = float(np.percentile(ddf2['ADX_14'].dropna().tail(63).values, 40))
print(f"ADX p40={adx_p40:.2f}, ADX > p40? {adx2 > adx_p40}")
print(f"Up day? close={close2} > open={opens2[-1]}? {close2 > opens2[-1]}")

# Weekly RSI
wdf2 = weekly2.copy()
wdf2.index = wdf2.index.tz_localize(None)
as_of = ddf2.index[-1]
wdf2_filt = wdf2[wdf2.index <= as_of].copy()
wdf2_filt.ta.rsi(length=14, append=True)
wkly_rsi2 = wdf2_filt.iloc[-1].get('RSI_14')
print(f"Weekly RSI: {wkly_rsi2}")
print(f"Weekly RSI < 35? {wkly_rsi2 < 35.0 if wkly_rsi2 is not None else 'N/A'}")

# What's the weekly_state for ema200 data?
from eigenview.factors.technical import _classify_weekly_state
ws2 = _classify_weekly_state(weekly2, as_of)
print(f"weekly_state via _classify_weekly_state: {ws2}")
