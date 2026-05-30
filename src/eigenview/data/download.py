from __future__ import annotations

import asyncio
import os
import sqlite3

import structlog

from eigenview.config import settings

log = structlog.get_logger(__name__)


def download_universe_data(tickers: list[str]) -> None:
    """Blocking: pull fresh prices + option chains from Databento for these tickers.

    Opens its own sqlite connection (raw, separate from the async engine) and sets
    busy_timeout so it waits on a lock instead of erroring instantly when the async
    engine commits concurrently. Run inside an executor thread by download_chunked().
    """
    import sys

    scripts_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts")
    )
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)

    import databento as _db
    from databento_load import DB_PATH, load_equities, load_key, load_options

    from eigenview.data.universe import get_options_universe

    client = _db.Historical(load_key())
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout=30000")
    try:
        # Prices/equities: ALL passed tickers (TA, sentiment, macro need the full universe).
        load_equities(client, tickers, con)
        # Options/chains: ONLY the broker-screened options universe (the 184-name list).
        opts_set = set(get_options_universe())
        opts = [t for t in tickers if t in opts_set]
        if opts:
            load_options(client, opts, con)
    finally:
        con.close()


async def download_chunked(
    tickers: list[str],
    chunk: int | None = None,
    timeout: float = 300.0,
    progress=None,
    concurrency: int | None = None,
) -> None:
    """Chunked download with bounded concurrency: up to `concurrency` chunks in flight
    at once (asyncio.gather + semaphore), each in its own executor thread with its own
    sqlite connection. Each chunk's prices+chains commit as they land — data trickles in.

    Each chunk has a hard timeout so one stuck Databento call can't hang the run (the
    abandoned thread dies on its own); a failed/timed-out chunk is logged and skipped.
    Concurrency is bounded (default settings.download_concurrency) because Databento
    throttles — too many parallel streams raise 504/429.
    """
    loop = asyncio.get_event_loop()
    n = len(tickers)
    step = chunk or settings.scanner_chunk_size
    sem = asyncio.Semaphore(concurrency or settings.download_concurrency)
    done = 0

    async def run_chunk(i: int, batch: list[str]) -> None:
        nonlocal done
        async with sem:
            try:
                await asyncio.wait_for(
                    loop.run_in_executor(None, download_universe_data, batch),
                    timeout=timeout,
                )
            except (Exception, asyncio.TimeoutError) as exc:
                log.warning("download_chunk_failed", start=i, error=str(exc))
        done += len(batch)
        if progress:
            progress(done, n)

    await asyncio.gather(
        *(run_chunk(i, tickers[i:i + step]) for i in range(0, n, step))
    )
