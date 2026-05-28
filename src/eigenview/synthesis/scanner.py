from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import pandas as pd
import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Chain, ContractHistory, DormantBet, FactorScore, Price, write_signal_trigger
from eigenview.factors.base import FactorResult
from eigenview.factors.dormant import (
    candidate_dwoi_floor,
    is_dormant_candidate,
    mark_price,
    score_dormant_from_history,
)
from eigenview.factors.flow import score_flow
from eigenview.factors.gex import score_gex
from eigenview.factors.macro_regime import score_macro_regime
from eigenview.factors.sentiment import score_sentiment
from eigenview.factors.technical import score_technical
from eigenview.synthesis.gate import SHORT_SETUP_PATTERNS, TickerScorecard, entry_zone, stop_level
from eigenview.synthesis.ranker import rank_picks, write_picks

log = structlog.get_logger(__name__)


async def _identify_dormant_bets(
    ticker: str,
    chains: list,
    spot: float,
    today: date,
    session: AsyncSession,
) -> None:
    """Upsert qualifying large long-dated positions into dormant_bets table."""
    if not chains or spot <= 0:
        return
    floor = candidate_dwoi_floor(list(chains), spot)
    for c in chains:
        if not is_dormant_candidate(c, spot, floor, today, settings.dormant_min_dte):
            continue
        if (c.oi or 0) < settings.scanner_min_oi:
            continue
        mid = mark_price(c.bid, c.ask, c.iv, spot, c.strike, c.expiry, c.call_put, today)
        premium = mid * (c.oi or 0) * 100
        # Naming matches find_dormant.py so both scripts produce the same contract key.
        # call_put uppercased: chains table stores both 'C' and 'c' variants.
        contract = f"{ticker}_{c.expiry.isoformat()}_{int(c.strike)}{str(c.call_put).upper()[:1]}"
        # Upsert on the (ticker, contract, original_date) unique key — atomic, so a
        # re-scan or an int(strike) contract-id collision updates instead of crashing.
        stmt = upsert(DormantBet).values(
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
        ).on_conflict_do_update(
            index_elements=["ticker", "contract", "original_date"],
            set_={"current_oi": c.oi, "updated_at": datetime.utcnow()},
        )
        await session.execute(stmt)


async def _fetch_live(ticker: str) -> pd.DataFrame:
    """Read daily OHLCV from the prices table (Databento 2yr daily)."""
    from eigenview.data.storage import AsyncSessionLocal

    cutoff = (datetime.utcnow() - timedelta(days=settings.scanner_price_lookback_days)).date()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Price)
            .where(
                Price.ticker == ticker.upper(),
                Price.timeframe == "1d",
                Price.date >= cutoff,
            )
            .order_by(Price.date.asc())
        )
        rows = result.scalars().all()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([
        {"date": r.date, "open": r.open, "high": r.high,
         "low": r.low, "close": r.close, "volume": r.volume}
        for r in rows
    ])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    return df.dropna(subset=["close"])


def _compute_contract_iv(
    close: float | None,
    spot: float | None,
    strike: float,
    d: date,
    expiry: date,
    call_put: str,
) -> float | None:
    if not (close and close > 0 and spot and spot > 0):
        return None
    from eigenview.config import settings
    from py_vollib.black_scholes.implied_volatility import implied_volatility
    t = max((expiry - d).days, 1) / 365.0
    try:
        return implied_volatility(close, spot, strike, t, settings.risk_free_rate, call_put.lower()[:1])
    except Exception:
        return None


async def _refresh_watchlist_history(session: AsyncSession) -> None:
    """Pull fresh contract_history from Databento for any stale watchlist entries.

    Thin incremental pull: only fetches dates after the current max in contract_history.
    Skips gracefully if no Databento key configured or API call fails.
    """
    from eigenview.config import settings
    if not settings.databento_key:
        log.info("refresh_watchlist.skip", reason="no_databento_key")
        return

    bets = (await session.execute(select(DormantBet))).scalars().all()
    if not bets:
        return

    max_hist_row = await session.execute(select(func.max(ContractHistory.date)))
    last_date = max_hist_row.scalar()

    if last_date and last_date >= date.today():
        log.info("refresh_watchlist.up_to_date")
        return

    start = (
        (last_date + timedelta(days=1)).isoformat()
        if last_date
        else (date.today() - timedelta(days=settings.scanner_history_backfill_days)).isoformat()
    )
    end = date.today().isoformat()

    from eigenview.data.databento_history import fetch_statistics, osi_symbol as _osi

    bet_by_osi = {_osi(b.ticker, b.expiry, b.call_put, b.strike): b for b in bets}

    und_rows = (await session.execute(
        select(Price).where(Price.timeframe == "1d")
    )).scalars().all()
    und_close: dict[str, dict[date, float]] = {}
    for r in und_rows:
        und_close.setdefault(r.ticker.upper(), {})[r.date] = r.close

    loop = asyncio.get_event_loop()
    try:
        df = await loop.run_in_executor(
            None, fetch_statistics, list(bet_by_osi.keys()), start, end
        )
    except Exception as exc:
        log.warning("refresh_watchlist.databento_failed", error=str(exc))
        return

    if df.empty:
        log.info("refresh_watchlist.no_new_data")
        return

    to_insert = []
    for r in df.itertuples():
        bet = bet_by_osi.get(r.osi_symbol)
        if not bet:
            continue
        d = r.date
        spot = und_close.get(bet.ticker.upper(), {}).get(d)
        close = float(r.close) if r.close == r.close and r.close else None
        oi = int(r.oi) if r.oi == r.oi and r.oi else None
        vol = int(r.volume) if r.volume == r.volume and r.volume else None
        iv = _compute_contract_iv(close, spot, bet.strike, d, bet.expiry, bet.call_put)
        to_insert.append({
            "osi_symbol": r.osi_symbol, "ticker": bet.ticker,
            "date": d, "oi": oi, "volume": vol, "close": close, "iv": iv,
        })

    if to_insert:
        # SQLite caps at 999 bind params; ContractHistory has 7 cols → max 142 rows/stmt.
        # scanner_history_insert_chunk (default 100) stays well clear of the limit.
        _CHUNK = settings.scanner_history_insert_chunk
        for _i in range(0, len(to_insert), _CHUNK):
            await session.execute(
                upsert(ContractHistory).values(to_insert[_i:_i + _CHUNK]).on_conflict_do_nothing()
            )
        log.info("refresh_watchlist.done", rows=len(to_insert))


def _score_with_lookback(
    df: pd.DataFrame,
    ticker: str,
    lookback: int = settings.scanner_ta_lookback_days,
    gex_levels: dict | None = None,
):
    n = len(df)
    max_back = min(lookback, n - 50)
    for i in range(max(0, max_back) + 1):
        sl = df.iloc[:n - i] if i > 0 else df
        r = score_technical(sl, ticker, gex_levels=gex_levels)
        if r.firing:
            return r
    return score_technical(df, ticker, gex_levels=gex_levels)


async def _score_ticker(
    ticker: str,
    macro_result,
    macro_score: int,
    session: AsyncSession,
) -> TickerScorecard | None:
    try:
        df = await _fetch_live(ticker)
        if df.empty:
            log.warning("ticker_score_skipped", ticker=ticker, reason="no price data")
            return None
        spot = float(df["close"].iloc[-1])

        # Read latest available chain snapshot (not necessarily today — Databento
        # snapshot date may lag by a day or more)
        latest_snap_row = await session.execute(
            select(func.max(Chain.snapshot_date)).where(Chain.ticker == ticker)
        )
        snap_date = latest_snap_row.scalar()
        if snap_date is None:
            chains = []
        else:
            chain_rows = await session.execute(
                select(Chain).where(Chain.ticker == ticker, Chain.snapshot_date == snap_date)
            )
            chains = chain_rows.scalars().all()

        # GEX first so its dealer levels feed TA confluence (strength-only).
        gex = score_gex(list(chains), spot, ticker)
        gex_levels = {
            "call_wall": gex.detail.get("call_wall"),
            "put_wall": gex.detail.get("put_wall"),
            "gamma_flip": gex.detail.get("gamma_flip"),
        } if gex.detail else None
        ta = _score_with_lookback(df, ticker, gex_levels=gex_levels)
        flow = score_flow(list(chains), ticker)

        # Options-liquidity gate (OI proxy until real options-volume history is
        # pulled). Illiquid names: don't accumulate dormant candidates, don't score,
        # never fire — their chains are too thin to judge dealer/dormant positioning.
        ticker_oi = sum(int(getattr(c, "oi", 0) or 0) for c in chains)
        if ticker_oi >= settings.dormant_min_ticker_oi:
            await _identify_dormant_bets(ticker, list(chains), spot, date.today(), session)
            dormant = await score_dormant_from_history(ticker, session, spot, list(chains))
        else:
            dormant = FactorResult(
                factor_id="dormant", firing=False, strength=0.0, label="NOT_LIQUID",
                detail={"ticker_oi": ticker_oi, "min_oi": settings.dormant_min_ticker_oi},
                narrative=(
                    f"Options illiquid (agg OI {ticker_oi} < "
                    f"{settings.dormant_min_ticker_oi}) — not screened for dormant bets."
                ),
            )
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

    # Refresh contract history for dormant watchlist before scoring
    await _refresh_watchlist_history(session)

    sem = asyncio.Semaphore(settings.scanner_concurrency)

    async def bounded(t: str) -> TickerScorecard | None:
        async with sem:
            return await _score_ticker(t, macro, macro_score, session)

    results = await asyncio.gather(*[bounded(t) for t in tickers])
    scorecards = [r for r in results if r is not None]

    qualified = rank_picks(scorecards, macro_score)
    await write_picks(qualified, macro_score, session, all_scorecards=scorecards)

    # Write per-ticker factor scores for all scanned tickers (heat map / debug source)
    today_date = date.today()
    for sc in scorecards:
        factors_firing = sum([
            sc.technical.firing, sc.gex.firing,
            sc.flow.firing, sc.dormant.firing, sc.sentiment.firing,
        ])
        stmt = upsert(FactorScore).values(
            date=today_date,
            ticker=sc.ticker,
            ta_strength=sc.technical.strength,
            ta_label=sc.technical.label,
            gex_strength=sc.gex.strength,
            gex_label=sc.gex.label,
            flow_strength=sc.flow.strength,
            flow_label=sc.flow.label,
            dormant_strength=sc.dormant.strength,
            dormant_label=sc.dormant.label,
            sentiment_strength=sc.sentiment.strength,
            sentiment_label=sc.sentiment.label,
            macro_score=macro_score,
            spot_price=sc.spot_price,
            factors_firing=factors_firing,
            updated_at=datetime.utcnow(),
        ).on_conflict_do_update(
            index_elements=["date", "ticker"],
            set_={
                "ta_strength": sc.technical.strength,
                "ta_label": sc.technical.label,
                "gex_strength": sc.gex.strength,
                "gex_label": sc.gex.label,
                "flow_strength": sc.flow.strength,
                "flow_label": sc.flow.label,
                "dormant_strength": sc.dormant.strength,
                "dormant_label": sc.dormant.label,
                "sentiment_strength": sc.sentiment.strength,
                "sentiment_label": sc.sentiment.label,
                "macro_score": macro_score,
                "spot_price": sc.spot_price,
                "factors_firing": factors_firing,
                "updated_at": datetime.utcnow(),
            },
        )
        await session.execute(stmt)
    await session.flush()

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
                log.warning("thesis_skipped_no_data", ticker=sc.ticker)
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
