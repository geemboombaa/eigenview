from __future__ import annotations

import json
from datetime import date

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from eigenview.data.storage import AsyncSessionLocal, Pick

router = APIRouter()


def recommend_structure(setup_type: str, direction: str | None, iv_rank: float | None) -> dict:
    iv = iv_rank or 50.0
    d = (direction or "long").lower()
    if d == "long":
        if setup_type in ("breakout", "compression") and iv < 50:
            return {
                "type": "bull_call_spread",
                "description": "Bull Call Spread",
                "legs": "Buy ATM call / Sell OTM call, same expiry",
                "rationale": f"IV rank {iv:.0f} — spread captures the move cheaply",
            }
        elif setup_type == "pullback" and iv < 40:
            return {
                "type": "long_call",
                "description": "Long Call",
                "legs": "Buy ATM-to-slightly-OTM call",
                "rationale": f"Low IV rank {iv:.0f}, pullback entry = good call buying spot",
            }
        else:
            return {
                "type": "bull_call_spread",
                "description": "Bull Call Spread",
                "legs": "Buy call / Sell higher strike, same expiry",
                "rationale": f"IV rank {iv:.0f} — defined risk spread",
            }
    else:
        return {
            "type": "bear_put_spread",
            "description": "Bear Put Spread",
            "legs": "Buy ATM put / Sell OTM put, same expiry",
            "rationale": "Short setup — defined risk spread",
        }


def _pick_to_dict(p: Pick) -> dict:
    factors_raw: dict = {}
    if p.factors_json:
        try:
            factors_raw = json.loads(p.factors_json)
        except Exception:
            pass

    structure = recommend_structure(
        p.setup_type or "breakout",
        p.direction or "long",
        None,
    )

    return {
        "ticker": p.ticker,
        "date": str(p.date),
        "conviction": p.conviction or 1,
        "setup_type": p.setup_type or "unknown",
        "direction": p.direction or "long",
        "entry_low": p.entry_low,
        "entry_high": p.entry_high,
        "stop": p.stop,
        "thesis": p.thesis or "",
        "spot": None,
        "iv_rank": None,
        "structure": structure,
        "factors": factors_raw,
    }


@router.get("/picks")
async def get_picks() -> list:
    today = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick)
            .where(Pick.date == today)
            .order_by(Pick.conviction.desc())
        )
        picks = result.scalars().all()
    return [_pick_to_dict(p) for p in picks]


@router.get("/pick/{ticker}")
async def get_pick(ticker: str) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick).where(Pick.date == today, Pick.ticker == ticker.upper())
        )
        pick = result.scalar_one_or_none()
    if pick is None:
        raise HTTPException(status_code=404, detail=f"No pick for {ticker} today")
    return _pick_to_dict(pick)


@router.get("/pick/{ticker}/factors")
async def get_pick_factors(ticker: str) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick).where(Pick.date == today, Pick.ticker == ticker.upper())
        )
        pick = result.scalar_one_or_none()
    if pick is None:
        raise HTTPException(status_code=404, detail=f"No pick for {ticker} today")
    if not pick.factors_json:
        return {}
    try:
        return json.loads(pick.factors_json)
    except Exception:
        return {}
