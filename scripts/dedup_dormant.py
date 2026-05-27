"""
One-time migration: deduplicate dormant_bets and normalize contract naming.

Runs via raw sqlite3 (no async) for speed and to avoid WAL lock contention.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Resolve DB path from env
from eigenview.config import settings
db_url = settings.database_url  # e.g. sqlite+aiosqlite:///data/eigenview.db
db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")

print(f"DB: {db_path}")
conn = sqlite3.connect(db_path, timeout=60)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

# Load all rows
cur.execute("SELECT id, ticker, strike, expiry, call_put, current_oi, original_oi, contract FROM dormant_bets")
rows = cur.fetchall()
print(f"Total rows: {len(rows)}")

# Group by canonical key (ticker, strike, expiry, call_put)
groups: dict[tuple, list] = {}
for r in rows:
    key = (r["ticker"].upper(), float(r["strike"]), r["expiry"], r["call_put"].upper()[:1])
    groups.setdefault(key, []).append(r)

to_delete: list[int] = []
updates: list[tuple[str, int]] = []  # (new_contract, id)

for key, bets in groups.items():
    ticker, strike, expiry, call_put = key
    canonical = f"{ticker}_{expiry}_{int(strike)}{call_put}"

    if len(bets) == 1:
        b = bets[0]
        if b["contract"] != canonical:
            updates.append((canonical, b["id"]))
    else:
        bets_sorted = sorted(
            bets,
            key=lambda x: (-(x["current_oi"] or x["original_oi"] or 0), x["id"])
        )
        keep = bets_sorted[0]
        for drop in bets_sorted[1:]:
            to_delete.append(drop["id"])
        if keep["contract"] != canonical:
            updates.append((canonical, keep["id"]))

print(f"Rows to delete: {len(to_delete)}")
print(f"Rows to rename: {len(updates)}")

# Execute in batches
BATCH = 500

# Renames first (in case deletes would create gaps that confuse SQLite)
for i in range(0, len(updates), BATCH):
    batch = updates[i:i+BATCH]
    cur.executemany("UPDATE dormant_bets SET contract=? WHERE id=?", batch)
    conn.commit()
    if i % 5000 == 0 and i > 0:
        print(f"  renamed {i}/{len(updates)}")

# Deletes in batches
for i in range(0, len(to_delete), BATCH):
    batch = to_delete[i:i+BATCH]
    placeholders = ",".join("?" * len(batch))
    cur.execute(f"DELETE FROM dormant_bets WHERE id IN ({placeholders})", batch)
    conn.commit()
    if i % 5000 == 0 and i > 0:
        print(f"  deleted {i}/{len(to_delete)}")

cur.execute("SELECT COUNT(*) FROM dormant_bets")
remaining = cur.fetchone()[0]
cur.execute("SELECT COUNT(DISTINCT ticker) FROM dormant_bets")
unique_tickers = cur.fetchone()[0]
print(f"Done. Remaining rows: {remaining}, unique tickers: {unique_tickers}")
conn.close()
