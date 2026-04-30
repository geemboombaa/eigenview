from __future__ import annotations

import asyncio
import sys

import typer
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


@app.command(name="init-db")
def init_db() -> None:
    """Create all DB tables if they don't exist."""

    async def _run() -> None:
        typer.echo("Initializing database tables...")
        await create_tables()
        typer.echo("Done.")

    asyncio.run(_run())
