"""Read-only Databento cost estimate for corrected-scope EigenView pull.

No data is downloaded. Uses metadata.get_cost (free) per stream.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys
from pathlib import Path

import databento as db

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def load_key() -> str:
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DATABENTO_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("DATABENTO_KEY not in .env")


def get_tickers() -> list[str]:
    from eigenview.data.universe import get_universe

    sp = asyncio.run(get_universe("sp500"))
    ndx = asyncio.run(get_universe("ndx100"))
    return sorted(set(sp) | set(ndx))


def clamp_start(requested: dt.date, avail_start: str) -> str:
    a = dt.date.fromisoformat(avail_start[:10])
    return max(requested, a).isoformat()


def main() -> None:
    client = db.Historical(load_key())
    tickers = get_tickers()
    opt_syms = [f"{t}.OPT" for t in tickers]
    print(f"universe: {len(tickers)} tickers\n")

    today = dt.date.today()
    four_yr = today - dt.timedelta(days=365 * 4)
    ninety_d = today - dt.timedelta(days=90)

    streams = [
        ("EQUS.MINI", "ohlcv-1d", "raw_symbol", tickers, four_yr),
        ("EQUS.MINI", "ohlcv-1h", "raw_symbol", tickers, ninety_d),
        ("OPRA.PILLAR", "definition", "parent", opt_syms, four_yr),
        ("OPRA.PILLAR", "statistics", "parent", opt_syms, four_yr),
        ("OPRA.PILLAR", "ohlcv-1d", "parent", opt_syms, four_yr),
    ]

    total = 0.0
    for ds, schema, stype, syms, start_req in streams:
        try:
            rng = client.metadata.get_dataset_range(dataset=ds)
            avail_start = rng["start"]
            avail_end = rng["end"]
            start = clamp_start(start_req, avail_start)
            end = avail_end[:10]
            cost = client.metadata.get_cost(
                dataset=ds,
                symbols=syms,
                schema=schema,
                start=start,
                end=end,
                stype_in=stype,
            )
            size = client.metadata.get_billable_size(
                dataset=ds,
                symbols=syms,
                schema=schema,
                start=start,
                end=end,
                stype_in=stype,
            )
            gb = size / 1e9
            print(f"{ds:14} {schema:11} {start}..{end}  {gb:8.2f} GB  ${cost:9.2f}")
            total += cost
        except Exception as exc:  # noqa: BLE001
            print(f"{ds:14} {schema:11} ERROR: {exc}")

    print(f"\nGRAND TOTAL: ${total:.2f}  (free credit: $125)")


if __name__ == "__main__":
    main()
