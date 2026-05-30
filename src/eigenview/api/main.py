from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eigenview.api.routes import bench, chart, chat, heat, layouts, market, picks, spec, ta_scan
from eigenview.data.storage import create_tables

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    yield


app = FastAPI(title="EigenView API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api")
app.include_router(picks.router, prefix="/api")
app.include_router(bench.router, prefix="/api")
app.include_router(chart.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(layouts.router, prefix="/api")
app.include_router(heat.router, prefix="/api")
app.include_router(spec.router, prefix="/api")
app.include_router(ta_scan.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "eigenview"}


_SCAN_COOLDOWN_SECS = 4 * 3600  # 4 hours

_scan_state: dict = {
    "running": False, "message": "idle", "phase": "idle", "done": 0, "total": 0,
    "picks": 0, "error": None, "last_scan_at": None
}
_scan_bg_tasks: set = set()


@app.get("/api/scan/status")
async def scan_status() -> dict:
    return _scan_state


@app.post("/api/scan")
async def trigger_scan(universe: str | None = None, download: bool = False) -> dict:
    global _scan_state
    from eigenview.config import settings as _settings
    universe = universe or _settings.scanner_universe   # default: both (NDX ∪ SP500)
    if _scan_state["running"]:
        return {"status": "already_running", **_scan_state}

    # SCAN is an explicit user action → always force-run. The only guard is "already
    # running" (can't run two at once). No time-of-day / cooldown gating.

    async def _do_scan() -> None:
        global _scan_state
        _scan_state = {
            "running": True, "message": "Starting…", "phase": "start", "done": 0, "total": 0,
            "picks": 0, "error": None, "last_scan_at": _scan_state.get("last_scan_at"),
        }

        def _progress(phase: str, done: int, total: int, message: str | None = None) -> None:
            _scan_state["phase"] = phase
            _scan_state["done"] = done
            _scan_state["total"] = total
            if message:
                _scan_state["message"] = message

        try:
            from eigenview.data.storage import AsyncSessionLocal, write_universe_membership
            from eigenview.data.universe import get_index_lists
            from eigenview.synthesis.scanner import run_daily_scan

            # Resolve scope from the already-wired NDX / SP500 lists, and tag membership
            # from those same lists — no new data source.
            ndx, sp = await get_index_lists()
            if not ndx and not sp:
                raise RuntimeError("Failed to load NDX/SP500 member lists")
            async with AsyncSessionLocal() as s:
                await write_universe_membership(s, ndx, sp)
                await s.commit()
            if universe == "sp500":
                tickers = sorted(set(sp))
            elif universe == "ndx100":
                tickers = sorted(set(ndx))
            else:
                tickers = sorted(set(ndx) | set(sp))
            _scan_state["total"] = len(tickers)

            if download:
                # Fresh macro (free scrape) then fresh prices + chains (paid Databento).
                _scan_state["phase"] = "download"
                _scan_state["message"] = "Downloading: macro…"
                try:
                    from eigenview.data.macro import fetch_macro
                    await fetch_macro()
                except Exception:
                    pass  # macro is non-fatal — pipeline still runs on existing macro_daily
                # Chunked async download (shared module): one executor call per chunk,
                # event loop free between chunks, per-chunk timeout, data trickles in.
                from eigenview.data.download import download_chunked
                ntk = len(tickers)

                def _dl_progress(done: int, total: int) -> None:
                    _scan_state["phase"] = "download"
                    _scan_state["done"] = done
                    _scan_state["message"] = f"Downloading prices + chains {done}/{total}…"

                await download_chunked(tickers, progress=_dl_progress)

                # News (free: Alpha Vantage + Finnhub) so sentiment can fire. Bounded
                # concurrency; each fetch_news upserts to the news table and fails soft
                # on rate limits (AV free = 25/day → mostly Finnhub for the bulk).
                _scan_state["message"] = f"Downloading: news for {len(tickers)} tickers…"
                from eigenview.data.news import fetch_news
                _news_sem = asyncio.Semaphore(8)

                async def _one_news(t: str) -> None:
                    async with _news_sem:
                        try:
                            await fetch_news(t)
                        except Exception:
                            pass

                await asyncio.gather(*[_one_news(t) for t in tickers])

            async with AsyncSessionLocal() as session:
                qualified = await run_daily_scan(
                    tickers, session, download=download, progress=_progress
                )
                await session.commit()
            n = len(qualified)
            _scan_state = {
                "running": False,
                "message": f"Done — {n} pick{'s' if n != 1 else ''}",
                "phase": "done", "done": len(tickers), "total": len(tickers),
                "picks": n, "error": None, "last_scan_at": datetime.now(),
            }
        except Exception as exc:
            _scan_state = {
                "running": False, "message": "Scan failed", "phase": "error",
                "done": _scan_state.get("done", 0), "total": _scan_state.get("total", 0),
                "picks": 0, "error": str(exc), "last_scan_at": _scan_state.get("last_scan_at"),
            }

    task = asyncio.create_task(_do_scan())
    _scan_bg_tasks.add(task)
    task.add_done_callback(_scan_bg_tasks.discard)
    return {"status": "started"}


# Serve web/ as static files — AFTER all API routes
_web_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)
if os.path.exists(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="static")
