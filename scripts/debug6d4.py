import os
os.environ['PYTHONUTF8'] = '1'
import sys
sys.path.insert(0, r'C:\Users\v_per\Claude\Projects\Eigenview\src')
import numpy as np
import pandas as pd
import pandas_ta as ta
from eigenview.factors.technical import detect_pattern

np.random.seed(99)
n = 150
prices = 100 + np.random.randn(n) * 1.5
prices[-2] = 100.0
prices[-1] = 122.0
opens = prices.copy()
opens[-1] = 120.0
dates = pd.date_range("2021-01-01", periods=n, freq="B")
highs = np.maximum(opens, prices) * 1.015
lows  = np.minimum(opens, prices) * 0.985
daily = pd.DataFrame({'open': opens, 'high': highs, 'low': lows, 'close': prices, 'volume': np.ones(n)*1e6}, index=pd.DatetimeIndex(dates))

w_close = np.linspace(85, 105, 30)
w_dates = pd.date_range("2021-01-01", periods=30, freq="W-FRI")
weekly = pd.DataFrame({'open': w_close, 'high': w_close*1.02, 'low': w_close*0.98, 'close': w_close, 'volume': np.ones(30)*5e6}, index=pd.DatetimeIndex(w_dates))

r = detect_pattern(daily, weekly)
print(f"Pattern: {r['pattern']}, Confidence: {r['confidence']}")
print(f"weekly_state: {r['detail'].get('weekly_state')}")

# Manual BB check
ddf = daily.copy()
ddf.index = ddf.index.tz_localize(None)
ddf.ta.bbands(length=20, append=True)
ddf.ta.adx(length=14, append=True)
ddf.ta.rsi(length=14, append=True)

last = ddf.iloc[-1]
bbu_key = "BBU_20_2.0_2.0" if "BBU_20_2.0_2.0" in ddf.columns else "BBU_20_2.0"
bbl_key = "BBL_20_2.0_2.0" if "BBL_20_2.0_2.0" in ddf.columns else "BBL_20_2.0"
bbu = float(last.get(bbu_key, float('nan')))
bbl = float(last.get(bbl_key, float('nan')))
adx = float(last.get('ADX_14', float('nan')))
rsi = float(last.get('RSI_14', float('nan')))
print(f"Close={prices[-1]:.2f}, BBU={bbu:.2f}, BBL={bbl:.2f}")
print(f"ADX={adx:.2f}, RSI={rsi:.2f}")
print(f"close >= BBU * 0.995: {prices[-1]} >= {bbu*0.995:.2f}? {prices[-1] >= bbu * 0.995}")

adx_arr = ddf['ADX_14'].dropna().tail(63).values
adx_p35 = max(20.0, float(np.percentile(adx_arr, 35)) if len(adx_arr) >= 10 else 20.0)
rsi_arr = ddf['RSI_14'].dropna().tail(63).values
rsi_p70 = float(np.percentile(rsi_arr, 70)) if len(rsi_arr) >= 10 else 65.0
print(f"ADX p35 (floored)={adx_p35:.2f}, ADX < p35? {adx < adx_p35}")
print(f"RSI p70={rsi_p70:.2f}, RSI > p70? {rsi > rsi_p70}")

# What weekly state
from eigenview.factors.technical import _classify_weekly_state
as_of = ddf.index[-1]
wdf_filt = weekly.copy()
wdf_filt.index = wdf_filt.index.tz_localize(None) if wdf_filt.index.tz else wdf_filt.index
ws = _classify_weekly_state(weekly, as_of)
print(f"weekly_state: {ws}")
print(f"weekly_state not in BEARISH_STRONG/BULLISH_EXTENDED? {ws not in ('BEARISH_STRONG', 'BULLISH_EXTENDED')}")

# What about the BB key in detect_pattern?
print()
print("BB cols in ddf:", [c for c in ddf.columns if 'BB' in c])
