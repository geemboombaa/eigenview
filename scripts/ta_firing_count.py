"""Phase-A validation: TA firing count across sp500 from DB prices only.

No Databento refresh, no dormant upserts — isolates the swapped TA engine.
Uses the scanner's own _score_with_lookback for apples-to-apples vs old 342/504.
"""
import asyncio
from collections import Counter

from eigenview.data.universe import get_universe
from eigenview.synthesis.scanner import _fetch_live, _score_with_lookback


async def main() -> None:
    tickers = await get_universe("sp500")
    total = 0
    fired = 0
    longs = 0
    shorts = 0
    labels: Counter[str] = Counter()
    for t in tickers:
        df = await _fetch_live(t)
        if df is None or df.empty or len(df) < 30:
            continue
        total += 1
        r = _score_with_lookback(df, t)
        if r.firing:
            fired += 1
            labels[r.label] += 1
            if r.detail.get("direction") == "short":
                shorts += 1
            else:
                longs += 1
    print(f"\nTA FIRED {fired}/{total}  (longs={longs}  shorts={shorts})")
    print("by setup:")
    for lab, c in labels.most_common():
        print(f"  {lab:24s} {c}")


if __name__ == "__main__":
    asyncio.run(main())
