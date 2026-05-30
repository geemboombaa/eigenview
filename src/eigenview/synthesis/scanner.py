from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta

import pandas as pd
import structlog
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import (
    AsyncSessionLocal,
    Chain,
    ContractHistory,
    DormantBet,
    FactorScore,
    Price,
    write_signal_trigger,
)
from eigenview.factors.base import FactorResult
from eigenview.factors.dormant import (
    bet_confidence,
    candidate_dwoi_floor,
    is_dormant_candidate,
    mark_price,
    score_dormant_from_history,
)
from eigenview.factors.flow import score_flow
from eigenview.factors.gex import score_gex
from eigenview.factors.macro_regime import score_macro_regime
from eigenview.factors.sentiment import score_sentiment
from eigenview.factors.sentiment_model import warm_up as warm_up_sentiment
from eigenview.factors.technical import score_technical
from eigenview.data.universe import get_options_universe
from eigenview.synthesis.gate import (
    SHORT_SETUP_PATTERNS,
    TickerScorecard,
    conviction_score,
    entry_zone,
    estimate_target,
    setup_type,
    stop_level,
)
from eigenview.synthesis.ranker import rank_picks, write_picks

log = structlog.get_logger(__name__)

# SQLite allows ONE writer at a time. The scan scores tickers concurrently, each on
# its own session; serialize just the brief dormant-bet write+commit so concurrent
# writers never contend the lock (a transient lock used to drop the whole ticker).
_DORMANT_WRITE_LOCK = asyncio.Lock()

# Broker-screened options universe (184 names). Only these get GEX/flow/dormant
# scored — TA + sentiment run on the full scan universe. Loaded once.
_OPTIONS_UNIVERSE = set(get_options_universe())


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
        # Hedge/spread filter: keep only contracts that read as standalone directional
        # bets. Done HERE so hedged contracts never enter the table or the backfill bill.
        conf, _cdetail = bet_confidence(c, list(chains), spot)
        if conf < settings.dormant_bet_confidence_min:
            continue
        mid = mark_price(c.bid, c.ask, c.iv, spot, c.strike, c.expiry, c.call_put, today)
        premium = mid * (c.oi or 0) * 100
        # call_put uppercased: chains table stores both 'C' and 'c' variants.
        contract = f"{ticker}_{c.expiry.isoformat()}_{int(c.strike)}{str(c.call_put).upper()[:1]}"
        # Upsert on the (ticker, contract) unique key — one row per contract. original_date
        # is first-seen (preserved on conflict); current_oi tracks the latest snapshot.
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
            index_elements=["ticker", "contract"],
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
    """Pull fresh contract_history from Databento for the dormant watchlist.

    PER-CONTRACT window (not a single global max). Each contract gets backfilled from
    its OWN last stored date + 1; a brand-new contract with no history gets the full
    backfill window (settings.scanner_history_backfill_days). Symbols are bucketed by
    start date so each distinct window is one batched Databento call. This is the fix
    for the old global-max bug, which only ever pulled a forward tail and never
    backfilled newly-added contracts. Skips gracefully if no key / API fails.
    """
    import pandas as pd
    from eigenview.config import settings
    if not settings.databento_key:
        log.info("refresh_watchlist.skip", reason="no_databento_key")
        return

    bets = (await session.execute(select(DormantBet))).scalars().all()
    if not bets:
        return

    from eigenview.data.databento_history import fetch_statistics, osi_symbol as _osi

    bet_by_osi = {_osi(b.ticker, b.expiry, b.call_put, b.strike): b for b in bets}

    # Per-symbol last stored history date (the whole watchlist in one query).
    permax_rows = await session.execute(
        select(ContractHistory.osi_symbol, func.max(ContractHistory.date))
        .group_by(ContractHistory.osi_symbol)
    )
    permax = {sym: d for sym, d in permax_rows.all()}

    today = date.today()
    end = today.isoformat()
    full_start = today - timedelta(days=settings.scanner_history_backfill_days)

    # Bucket symbols by their individual start date (incremental tail vs full backfill).
    buckets: dict[str, list[str]] = {}
    for osi in bet_by_osi:
        last = permax.get(osi)
        start_d = (last + timedelta(days=1)) if last else full_start
        if start_d >= today:   # already current through yesterday — nothing to pull
            continue
        buckets.setdefault(start_d.isoformat(), []).append(osi)

    if not buckets:
        log.info("refresh_watchlist.up_to_date")
        return

    und_rows = (await session.execute(
        select(Price).where(Price.timeframe == "1d")
    )).scalars().all()
    und_close: dict[str, dict[date, float]] = {}
    for r in und_rows:
        und_close.setdefault(r.ticker.upper(), {})[r.date] = r.close

    loop = asyncio.get_event_loop()
    frames: list[pd.DataFrame] = []
    for start, symbols in buckets.items():
        try:
            # Databento sync client has no request timeout — bound each bucket so a
            # stuck pull can't hang the whole download phase.
            part = await asyncio.wait_for(
                loop.run_in_executor(None, fetch_statistics, symbols, start, end),
                timeout=180.0,
            )
        except (Exception, asyncio.TimeoutError) as exc:
            log.warning("refresh_watchlist.databento_failed", start=start,
                        symbols=len(symbols), error=str(exc))
            continue
        if not part.empty:
            frames.append(part)

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

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
) -> TickerScorecard | None:
    """Score one ticker on its OWN session — never a shared one.

    Sharing a single AsyncSession across concurrent tasks deadlocks; each ticker
    gets an isolated session here so scoring is safely parallel. SQLite WAL +
    busy_timeout (set in storage) serialize the dormant-bet writes cleanly.
    """
    try:
        df = await _fetch_live(ticker)
        if df.empty:
            log.warning("ticker_score_skipped", ticker=ticker, reason="no price data")
            return None
        spot = float(df["close"].iloc[-1])

        async with AsyncSessionLocal() as session:
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

            # Options factors (GEX/flow/dormant) run ONLY for the broker-screened
            # options universe — chains exist for these names. Everything else scores
            # TA + sentiment only and cannot qualify as an options pick.
            in_options = ticker in _OPTIONS_UNIVERSE

            if in_options:
                # GEX first so its dealer levels feed TA confluence (strength-only).
                gex = score_gex(list(chains), spot, ticker)
                gex_levels = {
                    "call_wall": gex.detail.get("call_wall"),
                    "put_wall": gex.detail.get("put_wall"),
                    "gamma_flip": gex.detail.get("gamma_flip"),
                } if gex.detail else None
            else:
                gex = FactorResult(
                    factor_id="gex", firing=False, strength=0.0, label="NOT_IN_OPTIONS_UNIVERSE",
                    detail=None,
                    narrative="Not in options universe — no chains; GEX gate withheld.",
                )
                gex_levels = None

            ta = _score_with_lookback(df, ticker, gex_levels=gex_levels)

            if not in_options:
                flow = FactorResult(
                    factor_id="flow", firing=False, strength=0.0, label="NOT_IN_OPTIONS_UNIVERSE",
                    detail=None, narrative="Not in options universe — flow not scored.",
                )
                dormant = FactorResult(
                    factor_id="dormant", firing=False, strength=0.0, label="NOT_IN_OPTIONS_UNIVERSE",
                    detail=None, narrative="Not in options universe — dormant not screened.",
                )
            else:
                flow = score_flow(list(chains), ticker)

                # Options-liquidity gate (OI proxy until real options-volume history is
                # pulled). Illiquid names: don't accumulate dormant candidates, don't score,
                # never fire — their chains are too thin to judge dealer/dormant positioning.
                ticker_oi = sum(int(getattr(c, "oi", 0) or 0) for c in chains)
                if ticker_oi >= settings.dormant_min_ticker_oi:
                    # Serialize the write+commit so concurrent tickers can't collide on
                    # SQLite's single write lock (was dropping a ticker on transient lock).
                    async with _DORMANT_WRITE_LOCK:
                        await _identify_dormant_bets(ticker, list(chains), spot, date.today(), session)
                        await session.commit()
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
                    # Not options-tradeable → neutralize the GEX hard gate so the pick cannot
                    # qualify (a thin chain's dealer levels aren't trustworthy to trade on).
                    gex = FactorResult(
                        factor_id="gex", firing=False, strength=0.0, label="NOT_LIQUID",
                        detail=gex.detail,
                        narrative=(
                            f"Options illiquid (agg OI {ticker_oi} < "
                            f"{settings.dormant_min_ticker_oi}) — GEX gate withheld."
                        ),
                    )
            sentiment = await score_sentiment(ticker, session)
            await session.commit()  # persist dormant_bets accumulated above

        card = TickerScorecard(
            ticker=ticker,
            macro=macro_result,
            technical=ta,
            gex=gex,
            flow=flow,
            dormant=dormant,
            sentiment=sentiment,
            spot_price=spot,
        )

        # Price target (for R:R + the UI Target column) — computed here where the
        # price df + pattern detail are in scope.
        if ta.firing and ta.label:
            try:
                is_short = ta.label in SHORT_SETUP_PATTERNS
                ez = entry_zone(card)
                sl = stop_level(card)
                entry_ref = ez[0] if is_short else ez[1]
                card.target = estimate_target(ta.label, ta.detail, entry_ref, sl, df)
            except Exception as exc:
                log.warning("target_estimate_failed", ticker=ticker, error=str(exc))

        return card
    except Exception as exc:
        log.warning("ticker_score_failed", ticker=ticker, error=str(exc))
        return None


async def run_daily_scan(
    tickers: list[str],
    session: AsyncSession,
    download: bool = True,
    progress=None,
    chunk_size: int | None = None,
) -> list[TickerScorecard]:
    chunk = chunk_size or settings.scanner_chunk_size
    timeout = settings.scanner_ticker_timeout_secs
    total = len(tickers)

    def _report(phase: str, done: int, message: str | None = None) -> None:
        if progress:
            progress(phase=phase, done=done, total=total, message=message)

    macro = await score_macro_regime(session)
    macro_score = int(macro.detail.get("score", 0))

    # Refresh contract history for dormant watchlist before scoring.
    # Skipped when download=False — a no-download scan must touch no external source.
    if download:
        _report("download", 0, "Refreshing dormant watchlist history…")
        await _refresh_watchlist_history(session)

    # Pre-load FinBERT once (~14s) OUTSIDE the per-ticker timeout, so heavy-news
    # names (hundreds of articles) never lose their budget to the cold model load.
    _report("warmup", 0, "Loading sentiment model…")
    await asyncio.get_event_loop().run_in_executor(None, warm_up_sentiment)

    today_date = date.today()
    today_str = today_date.isoformat()
    sem = asyncio.Semaphore(settings.scanner_concurrency)

    async def _one(t: str) -> TickerScorecard | None:
        # Per-ticker timeout — one stuck name cannot stall the whole scan.
        async with sem:
            try:
                return await asyncio.wait_for(_score_ticker(t, macro, macro_score), timeout=timeout)
            except asyncio.TimeoutError:
                log.warning("ticker_timeout", ticker=t, secs=timeout)
                return None
            except Exception as exc:
                log.warning("ticker_failed_outer", ticker=t, error=str(exc))
                return None

    async def _persist(cards: list[TickerScorecard]) -> None:
        # All aggregate writes happen here on the single shared session, AFTER the
        # chunk's concurrent scoring (own sessions) has finished — never overlapping.
        for sc in cards:
            factors_firing = sum([
                sc.technical.firing, sc.gex.firing,
                sc.flow.firing, sc.dormant.firing, sc.sentiment.firing,
            ])
            vals = dict(
                ta_strength=sc.technical.strength, ta_label=sc.technical.label,
                ta_tier=(sc.technical.detail or {}).get("probability_tier"),
                gex_strength=sc.gex.strength, gex_label=sc.gex.label,
                flow_strength=sc.flow.strength, flow_label=sc.flow.label,
                dormant_strength=sc.dormant.strength, dormant_label=sc.dormant.label,
                sentiment_strength=sc.sentiment.strength, sentiment_label=sc.sentiment.label,
                macro_score=macro_score, spot_price=sc.spot_price,
                factors_firing=factors_firing, updated_at=datetime.utcnow(),
            )
            stmt = upsert(FactorScore).values(
                date=today_date, ticker=sc.ticker, **vals
            ).on_conflict_do_update(index_elements=["date", "ticker"], set_=vals)
            await session.execute(stmt)

            if sc.technical.firing and sc.technical.label:
                direction = "short" if sc.technical.label in SHORT_SETUP_PATTERNS else "long"
                ez = entry_zone(sc)
                sl = stop_level(sc)
                try:
                    await write_signal_trigger(
                        session, ticker=sc.ticker, scan_date=today_str,
                        setup_type=sc.technical.label, direction=direction,
                        entry_low=ez[0], entry_high=ez[1], stop=sl,
                        target=sc.target, confidence=sc.technical.strength,
                    )
                except Exception as exc:
                    log.warning("signal_trigger_write_failed", ticker=sc.ticker, error=str(exc))
        await session.commit()

    # ── Score in chunks; commit + report after each → live progress, no giant lock ──
    scorecards: list[TickerScorecard] = []
    done = 0
    _report("score", 0, f"Scoring 0/{total}…")
    for i in range(0, total, chunk):
        batch = tickers[i:i + chunk]
        results = await asyncio.gather(*[_one(t) for t in batch])
        cards = [r for r in results if r is not None]
        scorecards.extend(cards)
        await _persist(cards)
        # Trickle picks: write this chunk's qualifiers immediately so DAILY fills in
        # batches as scoring progresses (the UI polls /api/picks every 2s). qualify_pick
        # is per-scorecard independent and write_picks upserts, so the final full-set
        # rank/write below is an idempotent reconcile, not a conflict.
        try:
            chunk_qualified = rank_picks(cards, macro_score)
            if chunk_qualified:
                await write_picks(chunk_qualified, macro_score, session, all_scorecards=cards)
                await session.commit()
        except Exception as exc:
            log.warning("trickle_write_failed", error=str(exc))
        done += len(batch)
        _report("score", done, f"Scored {done}/{total}…")

    # ── Account for EVERY input ticker — a scored set smaller than the input means
    #    some names dropped (timeout/error/no-data). Never silent: surface count + names. ──
    scored_set = {sc.ticker for sc in scorecards}
    dropped = [t for t in tickers if t not in scored_set]
    if dropped:
        log.warning("scan.dropped_tickers", count=len(dropped), total=total, tickers=dropped)
        _report("rank", total, f"⚠ {len(dropped)} dropped (not scored): {', '.join(dropped)}")

    # ── Rank + write picks (needs the full set) ──
    _report("rank", total, "Ranking picks…")
    qualified = rank_picks(scorecards, macro_score)
    await write_picks(qualified, macro_score, session, all_scorecards=scorecards)
    await session.commit()

    # ── LLM theses (only network step; bounded, reported) ──
    n_q = len(qualified)
    _report("thesis", 0, f"Generating theses 0/{n_q}…")
    try:
        from datetime import date as _date

        from sqlalchemy import update

        from eigenview.data.storage import Pick
        from eigenview.llm.thesis import generate_thesis

        # Phase 1 — generate theses (network). generate_thesis writes its own llm_log
        # on a separate session; keep the main session idle here so those commits never
        # contend with an open Pick-write txn (the cause of the SQLite "database is locked").
        theses: dict[str, str] = {}
        for j, sc in enumerate(qualified, 1):
            if sc.technical.label == "NO DATA":
                log.warning("thesis_skipped_no_data", ticker=sc.ticker)
                continue
            factors_dict = {
                f.factor_id: {"firing": f.firing, "label": f.label, "detail": f.detail}
                for f in [sc.technical, sc.gex, sc.flow, sc.dormant, sc.sentiment]
            }
            direction = "short" if sc.technical.label in SHORT_SETUP_PATTERNS else "long"
            ez = entry_zone(sc)
            sl = stop_level(sc)
            entry_ref = ez[0] if direction == "short" else ez[1]
            rr = (round(abs(sc.target - entry_ref) / abs(entry_ref - sl), 2)
                  if sc.target and entry_ref != sl else None)
            ctx = {
                "ticker": sc.ticker,
                "direction": direction,
                "setup": setup_type(sc),
                "entry_low": ez[0], "entry_high": ez[1],
                "stop": sl, "target": sc.target, "rr": rr,
                "conviction": conviction_score(sc),
                "price": sc.spot_price,
                "catalyst": None,
                "macro_label": sc.macro.label,
                "factors": factors_dict,
            }
            theses[sc.ticker] = await generate_thesis(ctx)
            _report("thesis", j, f"Generating theses {j}/{n_q}…")
        # Phase 2 — write all theses in one short transaction (no concurrent writer).
        for ticker, thesis in theses.items():
            await session.execute(
                update(Pick)
                .where(Pick.ticker == ticker, Pick.date == _date.today())
                .values(thesis=thesis)
            )
        await session.commit()
    except Exception as exc:
        log.warning("thesis_generation_failed", error=str(exc))

    _report("done", total, f"Done — {n_q} pick{'s' if n_q != 1 else ''}")
    return qualified
