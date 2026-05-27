"""
Apply B(2%)+D filter to dormant_bets, run score_bet_v2 on survivors.
No code changes. Analysis only.
"""
from __future__ import annotations

import asyncio
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta

sys.path.insert(0, r"C:\Users\v_per\Claude\Projects\Eigenview\src")

import structlog
structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(40))  # ERROR only

from eigenview.data.storage import AsyncSessionLocal, DormantBet, Chain
from eigenview.factors.dormant import score_bet_v2, percentile_value, dwoi
from sqlalchemy import select


@dataclass
class ProxyChainRow:
    """Proxy chain row built from dormant_bets when real chain data absent."""
    strike: float
    call_put: str
    oi: int | None
    delta: float | None = None
    iv: float | None = None
    expiry: date | None = None


async def main():
    async with AsyncSessionLocal() as session:
        # --- Load all dormant_bets ---
        rows = (await session.execute(select(DormantBet))).scalars().all()
        print(f"Total dormant_bets rows: {len(rows)}")

        # --- Load real chain data (4 tickers) ---
        chain_rows = (await session.execute(select(Chain))).scalars().all()
        real_chains: dict[str, list] = defaultdict(list)
        for c in chain_rows:
            real_chains[c.ticker.upper()].append(c)
        print(f"Tickers with real chain data: {sorted(real_chains.keys())}")

        # --- Deduplicate bets: keep latest per (ticker, contract) ---
        latest: dict[tuple[str, str], DormantBet] = {}
        for b in rows:
            key = (b.ticker.upper(), b.contract)
            existing = latest.get(key)
            if existing is None or b.original_date > existing.original_date:
                latest[key] = b
        bets = list(latest.values())
        print(f"Deduped bets: {len(bets)}")

        # --- Compute spot proxy per ticker (max original_premium / (original_oi * 100 * 0.5 * delta_assume)) ---
        # We'll use a fixed $100 spot for DWOI when delta is None (proxy OI-weighted rank)
        # Actually: use original_premium / (original_oi * 100) as rough spot-normalized premium
        # But for filter we need spot. Use a simple proxy: group by ticker, take max strike as rough spot
        ticker_bets: dict[str, list[DormantBet]] = defaultdict(list)
        for b in bets:
            ticker_bets[b.ticker.upper()].append(b)

        # --- Compute proxy spot per ticker: use ~ATM estimate = median of strikes ---
        ticker_spot: dict[str, float] = {}
        for tk, tbets in ticker_bets.items():
            strikes = [b.strike for b in tbets if b.strike]
            if strikes:
                strikes.sort()
                # Use median as rough spot proxy
                ticker_spot[tk] = strikes[len(strikes) // 2]
            else:
                ticker_spot[tk] = 100.0

        # --- Filter B: OI >= 2% of total ticker OI ---
        ticker_total_oi: dict[str, int] = {}
        for tk, tbets in ticker_bets.items():
            ticker_total_oi[tk] = sum((b.current_oi or b.original_oi or 0) for b in tbets)

        def passes_B(b: DormantBet, pct: float = 0.02) -> bool:
            oi = b.current_oi or b.original_oi or 0
            total = ticker_total_oi.get(b.ticker.upper(), 0)
            return total > 0 and (oi / total) >= pct

        # --- Filter D: within-expiry 90th percentile DWOI ---
        # Group bets by (ticker, expiry) and compute 90th pct
        # Use OI as proxy for DWOI since delta=None for most
        expiry_oi: dict[tuple[str, date], list[int]] = defaultdict(list)
        for b in bets:
            expiry_oi[(b.ticker.upper(), b.expiry)].append(b.current_oi or b.original_oi or 0)

        def passes_D(b: DormantBet, q: float = 0.90) -> bool:
            key = (b.ticker.upper(), b.expiry)
            group = expiry_oi.get(key, [])
            if not group:
                return False
            threshold = percentile_value(sorted(group), q)
            oi = b.current_oi or b.original_oi or 0
            return oi >= threshold

        # --- Apply B(2%)+D ---
        bd_bets = [b for b in bets if passes_B(b) and passes_D(b)]
        bd_tickers = {b.ticker.upper() for b in bd_bets}
        print(f"\nB(2%)+D filter: {len(bd_bets)} contracts across {len(bd_tickers)} tickers")

        # --- Build proxy ticker_chain from dormant_bets for scoring ---
        def proxy_chain(ticker: str) -> list:
            if ticker in real_chains and real_chains[ticker]:
                return real_chains[ticker]
            # Build proxy from all bets for this ticker
            return [
                ProxyChainRow(
                    strike=b.strike,
                    call_put=b.call_put,
                    oi=b.current_oi or b.original_oi or 0,
                    delta=None,
                    iv=None,
                    expiry=b.expiry,
                )
                for b in ticker_bets.get(ticker, [])
            ]

        # --- Score each bet ---
        scores: list[tuple[DormantBet, float, dict]] = []
        for b in bd_bets:
            tk = b.ticker.upper()
            spot = ticker_spot.get(tk, 100.0)
            chain = proxy_chain(tk)
            catalyst_near = False  # no catalyst data — conservative
            final_score, detail = score_bet_v2(b, chain, spot, catalyst_near)
            scores.append((b, final_score, detail))

        # --- Score distribution ---
        from collections import Counter
        score_vals = [round(s, 2) for _, s, _ in scores]
        score_counter = Counter(score_vals)

        print("\n=== SCORE DISTRIBUTION (final_score = raw * isolation_mult) ===")
        max_score = 7
        print(f"{'Score':>8}  {'Pct/7':>7}  {'Count':>6}")
        for sv in sorted(score_counter.keys(), reverse=True):
            print(f"{sv:>8.2f}  {sv/max_score:>6.1%}  {score_counter[sv]:>6}")

        # --- What fires at each threshold ---
        for thr in (0.6, 0.5, 0.4):
            fires = [(b, s, d) for b, s, d in scores if s / max_score >= thr]
            print(f"\n=== FIRES at threshold {thr} (score/{max_score} >= {thr}, score >= {thr*max_score:.1f}) ===")
            print(f"  Count: {len(fires)} / {len(scores)}")
            if fires:
                by_ticker: dict[str, list] = defaultdict(list)
                for b, s, d in fires:
                    by_ticker[b.ticker.upper()].append((b, s, d))
                print(f"  Tickers: {len(by_ticker)}")
                print(f"  {'Ticker':>6}  {'Score':>6}  {'Contract':<30}  {'OI':>7}  {'DTE':>4}  {'Purity':>6}")
                for tk in sorted(by_ticker.keys()):
                    for b, s, d in sorted(by_ticker[tk], key=lambda x: -x[1]):
                        dte = (b.expiry - date.today()).days if b.expiry else 0
                        print(f"  {tk:>6}  {s:>6.2f}  {b.contract:<30}  {(b.current_oi or b.original_oi or 0):>7}  {dte:>4}  {d.get('hedge_purity', 0):>6.3f}")

        # --- Detailed breakdown by signal ---
        print("\n=== STRUCTURAL SIGNAL BREAKDOWN (all 925 contracts) ===")
        time_ok = sum(1 for _, _, d in scores if d.get("raw_score", 0) >= 1)
        long_dated = sum(1 for b, _, _ in scores
                         if b.expiry and b.original_date and (b.expiry - b.original_date).days >= 90)
        has_size = sum(1 for _, _, d in scores if d.get("size_pct", 0) >= 0.90)
        has_size2 = sum(1 for _, _, d in scores if d.get("size_pct", 0) >= 0.99)
        has_iv = sum(1 for _, _, d in scores if d.get("iv_pct") is not None)
        isolated = sum(1 for _, _, d in scores if d.get("isolation_multiplier", 1) == 1.0)
        half_iso = sum(1 for _, _, d in scores if d.get("isolation_multiplier", 1) == 0.5)
        zero_iso = sum(1 for _, _, d in scores if d.get("isolation_multiplier", 1) == 0.0)
        n = len(scores)
        print(f"  Time remaining >7d: {time_ok}/{n} ({time_ok/n:.0%})")
        print(f"  Long-dated (>=90 DTE at open): {long_dated}/{n} ({long_dated/n:.0%})")
        print(f"  Size pct >=90th: {has_size}/{n} ({has_size/n:.0%})")
        print(f"  Size pct >=99th: {has_size2}/{n} ({has_size2/n:.0%})")
        print(f"  IV data available: {has_iv}/{n} ({has_iv/n:.0%})")
        print(f"  Isolation mult=1.0 (isolated): {isolated}/{n} ({isolated/n:.0%})")
        print(f"  Isolation mult=0.5 (partial): {half_iso}/{n} ({half_iso/n:.0%})")
        print(f"  Isolation mult=0.0 (hedged): {zero_iso}/{n} ({zero_iso/n:.0%})")

        # --- Top 20 by score ---
        print("\n=== TOP 20 BY SCORE ===")
        top20 = sorted(scores, key=lambda x: -x[1])[:20]
        print(f"{'Ticker':>6}  {'Score':>6}  {'Pct':>5}  {'RawSc':>6}  {'Mult':>5}  {'OI':>7}  {'DTE':>4}  {'Contract'}")
        for b, s, d in top20:
            dte = (b.expiry - date.today()).days if b.expiry else 0
            oi = b.current_oi or b.original_oi or 0
            raw = d.get("raw_score", "?")
            mult = d.get("isolation_multiplier", "?")
            pct = s / max_score
            print(f"  {b.ticker.upper():>6}  {s:>6.2f}  {pct:>4.1%}  {str(raw):>6}  {str(mult):>5}  {oi:>7}  {dte:>4}  {b.contract}")

        # --- REAL chain tickers breakdown ---
        print("\n=== REAL CHAIN TICKERS (4) — SCORE DETAIL ===")
        real_bd = [(b, s, d) for b, s, d in scores if b.ticker.upper() in real_chains]
        if real_bd:
            for b, s, d in sorted(real_bd, key=lambda x: -x[1]):
                dte = (b.expiry - date.today()).days if b.expiry else 0
                print(f"  {b.ticker.upper()}  score={s:.2f}  raw={d.get('raw_score')}  mult={d.get('isolation_multiplier')}  size_pct={d.get('size_pct','N/A')}  iv_pct={d.get('iv_pct','N/A')}  dwoi=${d.get('dwoi_usd',0):,.0f}  dte={dte}")
        else:
            print("  None of the real-chain tickers survived B+D filter")


asyncio.run(main())
