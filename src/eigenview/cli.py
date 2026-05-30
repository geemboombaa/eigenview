from __future__ import annotations

import asyncio
import sys

import structlog
import typer

log = structlog.get_logger(__name__)

# Windows cp1252 console can't render non-BMP chars from external data
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
from sqlalchemy import func, select, text

from eigenview.data.storage import (
    AsyncSessionLocal,
    Catalyst,
    Chain,
    CotWeekly,
    MacroDaily,
    NewsItem,
    Pick,
    Price,
    create_tables,
)
from eigenview.synthesis.gate import conviction_score, entry_zone, setup_type, stop_level
from eigenview.synthesis.scanner import run_daily_scan

# Windows asyncio fix — must be set before any async work
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command()
def fetch(ticker: str) -> None:
    """Fetch all data for one ticker and write to DB."""

    async def _run() -> None:
        from eigenview.data.chains import fetch_chain
        from eigenview.data.news import fetch_news
        from eigenview.data.prices import fetch_prices

        ticker_upper = ticker.upper()
        typer.echo(f"Fetching data for {ticker_upper}...")

        results: dict[str, int | str] = {}

        # Prices
        try:
            df = await fetch_prices(ticker_upper)
            results["prices"] = len(df)
        except Exception as exc:
            results["prices"] = f"ERROR: {exc}"

        # Options chain
        try:
            chain_df = await fetch_chain(ticker_upper)
            results["chains"] = len(chain_df)
        except Exception as exc:
            results["chains"] = f"ERROR: {exc}"

        # News
        try:
            news = await fetch_news(ticker_upper)
            results["news"] = len(news)
        except Exception as exc:
            results["news"] = f"ERROR: {exc}"

        typer.echo("\nFetch summary:")
        for table, val in results.items():
            typer.echo(f"  {table:<12} {val}")

    asyncio.run(_run())


@app.command(name="fetch-macro")
def fetch_macro_cmd() -> None:
    """Fetch macro signals (DIX, VIX term structure, COT)."""

    async def _run() -> None:
        from eigenview.data.macro import fetch_macro

        typer.echo("Fetching macro signals...")
        data = await fetch_macro()

        typer.echo(f"\n  date             {data['date']}")
        typer.echo(f"  dix              {data['dix']}")
        typer.echo(f"  gex_index        {data['gex_index']}")
        typer.echo(f"  vix_m1           {data['vix_m1']}")
        typer.echo(f"  vix_m2           {data['vix_m2']}")
        typer.echo(f"  vix_m3           {data['vix_m3']}")
        typer.echo(f"  contango_pct     {data['vix_contango_pct']}")
        typer.echo(f"  cot_es_net_long  {data['cot_es_net_long_pct']}")

    asyncio.run(_run())


async def _resolve_news_scope(scope: str, limit: int | None) -> list[str]:
    """Resolve the ticker list for the news-refresh job from a scope name."""
    scope = scope.lower()
    if scope == "picks":
        from datetime import date as _date

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Pick.ticker).where(Pick.date == _date.today()).distinct()
            )
            tickers = [t.upper() for (t,) in result.all()]
    elif scope in ("sp500", "ndx100"):
        from eigenview.data.universe import get_universe

        tickers = await get_universe(scope)
    elif scope == "all":
        from eigenview.data.universe import get_index_lists

        ndx, sp = await get_index_lists()
        tickers = sorted(set(ndx) | set(sp))
    else:
        raise ValueError(f"unknown scope '{scope}' (all|sp500|ndx100|picks)")

    if limit is not None and limit > 0:
        tickers = tickers[:limit]
    return tickers


async def refresh_news(scope: str = "all", limit: int | None = None) -> dict[str, int]:
    """Decoupled news refresh for the scan universe.

    Finnhub fetches every ticker (bulk-safe, ~60 req/min). Alpha Vantage's
    25/day free budget is reserved for a small subset only — today's picks if
    available, else the first N tickers — so a 600-name bulk run never throttles
    AV. Bounded concurrency, fail-soft per ticker. Idempotent (URL-hash dedup).

    Returns counts: {tickers, ok, failed, articles, av_tickers}.
    """
    from eigenview.config import settings as _settings
    from eigenview.data.news import fetch_news

    tickers = await _resolve_news_scope(scope, limit)
    if not tickers:
        log.info("refresh_news.empty", scope=scope)
        return {"tickers": 0, "ok": 0, "failed": 0, "articles": 0, "av_tickers": 0}

    # AV path: today's picks (small), else first-N up to the daily budget.
    budget = _settings.news_av_daily_budget
    if scope == "picks":
        av_set = set(tickers[:budget])
    else:
        try:
            picks = await _resolve_news_scope("picks", None)
        except Exception:
            picks = []
        av_candidates = [t for t in tickers if t in set(picks)] or tickers
        av_set = set(av_candidates[:budget])

    sem = asyncio.Semaphore(_settings.news_refresh_concurrency)
    counts = {"ok": 0, "failed": 0, "articles": 0}

    async def _one(tk: str) -> None:
        srcs = ("av", "finnhub") if tk in av_set else ("finnhub",)
        async with sem:
            try:
                arts = await fetch_news(
                    tk, lookback_days=_settings.news_lookback_days, sources=srcs
                )
                counts["ok"] += 1
                counts["articles"] += len(arts)
            except Exception as exc:  # fail-soft: one ticker never wedges the run
                counts["failed"] += 1
                log.warning("refresh_news.ticker_failed", ticker=tk, error=str(exc))

    await asyncio.gather(*(_one(tk) for tk in tickers))

    result = {
        "tickers": len(tickers),
        "ok": counts["ok"],
        "failed": counts["failed"],
        "articles": counts["articles"],
        "av_tickers": len(av_set),
    }
    log.info("refresh_news.done", scope=scope, **result)
    return result


@app.command(name="fetch-news")
def fetch_news_cmd(
    scope: str = typer.Option("all", help="all | sp500 | ndx100 | picks"),
    limit: int = typer.Option(0, help="Cap tickers (0 = no cap)"),
) -> None:
    """Refresh the news table for the scan universe (decoupled from daily scan).

    Finnhub covers the full universe in bulk; Alpha Vantage (25/day free) is
    reserved for today's picks / a capped subset. Run intraday + pre-market.

    Schedule via Windows Task Scheduler (run from the repo root, adjust paths):

        schtasks /Create /TN "EigenView-NewsPremarket" /SC DAILY /ST 08:00 ^
          /TR "C:\\Users\\v_per\\Claude\\Projects\\Eigenview\\.venv\\Scripts\\eigenview.exe fetch-news --scope all" /F

        schtasks /Create /TN "EigenView-NewsIntraday" /SC MINUTE /MO 90 ^
          /ST 09:30 /ET 16:00 /K ^
          /TR "C:\\Users\\v_per\\Claude\\Projects\\Eigenview\\.venv\\Scripts\\eigenview.exe fetch-news --scope picks" /F
    """

    async def _run() -> None:
        lim = limit if limit > 0 else None
        typer.echo(f"Refreshing news — scope={scope} limit={lim or 'none'} ...")
        try:
            res = await refresh_news(scope=scope, limit=lim)
        except ValueError as exc:
            typer.echo(f"ERROR: {exc}")
            raise typer.Exit(code=1) from exc
        typer.echo(
            f"\n  tickers     {res['tickers']}"
            f"\n  ok          {res['ok']}"
            f"\n  failed      {res['failed']}"
            f"\n  articles    {res['articles']}"
            f"\n  av_tickers  {res['av_tickers']}"
        )

    asyncio.run(_run())


@app.command()
def status() -> None:
    """Print DB row counts and latest timestamps per table."""

    async def _run() -> None:
        tables = [
            ("prices", Price, "fetched_at"),
            ("chains", Chain, "snapshot_date"),
            ("news", NewsItem, "fetched_at"),
            ("catalysts", Catalyst, "updated_at"),
            ("macro_daily", MacroDaily, "fetched_at"),
            ("cot_weekly", CotWeekly, "week_ending"),
            ("picks", Pick, "created_at"),
        ]

        typer.echo(f"\n{'Table':<16} {'Rows':>8}  {'Latest'}")
        typer.echo("-" * 50)

        async with AsyncSessionLocal() as session:
            for table_name, model, ts_col in tables:
                try:
                    count_result = await session.execute(
                        select(func.count()).select_from(model)
                    )
                    count = count_result.scalar_one()

                    ts_attr = getattr(model, ts_col, None)
                    if ts_attr is not None:
                        latest_result = await session.execute(
                            select(func.max(ts_attr))
                        )
                        latest = latest_result.scalar_one()
                    else:
                        latest = "—"

                    typer.echo(f"{table_name:<16} {count:>8}  {latest or '—'}")
                except Exception as exc:
                    typer.echo(f"{table_name:<16} {'ERROR':>8}  {exc}")

    asyncio.run(_run())


@app.command(name="daily-scan")
def daily_scan(
    universe: str = typer.Option("ndx100", help="ndx100 | sp500"),
    tickers_csv: str = typer.Option("", "--tickers", help="Comma-separated tickers (overrides universe)"),
) -> None:
    """Run full daily scan pipeline and print top picks."""

    async def _run() -> None:
        if tickers_csv:
            tickers = [t.strip().upper() for t in tickers_csv.split(",") if t.strip()]
            typer.echo(f"Scanning {len(tickers)} tickers: {','.join(tickers)}")
        else:
            from eigenview.data.universe import get_universe
            tickers = await get_universe(universe)
            if not tickers:
                typer.echo(f"Failed to load universe '{universe}' from Wikipedia. Check network.")
                return
            typer.echo(f"Universe '{universe}': {len(tickers)} tickers loaded.")
        async with AsyncSessionLocal() as session:
            qualified = await run_daily_scan(tickers, session)
            await session.commit()
        if not qualified:
            typer.echo("No qualifying picks today.")
            return
        typer.echo(f"\n{'='*60}")
        typer.echo(f"EigenView Daily Scan — {len(qualified)} pick(s)")
        typer.echo(f"{'='*60}")
        for sc in qualified:
            conv = conviction_score(sc)
            stype = setup_type(sc)
            entry_lo, entry_hi = entry_zone(sc)
            stop = stop_level(sc)
            typer.echo(f"\n{sc.ticker} | {stype} | conviction {conv}/5")
            typer.echo(f"  Entry: ${entry_lo}–${entry_hi}  Stop: ${stop}")
            typer.echo(f"  TA: {sc.technical.label}  GEX: {sc.gex.label}  Flow: {sc.flow.label}")

    asyncio.run(_run())


@app.command(name="populate-forward-returns")
def populate_forward_returns(
    lookback_days: int = typer.Option(30, help="Number of days back to populate"),
) -> None:
    """Populate forward_returns table with T+5 and T+20 realized returns."""
    from eigenview.synthesis.forward_returns import populate_recent

    async def _run() -> None:
        typer.echo(f"Populating forward returns for last {lookback_days} days...")
        await populate_recent(lookback_days=lookback_days)
        typer.echo("Done.")

    asyncio.run(_run())


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Auto-reload on file changes"),
) -> None:
    """Start EigenView dashboard server."""
    import uvicorn

    typer.echo(f"EigenView starting at http://{host}:{port}")
    typer.echo("Press Ctrl+C to stop.")
    uvicorn.run("eigenview.api.main:app", host=host, port=port, reload=reload)


@app.command(name="init-db")
def init_db() -> None:
    """Create all DB tables if they don't exist."""

    async def _run() -> None:
        typer.echo("Initializing database tables...")
        import eigenview.data.storage as _storage
        await _storage.create_tables()
        typer.echo("Done.")

    asyncio.run(_run())
