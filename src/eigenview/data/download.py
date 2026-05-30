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

    client = _db.Historical(load_key())
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA busy_timeout=30000")
    try:
        load_equities(client, tickers, con)
        load_options(client, tickers, con)
    finally:
        con.close()


async def download_chunked(
    tickers: list[str],
    chunk: int | None = None,
    timeout: float = 300.0,
    progress=None,
) -> None:
    """Chunked async download: one executor call per chunk (not a single monolith).

    The event loop is released between chunks (UI/poll stays live) and each chunk's
    prices+chains commit to the DB as they land — data trickles in. Each chunk has a
    hard timeout so one stuck Databento call can't hang the run (the abandoned thread
    dies on its own); a failed/timed-out chunk is logged and skipped.
    """
    loop = asyncio.get_event_loop()
    n = len(tickers)
    step = chunk or settings.scanner_chunk_size
    for i in range(0, n, step):
        batch = tickers[i:i + step]
        if progress:
            progress(i, n)
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, download_universe_data, batch),
                timeout=timeout,
            )
        except (Exception, asyncio.TimeoutError) as exc:
            log.warning("download_chunk_failed", start=i, error=str(exc))
    if progress:
        progress(n, n)
