from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, distinct

from eigenview.data.storage import AsyncSessionLocal, FactorScore, Pick

log = structlog.get_logger(__name__)
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


def _pick_to_dict(p: Pick, spot: float | None = None) -> dict:
    factors_raw: dict = {}
    if p.factors_json:
        try:
            factors_raw = json.loads(p.factors_json)
        except Exception as exc:
            log.warning("picks_factors_parse_error", ticker=p.ticker, error=str(exc))

    # Compute signal freshness
    signal_fired_at = p.signal_fired_at
    freshness_label = "unknown"
    signal_age_hours = None
    if signal_fired_at:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        delta_h = (now - signal_fired_at).total_seconds() / 3600
        signal_age_hours = round(delta_h, 1)
        if delta_h < 2:
            freshness_label = "fresh"
        elif delta_h < 8:
            freshness_label = "valid"
        else:
            freshness_label = "stale"

    # Extract iv_rank from factors if stored
    iv_rank = None
    ta_detail = factors_raw.get("technical", {}).get("detail", {})
    iv_rank = factors_raw.get("iv_rank") or ta_detail.get("iv_rank")

    structure = recommend_structure(
        p.setup_type or "breakout",
        p.direction or "long",
        iv_rank,
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
        "target": p.target,
        "ta_tier": ta_detail.get("probability_tier"),
        "thesis": p.thesis or "",
        "spot": spot,
        "iv_rank": iv_rank,
        "signal_fired_at": signal_fired_at.isoformat() if signal_fired_at else None,
        "signal_age_hours": signal_age_hours,
        "freshness": freshness_label,
        "structure": structure,
        "factors": factors_raw,
    }


@router.get("/picks/week")
async def get_picks_week(days: int = 7) -> list:
    """Picks from last `days` days, excluding today. Used for the Prior Picks panel."""
    today = date.today()
    start = today - timedelta(days=days)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick)
            .where(Pick.date >= start, Pick.date < today)
            .order_by(Pick.date.desc(), Pick.conviction.desc())
        )
        picks = result.scalars().all()
        spot_result = await session.execute(
            select(FactorScore.ticker, FactorScore.date, FactorScore.spot_price)
            .where(FactorScore.date >= start, FactorScore.date < today)
        )
        spot_map = {(r[0], str(r[1])): r[2] for r in spot_result}
    return [_pick_to_dict(p, spot_map.get((p.ticker, str(p.date)))) for p in picks]


@router.get("/picks/dates")
async def get_pick_dates() -> list[str]:
    """Return all dates that have at least one pick, most recent first."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(distinct(Pick.date)).order_by(Pick.date.desc())
        )
        dates = result.scalars().all()
    return [str(d) for d in dates]


@router.get("/picks")
async def get_picks(date_str: str = Query(None, alias="date")) -> list:
    if date_str:
        try:
            target = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")
    else:
        target = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick)
            .where(Pick.date == target)
            .order_by(Pick.conviction.desc())
        )
        picks = result.scalars().all()
        # Fetch spot prices from factor_scores for this date
        spot_result = await session.execute(
            select(FactorScore.ticker, FactorScore.spot_price)
            .where(FactorScore.date == target)
        )
        spot_map: dict[str, float | None] = {row[0]: row[1] for row in spot_result}
    return [_pick_to_dict(p, spot_map.get(p.ticker)) for p in picks]


@router.get("/pick/{ticker}")
async def get_pick(ticker: str) -> dict:
    today = date.today()
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Pick).where(Pick.date == today, Pick.ticker == ticker.upper())
        )
        pick = result.scalar_one_or_none()
        spot: float | None = None
        if pick is not None:
            fs_result = await session.execute(
                select(FactorScore.spot_price)
                .where(FactorScore.date == today, FactorScore.ticker == ticker.upper())
            )
            spot = fs_result.scalar_one_or_none()
    if pick is None:
        raise HTTPException(status_code=404, detail=f"No pick for {ticker} today")
    return _pick_to_dict(pick, spot)


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
    except Exception as exc:
        log.warning("picks_factors_json_error", ticker=ticker, error=str(exc))
        return {}
