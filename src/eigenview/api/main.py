from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from eigenview.api.routes import chart, chat, layouts, market, picks

app = FastAPI(title="EigenView API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market.router, prefix="/api")
app.include_router(picks.router, prefix="/api")
app.include_router(chart.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(layouts.router, prefix="/api")


@app.get("/api/health")
async def health() -> dict:
    return {"status": "ok", "service": "eigenview"}


# Serve web/ as static files — AFTER all API routes
_web_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)
if os.path.exists(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="static")
