import sqlite3
conn = sqlite3.connect("data/eigenview.db")
cur = conn.cursor()
tables = ["prices","chains","news","catalysts","macro_daily","cot_weekly",
          "picks","forward_returns","signal_triggers","factor_scores","dormant_bets","llm_log"]
print("\n[DB ROW COUNTS]")
for t in tables:
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t}: {n:,}")
    except Exception as e:
        print(f"  {t}: ERROR - {e}")
conn.close()
