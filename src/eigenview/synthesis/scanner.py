from __future__ import annotations

import asyncio
from datetime import date, datetime

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import yfinance as yf
from eigenview.data.calendar import get_catalysts
from eigenview.data.chains import get_chain
from eigenview.data.news import fetch_news
from eigenview.data.storage import Chain, DormantBet, write_signal_trigger
from eigenview.synthesis.gate import SHORT_SETUP_PATTERNS, entry_zone, stop_level
from eigenview.factors.dormant import (
    candidate_dwoi_floor,
    is_dormant_candidate,
    mark_price,
    score_dormant,
)
from eigenview.factors.flow import score_flow
from eigenview.factors.gex import score_gex
from eigenview.factors.macro_regime import score_macro_regime
from eigenview.factors.sentiment import score_sentiment
from eigenview.factors.technical import score_technical
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.ranker import rank_picks, write_picks

log = structlog.get_logger(__name__)

_DORMANT_MIN_DTE = 20


async def _identify_dormant_bets(
    ticker: str,
    chains: list,
    spot: float,
    today: date,
    session: AsyncSession,
) -> None:
    """Upsert qualifying large long-dated positions into dormant_bets table.

    Qualification is relative to the ticker's own chain (ΔWOI ≥ 80th pct, with a
    $1M tradeability floor) — shared with the find_dormant screen via dormant.py.
    """
    if not chains or spot <= 0:
        return
    floor = candidate_dwoi_floor(list(chains), spot)
    for c in chains:
        if not is_dormant_candidate(c, spot, floor, today, _DORMANT_MIN_DTE):
            continue
        mid = mark_price(c.bid, c.ask, c.iv, spot, c.strike, c.expiry, c.call_put, today)
        premium = mid * (c.oi or 0) * 100
        contract = f"{ticker}{c.expiry.strftime('%y%m%d')}{c.call_put}{int(c.strike)}"
        # Match on the contract only (NOT original_date) so the first-seen row is
        # found and its OI carried forward — otherwise original_oi == current_oi
        # every day and OI change is always zero.
        existing = await session.execute(
            select(DormantBet).where(
                DormantBet.ticker == ticker,
                DormantBet.contract == contract,
            )
        )
        row = existing.scalars().first()
        if row is None:
            session.add(DormantBet(
                ticker=ticker,
                contract=contract,
                original_date=today,
                strike=c.strike,
                expiry=c.expiry,
                call_put=c.call_put,
                original_premium=round(premium, 2),
                current_oi=c.oi,
                original_oi=c.oi,
                updated_at=datetime.utcnow(),
            ))
        else:
            row.current_oi = c.oi
            row.updated_at = datetime.utcnow()


async def _fetch_live(ticker: str) -> "pd.DataFrame":
    import pandas as pd
    loop = asyncio.get_event_loop()
    def _dl():
        return yf.download(ticker, period="200d", interval="1d",
                           auto_adjust=True, progress=False, threads=False)
    raw = await loop.run_in_executor(None, _dl)
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    df.columns = df.columns.str.lower() if not hasattr(df.columns, 'levels') else \
        df.xs(ticker, axis=1, level=1).columns.str.lower()
    if hasattr(raw.columns, 'levels'):
        df = raw.xs(ticker, axis=1, level=1).copy()
        df.columns = df.columns.str.lower()
    df.index.name = "date"
    return df.dropna(subset=["close"])


def _score_with_lookback(df: "pd.DataFrame", ticker: str, lookback: int = 10):
    n = len(df)
    max_back = min(lookback, n - 50)
    for i in range(max(0, max_back) + 1):
        sl = df.iloc[:n - i] if i > 0 else df
        r = score_technical(sl, ticker)
        if r.firing:
            return r
    return score_technical(df, ticker)


async def _score_ticker(
    ticker: str,
    macro_result,
    macro_score: int,
    session: AsyncSession,
) -> TickerScorecard | None:
    try:
        df = await _fetch_live(ticker)
        if df.empty:
            return None
        spot = float(df["close"].iloc[-1])

        chain_data = await get_chain(ticker)
        chain_rows = await session.execute(
            select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == date.today())
        )
        chains = chain_rows.scalars().all()

        # Accumulate dormant-bet candidates from today's chain (Day-1 onward).
        await _identify_dormant_bets(ticker, list(chains), spot, date.today(), session)

        ta = _score_with_lookback(df, ticker)
        gex = score_gex(list(chains), spot, ticker)
        flow = score_flow(list(chains), ticker)

        count_q = await session.execute(
            select(func.count()).select_from(Chain).where(Chain.ticker == ticker)
        )
        chain_count = count_q.scalar() or 0
        days_history = min(chain_count // max(1, len(chains) if chains else 1), 90)

        dormant = await score_dormant(ticker, session, spot, list(chains), days_history)
        sentiment = await score_sentiment(ticker, session)

        return TickerScorecard(
            ticker=ticker,
            macro=macro_result,
            technical=ta,
            gex=gex,
            flow=flow,
            dormant=dormant,
            sentiment=sentiment,
            spot_price=spot,
        )
    except Exception as exc:
        log.warning("ticker_score_failed", ticker=ticker, error=str(exc))
        return None


async def run_daily_scan(tickers: list[str], session: AsyncSession) -> list[TickerScorecard]:
    macro = await score_macro_regime(session)
    macro_score = int(macro.detail.get("score", 0))

    sem = asyncio.Semaphore(5)

    async def bounded(t: str) -> TickerScorecard | None:
        async with sem:
            return await _score_ticker(t, macro, macro_score, session)

    results = await asyncio.gather(*[bounded(t) for t in tickers])
    scorecards = [r for r in results if r is not None]

    qualified = rank_picks(scorecards, macro_score)
    await write_picks(qualified, macro_score, session, all_scorecards=scorecards)

    today_str = date.today().isoformat()
    for sc in scorecards:
        if not sc.technical.firing or not sc.technical.label:
            continue
        direction = "short" if sc.technical.label in SHORT_SETUP_PATTERNS else "long"
        ez = entry_zone(sc)
        sl = stop_level(sc)
        try:
            await write_signal_trigger(
                session,
                ticker=sc.ticker,
                scan_date=today_str,
                setup_type=sc.technical.label,
                direction=direction,
                entry_low=ez[0],
                entry_high=ez[1],
                stop=sl,
                target=None,
                confidence=sc.technical.strength,
            )
        except Exception as exc:
            log.warning("signal_trigger_write_failed", ticker=sc.ticker, error=str(exc))

    # Generate LLM theses for qualifying picks
    try:
        from datetime import date as _date

        from sqlalchemy import update

        from eigenview.data.storage import Pick
        from eigenview.llm.thesis import generate_thesis

        for sc in qualified:
            if sc.technical.label == "NO DATA":
                continue
            factors_dict = {
                f.factor_id: {"firing": f.firing, "label": f.label, "detail": f.detail}
                for f in [sc.technical, sc.gex, sc.flow, sc.dormant, sc.sentiment]
            }
            thesis = await generate_thesis(sc.ticker, factors_dict, sc.spot_price, None)
            await session.execute(
                update(Pick)
                .where(Pick.ticker == sc.ticker, Pick.date == _date.today())
                .values(thesis=thesis)
            )
        await session.flush()
    except Exception as exc:
        log.warning("thesis_generation_failed", error=str(exc))

    return qualified
