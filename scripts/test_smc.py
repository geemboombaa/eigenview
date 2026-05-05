import os
os.environ['PYTHONUTF8'] = '1'
import pandas as pd
import numpy as np
import smartmoneyconcepts.smc as smc_mod

n = 150
dates = pd.date_range('2022-01-01', periods=n, freq='D')
prices = np.zeros(n)
prices[0:20] = np.linspace(100, 85, 20)
prices[20:30] = np.linspace(85, 92, 10)
prices[30:50] = np.linspace(92, 78, 20)
prices[50:60] = np.linspace(78, 86, 10)
prices[60:80] = np.linspace(86, 72, 20)
prices[80:90] = np.linspace(72, 80, 10)
prices[90:110] = np.linspace(80, 66, 20)
prices[110:120] = np.linspace(66, 95, 10)
prices[120:150] = np.linspace(95, 105, 30)
highs = prices * 1.015
lows  = prices * 0.985
opens = np.roll(prices, 1); opens[0] = prices[0]
df = pd.DataFrame(
    {'open': opens, 'high': highs, 'low': lows, 'close': prices, 'volume': np.ones(n)*1e6},
    index=dates
)
shl = smc_mod.swing_highs_lows(df, swing_length=10)
bc = smc_mod.bos_choch(df, shl, close_break=True)

print("All non-NaN rows in bc:")
mask = bc['BOS'].notna() | bc['CHOCH'].notna()
print(bc[mask])
print()
print("SHL non-null positions:")
shl_nn = shl.dropna()
for i, (idx, row) in enumerate(shl_nn.iterrows()):
    print(f"  SHL[{i}]: df_idx={idx}, HighLow={row['HighLow']}, Level={row['Level']:.3f}")

# Now test if the detect approach can work: look for any CHoCH/BOS signal in last N bars
print()
recent_bc = bc.iloc[-30:]
recent_choch_bull = recent_bc['CHOCH'].eq(1).any()
recent_choch_bear = recent_bc['CHOCH'].eq(-1).any()
recent_bos_bull   = recent_bc['BOS'].eq(1).any()
recent_bos_bear   = recent_bc['BOS'].eq(-1).any()
print(f"Last 30 bars: CHOCH_bull={recent_choch_bull}, CHOCH_bear={recent_choch_bear}")
print(f"Last 30 bars: BOS_bull={recent_bos_bull}, BOS_bear={recent_bos_bear}")

# Also check entire dataframe
print()
print("Full df - any CHoCH bull:", bc['CHOCH'].eq(1).any())
print("Full df - any CHOCH bear:", bc['CHOCH'].eq(-1).any())
print("Full df - any BOS bull:", bc['BOS'].eq(1).any())
print("Full df - any BOS bear:", bc['BOS'].eq(-1).any())

# What BrokenIndex values are there?
print()
print("BrokenIndex values:", bc['BrokenIndex'].dropna().values)
print("CHoCH values:", bc['CHOCH'].dropna().values)
print("BOS values:", bc['BOS'].dropna().values)

# Find the rows
mask2 = bc['CHOCH'].notna()
print("CHOCH non-null indices:", bc[mask2].index.tolist())
mask3 = bc['BOS'].notna()
print("BOS non-null indices:", bc[mask3].index.tolist())
