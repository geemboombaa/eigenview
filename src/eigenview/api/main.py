from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eigenview.api.routes import bench, chart, chat, heat, layouts, market, picks, spec, ta_scan
from eigenview.data.storage import create_tables


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
    "running": False, "message": "idle", "picks": 0, "error": None, "last_scan_at": None
}


@app.get("/api/scan/status")
async def scan_status() -> dict:
    return _scan_state


@app.post("/api/scan")
async def trigger_scan(universe: str = "ndx100") -> dict:
    global _scan_state
    if _scan_state["running"]:
        return {"status": "already_running", **_scan_state}

    last_at = _scan_state.get("last_scan_at")
    if last_at:
        elapsed = (datetime.now() - last_at).total_seconds()
        if elapsed < _SCAN_COOLDOWN_SECS:
            mins_left = int((_SCAN_COOLDOWN_SECS - elapsed) / 60)
            return {
                "status": "too_recent",
                "message": f"Scanned {int(elapsed/60)}m ago — next available in {mins_left}m",
                **_scan_state,
            }

    async def _do_scan() -> None:
        global _scan_state
        _scan_state = {"running": True, "message": "Fetching data…", "picks": 0, "error": None, "last_scan_at": _scan_state.get("last_scan_at")}
        try:
            from eigenview.cli import NDX100, SP500, TEST5, _SP500_NDX100
            from eigenview.data.storage import AsyncSessionLocal
            from eigenview.synthesis.scanner import run_daily_scan
            if universe == "ndx100":
                tickers = NDX100
            elif universe == "sp500":
                tickers = SP500
            elif universe == "full":
                tickers = _SP500_NDX100
            else:
                tickers = TEST5
            _scan_state["message"] = f"Scanning {len(tickers)} tickers…"
            async with AsyncSessionLocal() as session:
                qualified = await run_daily_scan(tickers, session)
                await session.commit()
            n = len(qualified)
            _scan_state = {
                "running": False,
                "message": f"Done — {n} pick{'s' if n != 1 else ''}",
                "picks": n,
                "error": None,
                "last_scan_at": datetime.now(),
            }
        except Exception as exc:
            _scan_state = {
                "running": False, "message": "Scan failed", "picks": 0,
                "error": str(exc), "last_scan_at": _scan_state.get("last_scan_at"),
            }

    asyncio.create_task(_do_scan())
    return {"status": "started"}


# Serve web/ as static files — AFTER all API routes
_web_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)
if os.path.exists(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="static")
