#!/usr/bin/env python3
"""
EigenView Pipeline Validator
Run: uv run python scripts/validate_pipeline.py [TICKER]

Proves the full pipeline works by running every stage with REAL data and
showing exactly what raw values drove each factor decision.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── helpers ──────────────────────────────────────────────────────────────────

SEP  = "-" * 64
SEP2 = "=" * 64

def hdr(title: str) -> None:
    print(f"\n{SEP}\n  {title}\n{SEP}")

def row(label: str, value, pass_: bool | None = None, indent: int = 2) -> None:
    tick = " OK" if pass_ is True else (" FAIL" if pass_ is False else "")
    print(f"{'  ' * indent}{label:<32} {value}{tick}")

def firing_line(result) -> str:
    symbol = "[FIRING]" if result.firing else "[NOT FIRING]"
    return f"{symbol}  strength={result.strength:.2f}  label={result.label}"


# ── stages ────────────────────────────────────────────────────────────────────

async def validate_prices(ticker: str) -> "pd.DataFrame":
    import pandas as pd
    from eigenview.data.prices import get_prices
    hdr(f"DATA: PRICES — {ticker}")
    df = await get_prices(ticker, timeframe="1d", days=90)
    if df.empty:
        print("  ✗ NO PRICE DATA")
        return df
    row("Rows returned", len(df), len(df) >= 60)
    row("Date range", f"{df.index[0].date()} → {df.index[-1].date()}")
    row("Last close", f"${df['close'].iloc[-1]:.2f}")
    row("Columns", ", ".join(df.columns.tolist()))
    # Check for gaps (trading days)
    gaps = df.index.to_series().diff().dt.days.dropna()
    big_gaps = gaps[gaps > 5]
    row("Large gaps (>5d)", len(big_gaps), len(big_gaps) == 0)
    return df


async def validate_chain(ticker: str) -> list:
    from eigenview.data.chains import get_chain
    from eigenview.data.storage import AsyncSessionLocal, Chain
    from sqlalchemy import select
    hdr(f"DATA: OPTIONS CHAIN — {ticker}")
    await get_chain(ticker)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == date.today())
        )
        chains = result.scalars().all()
    row("Contracts in DB (today)", len(chains), len(chains) > 0)
    if chains:
        calls = [c for c in chains if str(c.call_put).lower() == "c"]
        puts  = [c for c in chains if str(c.call_put).lower() == "p"]
        row("Calls / Puts", f"{len(calls)} / {len(puts)}")
        with_gamma = [c for c in chains if c.gamma is not None and c.gamma != 0]
        row("Contracts with gamma", len(with_gamma), len(with_gamma) > 10)
        exps = sorted({c.expiry for c in chains if c.expiry})
        row("Expiry range", f"{exps[0]} → {exps[-1]}" if exps else "none")
    return chains


async def validate_macro() -> dict:
    from eigenview.data.storage import AsyncSessionLocal, MacroDaily
    from sqlalchemy import select
    hdr("DATA: MACRO REGIME")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(MacroDaily).order_by(MacroDaily.date.desc()).limit(1)
        )
        macro = result.scalar_one_or_none()
    if not macro:
        print("  ✗ No macro data in DB — run `uv run eigenview fetch-macro`")
        return {}
    row("Date",           macro.date)
    row("VIX M1",         f"{macro.vix_m1:.2f}" if macro.vix_m1 else "N/A")
    row("VIX M2",         f"{macro.vix_m2:.2f}" if macro.vix_m2 else "N/A")
    row("VIX contango %", f"{macro.vix_contango_pct:.2f}%" if macro.vix_contango_pct else "N/A")
    row("DIX",            f"{macro.dix:.3f}" if macro.dix else "N/A")
    row("GEX index",      f"{macro.gex_index:.2e}" if macro.gex_index else "N/A")
    row("SPX breadth %",  f"{macro.spx_breadth_pct:.1f}%" if macro.spx_breadth_pct else "N/A")
    return {
        "vix_m1": macro.vix_m1, "vix_m2": macro.vix_m2,
        "vix_contango_pct": macro.vix_contango_pct,
        "dix": macro.dix, "gex_index": macro.gex_index,
        "spx_breadth_pct": macro.spx_breadth_pct,
    }


def validate_technical(df: "pd.DataFrame", ticker: str) -> None:
    from eigenview.factors.technical import score_technical
    hdr(f"FACTOR: TECHNICAL — {ticker}")
    result = score_technical(df, ticker)
    print(f"  {firing_line(result)}")
    d = result.detail
    row("Pattern",       d.get("pattern", "?"))
    row("Confidence",    f"{d.get('confidence', 0):.0%}",  d.get("confidence", 0) >= 0.6)
    row("Trend",         d.get("trend", "?"))
    row("Weekly trend",  d.get("weekly_trend", "?"))
    row("ADX",           f"{d.get('adx', 0):.1f}",         d.get("adx", 0) > 20)
    row("RSI",           f"{d.get('rsi', 0):.1f}")
    row("Vol ratio",     f"{d.get('vol_ratio', 0):.2f}x")
    row("Vol character", d.get("vol_character", "?"))
    fib = d.get("fib_levels", {})
    if fib:
        row("Fib 38.2%",  f"${fib.get('f382', 0):.2f}")
        row("Fib 61.8%",  f"${fib.get('f618', 0):.2f}")
    row("Swing high/low", f"${d.get('swing_high',0):.2f} / ${d.get('swing_low',0):.2f}")
    if not result.firing:
        print(f"\n  WHY NOT FIRING: confidence {d.get('confidence',0):.0%} < 60% threshold")
    else:
        print(f"\n  WHY FIRING: pattern={d.get('pattern')} conf={d.get('confidence',0):.0%} ≥ 60%")
    print(f"\n  Narrative: {result.narrative}")
    return result


def validate_gex(chains: list, spot: float, ticker: str) -> None:
    from eigenview.factors.gex import score_gex
    hdr(f"FACTOR: GEX — {ticker}")
    result = score_gex(chains, spot, ticker)
    print(f"  {firing_line(result)}")
    d = result.detail
    net_gex = d.get("net_gex", 0)
    row("Net GEX",        f"${net_gex:,.0f}")
    row("Regime",         d.get("regime", "?"))
    row("Gamma flip",     f"${d.get('gamma_flip', 0):.2f}")
    row("Call wall",      f"${d.get('call_wall', 0):.0f}",  d.get("call_wall") is not None)
    row("Put wall",       f"${d.get('put_wall', 0):.0f}",   d.get("put_wall") is not None)
    row("Spot vs call wall", f"{((spot / d.get('call_wall',spot)) - 1)*100:.1f}% away" if d.get('call_wall') else "N/A")
    # GEX by expiry
    by_exp = d.get("gex_by_expiry", {})
    if by_exp:
        row("0DTE GEX",   f"${by_exp.get('0dte', 0):,.0f}")
        row("Weekly GEX", f"${by_exp.get('weekly', 0):,.0f}")
        row("Monthly GEX",f"${by_exp.get('monthly', 0):,.0f}")
    # Gamma cluster
    cluster = d.get("gamma_cluster", {})
    if cluster:
        row("Gamma cluster strikes", f"{cluster.get('dense_strikes', 0)} dense in ±2% band")
        row("Pinning risk", str(cluster.get("pinning_risk", False)))
    print(f"\n  WHY: regime={d.get('regime')} — ", end="")
    if result.firing:
        print(f"short_gamma or flip_zone triggers firing")
    else:
        print(f"long_gamma = suppressed moves (fires but low strength)")
    print(f"\n  Narrative: {result.narrative}")
    return result


def validate_flow(chains: list, ticker: str) -> None:
    from eigenview.factors.flow import score_flow
    hdr(f"FACTOR: FLOW — {ticker}")
    result = score_flow(chains, ticker)
    print(f"  {firing_line(result)}")
    d = result.detail
    row("Total qualified sweeps",    d.get("total_qualified", 0), d.get("total_qualified", 0) >= 1)
    row("Largest sweep",             f"${d.get('largest_sweep_usd', 0):,.0f}")
    row("Call premium",              f"${d.get('call_premium', 0):,.0f}")
    row("Put premium",               f"${d.get('put_premium', 0):,.0f}")
    call_p = d.get("call_premium", 0)
    put_p  = d.get("put_premium", 0)
    ratio  = call_p / put_p if put_p > 0 else 0
    row("Call/Put ratio",            f"{ratio:.2f}:1")
    row("Dominant side",             d.get("dominant_side", "?"))
    row("Aggressive call buys",      d.get("aggressive_buy_calls", 0))
    row("Aggressive put buys",       d.get("aggressive_buy_puts", 0))
    print(f"\n  WHY: ", end="")
    if result.firing:
        print(f"qualified sweeps={d.get('total_qualified',0)} + dominant side = {d.get('dominant_side')}")
    else:
        print(f"not enough qualified sweeps (need ≥1 with premium >$500K)")
    print(f"\n  Narrative: {result.narrative}")
    return result


async def validate_dormant(ticker: str, chains: list, spot: float, days_history: int) -> None:
    from eigenview.data.storage import AsyncSessionLocal, DormantBet
    from eigenview.factors.dormant import score_dormant_from_history
    from sqlalchemy import select
    hdr(f"FACTOR: DORMANT — {ticker}")
    # Show dormant bets in DB
    async with AsyncSessionLocal() as session:
        result_db = await session.execute(
            select(DormantBet).where(DormantBet.ticker == ticker).limit(10)
        )
        bets = result_db.scalars().all()
        dormant_result = await score_dormant_from_history(ticker, session, spot, chains)

    row("Dormant bets tracked",  len(bets), len(bets) > 0)
    row("Days of chain history", days_history, days_history >= 30)
    if bets:
        print(f"\n  TRACKED POSITIONS:")
        for b in bets[:5]:
            age = (date.today() - b.original_date).days
            oi_chg = ((b.current_oi - b.original_oi) / b.original_oi * 100) if b.original_oi else 0
            print(f"    {b.contract}")
            print(f"      Opened: {b.original_date} ({age}d ago)  Premium: ${b.original_premium:,.0f}")
            print(f"      OI: {b.original_oi} → {b.current_oi} ({oi_chg:+.0f}%)")
            print(f"      Strike: ${b.strike}  Expiry: {b.expiry}  {b.call_put.upper()}")
    else:
        print("\n  No dormant bets yet — needs 30+ days of chain data to accumulate")

    print(f"\n  {firing_line(dormant_result)}")
    if not dormant_result.firing and not bets:
        print(f"  WHY NOT FIRING: no large long-dated positions identified in today's chain")
        print(f"  (Scanner identifies positions with DTE≥60 and premium≥$300K on each scan)")
    print(f"\n  Narrative: {dormant_result.narrative}")
    return dormant_result


async def validate_sentiment(ticker: str) -> None:
    from eigenview.data.storage import AsyncSessionLocal
    from eigenview.factors.sentiment import score_sentiment
    hdr(f"FACTOR: SENTIMENT — {ticker}")
    async with AsyncSessionLocal() as session:
        result = await score_sentiment(ticker, session)
    print(f"  {firing_line(result)}")
    d = result.detail
    row("Novelty score",  f"{d.get('novelty_z', 0):.2f}" if d.get('novelty_z') else "N/A")
    row("Sentiment dir",  d.get("sentiment_direction", "?"))
    row("Catalyst near",  str(d.get("catalyst_near", False)))
    row("Top headline",   (d.get("top_headline") or "none")[:60])
    print(f"\n  Narrative: {result.narrative}")
    return result


def validate_synthesis(ticker: str, macro_score: int, ta, gex, flow, dormant, sent, macro_result, spot: float) -> None:
    from eigenview.synthesis.gate import (
        TickerScorecard, conviction_score, entry_zone,
        qualify_pick, setup_type, stop_level, tier_score,
    )
    hdr(f"SYNTHESIS: GATE + RANK — {ticker}")
    sc = TickerScorecard(
        ticker=ticker, macro=macro_result,
        technical=ta, gex=gex, flow=flow, dormant=dormant, sentiment=sent,
        spot_price=spot,
    )
    q = qualify_pick(sc, macro_score)
    tier = tier_score(sc, macro_score)
    conv = conviction_score(sc)
    stype = setup_type(sc)
    entry_lo, entry_hi = entry_zone(sc)
    stop = stop_level(sc)

    print(f"  Macro score:    {macro_score}/10")
    print(f"  TA firing:      {'✓' if ta.firing else '✗'} (hard gate)")
    print(f"  GEX firing:     {'✓' if gex.firing else '✗'} (hard gate)")
    soft = sum([flow.firing, dormant.firing, sent.firing])
    print(f"  Soft factors:   {soft}/3 — flow={flow.firing} dormant={dormant.firing} sentiment={sent.firing}")
    print()
    print(f"  QUALIFIES:      {'YES ✓' if q else 'NO ✗'}")
    print(f"  TIER:           {tier or 'none'}")
    print(f"  CONVICTION:     {conv}/5")
    print(f"  SETUP TYPE:     {stype}")
    print(f"  ENTRY ZONE:     ${entry_lo} – ${entry_hi}")
    print(f"  STOP:           ${stop}")
    if not q:
        reasons = []
        if macro_score < 3:        reasons.append(f"macro RED ({macro_score}<3)")
        if not ta.firing:           reasons.append("TA gate blocked")
        if not gex.firing:          reasons.append("GEX gate blocked")
        if soft < 2:                reasons.append(f"only {soft} soft factor(s) (need ≥2)")
        print(f"\n  WHY NOT QUALIFYING: {' | '.join(reasons)}")


async def validate_db_state(ticker: str) -> None:
    from eigenview.data.storage import AsyncSessionLocal, FactorScore, Pick
    from sqlalchemy import select
    hdr("DB STATE")
    async with AsyncSessionLocal() as session:
        # Latest pick
        pick_res = await session.execute(
            select(Pick).where(Pick.ticker == ticker).order_by(Pick.date.desc()).limit(1)
        )
        pick = pick_res.scalar_one_or_none()
        # Latest factor score
        fs_res = await session.execute(
            select(FactorScore).where(FactorScore.ticker == ticker).order_by(FactorScore.date.desc()).limit(1)
        )
        fs = fs_res.scalar_one_or_none()
        # All picks today
        today_res = await session.execute(
            select(Pick).where(Pick.date == date.today())
        )
        today_picks = today_res.scalars().all()

    print(f"  Today's picks in DB: {len(today_picks)}")
    for p in today_picks:
        print(f"    {p.ticker}  conviction={p.conviction}  setup={p.setup_type}  score={p.score}")
    if pick:
        print(f"\n  Latest pick for {ticker}: {pick.date}  conviction={pick.conviction}")
        if pick.thesis:
            print(f"  Thesis: {pick.thesis[:120]}…")
    if fs:
        print(f"\n  Latest FactorScore for {ticker}: {fs.date}")
        row("TA",        f"{fs.ta_strength:.2f}  {fs.ta_label}", indent=2)
        row("GEX",       f"{fs.gex_strength:.2f}  {fs.gex_label}", indent=2)
        row("Flow",      f"{fs.flow_strength:.2f}  {fs.flow_label}", indent=2)
        row("Dormant",   f"{fs.dormant_strength:.2f}  {fs.dormant_label}", indent=2)
        row("Sentiment", f"{fs.sentiment_strength:.2f}  {fs.sentiment_label}", indent=2)
        row("Macro",     f"{fs.macro_score}/10", indent=2)
        row("Factors firing", fs.factors_firing, indent=2)
    else:
        print(f"\n  No FactorScore for {ticker} — run a scan first")


# ── main ──────────────────────────────────────────────────────────────────────

async def main(ticker: str = "NVDA") -> None:
    ticker = ticker.upper()
    print(f"\n{SEP2}")
    print(f"  EigenView Pipeline Validator")
    print(f"  Ticker: {ticker}   Date: {date.today()}")
    print(SEP2)

    # 1. Data layer
    df = await validate_prices(ticker)
    chains = await validate_chain(ticker)
    macro_data = await validate_macro()

    if df.empty:
        print("\n  ✗ Cannot proceed: no price data")
        return

    spot = float(df["close"].iloc[-1])
    print(f"\n  Current spot: ${spot:.2f}")

    # 2. Macro factor (needed for synthesis)
    from eigenview.data.storage import AsyncSessionLocal
    from eigenview.factors.macro_regime import score_macro_regime
    from eigenview.data.storage import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        macro_result = await score_macro_regime(session)
    macro_score = int(macro_result.detail.get("score", 0))
    hdr("FACTOR: MACRO REGIME")
    print(f"  {firing_line(macro_result)}")
    row("Score",      f"{macro_score}/10", macro_score >= 4)
    row("Label",      macro_result.label)
    print(f"\n  Narrative: {macro_result.narrative}")

    # 3. Per-ticker factors
    ta_result       = validate_technical(df, ticker)
    gex_result      = validate_gex(chains, spot, ticker)
    flow_result     = validate_flow(chains, ticker)

    from eigenview.data.storage import AsyncSessionLocal, Chain
    from sqlalchemy import func, select
    async with AsyncSessionLocal() as session:
        count_q = await session.execute(
            select(func.count()).select_from(Chain).where(Chain.ticker == ticker)
        )
        chain_count = count_q.scalar() or 0
    today_chain_count = len(chains)
    days_history = min(chain_count // max(1, today_chain_count), 90)

    dormant_result  = await validate_dormant(ticker, chains, spot, days_history)
    sent_result     = await validate_sentiment(ticker)

    # 4. Synthesis
    validate_synthesis(ticker, macro_score, ta_result, gex_result, flow_result,
                       dormant_result, sent_result, macro_result, spot)

    # 5. DB state
    await validate_db_state(ticker)

    print(f"\n{SEP2}")
    print("  Validation complete.")
    print(SEP2 + "\n")


if __name__ == "__main__":
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    asyncio.run(main(ticker))
