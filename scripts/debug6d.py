import os
os.environ['PYTHONUTF8'] = '1'
import numpy as np
import pandas as pd
import smartmoneyconcepts.smc as smc_mod

# ── Debug CHoCH bullish fixture ─────────────────────────────────────────────
print("=== CHoCH Bullish Debug ===")
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
df = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': prices, 'volume': np.ones(n)*1e6}, index=dates)

shl = smc_mod.swing_highs_lows(df, swing_length=10)
bc = smc_mod.bos_choch(df, shl, close_break=True)

print("SHL non-null:")
print(shl.dropna())
print()
mask = bc['BOS'].notna() | bc['CHOCH'].notna()
print("BC non-null:")
print(bc[mask])
print()
# Check BrokenIndex values
print("BrokenIndex values:", bc['BrokenIndex'].dropna().values)
print("n =", n, "so last 30 bars = bars 120-149")
print()

# What's the situation at BrokenIndex values?
bi_vals = bc['BrokenIndex'].dropna().values
print("BrokenIndex >= n-30 =", n-30, "?")
for biv in bi_vals:
    print(f"  BrokenIndex={biv}: in last 30? {biv >= n-30}")

print()
print("=== BB Mean Reversion Debug ===")
np.random.seed(42)
n2 = 150
prices2 = 100 + np.random.randn(n2) * 2.0
prices2[-3] = 92.0
prices2[-2] = 89.0
prices2[-1] = 87.0
opens2 = prices2.copy()
opens2[-1] = 88.0

dates2 = pd.date_range("2021-01-01", periods=n2, freq="B")
highs2 = np.maximum(opens2, prices2) * 1.015
lows2  = np.minimum(opens2, prices2) * 0.985
df2 = pd.DataFrame({'open': opens2, 'high': highs2, 'low': lows2, 'close': prices2, 'volume': np.ones(n2)*1e6}, index=dates2)

import pandas_ta as ta
df2.ta.bbands(length=20, append=True)
df2.ta.adx(length=14, append=True)
df2.ta.rsi(length=14, append=True)

last2 = df2.iloc[-1]
print("Close[-1]:", prices2[-1])
print("BBL cols:", [c for c in df2.columns if 'BBL' in c])
print("BBU cols:", [c for c in df2.columns if 'BBU' in c])
bbl_key = "BBL_20_2.0_2.0" if "BBL_20_2.0_2.0" in df2.columns else "BBL_20_2.0"
bbu_key = "BBU_20_2.0_2.0" if "BBU_20_2.0_2.0" in df2.columns else "BBU_20_2.0"
bbl = float(last2.get(bbl_key, float('nan')))
bbu = float(last2.get(bbu_key, float('nan')))
print(f"BBL={bbl:.3f}, BBU={bbu:.3f}")
print(f"Close <= BBL * 1.005: {prices2[-1]} <= {bbl * 1.005}? {prices2[-1] <= bbl * 1.005}")

adx_val = float(last2.get('ADX_14', float('nan')))
rsi_val = float(last2.get('RSI_14', float('nan')))
print(f"ADX={adx_val:.2f}, RSI={rsi_val:.2f}")

# ADX p35
adx_series = df2['ADX_14'].dropna().tail(63).values
adx_p35 = float(np.percentile(adx_series, 35)) if len(adx_series) >= 10 else 20.0
print(f"ADX_p35={adx_p35:.2f}, ADX < p35? {adx_val < adx_p35}")

# RSI p30
rsi_series2 = df2['RSI_14'].dropna().tail(63).values
rsi_p30 = float(np.percentile(rsi_series2, 30)) if len(rsi_series2) >= 10 else 35.0
print(f"RSI_p30={rsi_p30:.2f}, RSI < p30? {rsi_val < rsi_p30}")

print()
print("=== What detect_pattern returns for BB MR ===")
import sys
sys.path.insert(0, r'C:\Users\v_per\Claude\Projects\Eigenview\src')
from eigenview.factors.technical import detect_pattern

np.random.seed(42)
prices2r = 100 + np.random.randn(n2) * 2.0
prices2r[-3] = 92.0
prices2r[-2] = 89.0
prices2r[-1] = 87.0
opens2r = prices2r.copy()
opens2r[-1] = 88.0
dates2r = pd.date_range("2021-01-01", periods=n2, freq="B")
highs2r = np.maximum(opens2r, prices2r) * 1.015
lows2r  = np.minimum(opens2r, prices2r) * 0.985
daily2r = pd.DataFrame({'open': opens2r, 'high': highs2r, 'low': lows2r, 'close': prices2r, 'volume': np.ones(n2)*1e6}, index=pd.DatetimeIndex(dates2r))

np.random.seed(42)
w_close2r = 100 + np.random.randn(25) * 1.5
w_dates2r = pd.date_range("2021-01-01", periods=25, freq="W-FRI")
weekly2r = pd.DataFrame({'open': w_close2r, 'high': w_close2r*1.02, 'low': w_close2r*0.98, 'close': w_close2r, 'volume': np.ones(25)*5e6}, index=pd.DatetimeIndex(w_dates2r))

result = detect_pattern(daily2r, weekly2r)
print(f"Pattern: {result['pattern']}, Confidence: {result['confidence']}")
print(f"Detail keys: {list(result['detail'].keys())}")
print(f"weekly_state: {result['detail'].get('weekly_state')}")
print(f"adx: {result['detail'].get('adx')}")
print(f"rsi: {result['detail'].get('rsi')}")
