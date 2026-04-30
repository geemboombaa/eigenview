from __future__ import annotations

import asyncio
from datetime import date

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.chains import get_chain
from eigenview.data.prices import get_prices
from eigenview.data.storage import Chain
from eigenview.factors.dormant import score_dormant
from eigenview.factors.flow import score_flow
from eigenview.factors.gex import score_gex
from eigenview.factors.macro_regime import score_macro_regime
from eigenview.factors.sentiment import score_sentiment
from eigenview.factors.technical import score_technical
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.ranker import rank_picks, write_picks

log = structlog.get_logger(__name__)


async def _score_ticker(
    ticker: str,
    macro_result,
    macro_score: int,
    session: AsyncSession,
) -> TickerScorecard | None:
    try:
        df = await get_prices(ticker, timeframe="1d", days=90)
        if df.empty:
            return None
        spot = float(df["close"].iloc[-1])

        chain_data = await get_chain(ticker)
        chain_rows = await session.execute(
            select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == date.today())
        )
        chains = chain_rows.scalars().all()

        ta = score_technical(df, ticker)
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
