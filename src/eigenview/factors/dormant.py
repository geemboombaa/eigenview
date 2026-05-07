from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Catalyst, DormantBet
from eigenview.factors.base import FactorResult

log = structlog.get_logger(__name__)

_FACTOR_ID = "dormant"
_MAX_SCORE = 9


@dataclass
class _ChainRow:
    """Minimal interface for current chain rows (accepts both ORM and mock objects)."""
    strike: float
    call_put: str
    oi: int | None


def _build_chain_index(current_chains: list) -> dict[tuple[float, str], int]:
    """Map (strike, call_put) → current OI from today's chain snapshot."""
    index: dict[tuple[float, str], int] = {}
    for row in current_chains:
        key = (float(row.strike), str(row.call_put))
        index[key] = int(row.oi or 0)
    return index


async def _has_catalyst_near(ticker: str, session: AsyncSession, days: int = 14) -> bool:
    rows = await session.execute(
        select(Catalyst).where(
            Catalyst.ticker == ticker,
            Catalyst.days_from_now >= 0,
            Catalyst.days_from_now <= days,
        )
    )
    return rows.scalars().first() is not None


def _score_bet(
    bet: DormantBet,
    chain_index: dict[tuple[float, str], int],
    spot_price: float,
    catalyst_near: bool,
) -> int:
    score = 0

    # sig1 — OI growth
    current_oi = chain_index.get((float(bet.strike), str(bet.call_put)), None)
    if current_oi is not None and bet.original_oi and bet.original_oi > 0:
        growth = (current_oi - bet.original_oi) / bet.original_oi
        if growth > 0.1:
            score += 2

    # sig2 — catalyst within 14 days
    if catalyst_near:
        score += 2

    # sig3 — strike proximity to spot (within 5%)
    if spot_price > 0 and abs(bet.strike - spot_price) / spot_price < 0.05:
        score += 2

    # sig4 — large original premium
    if bet.original_premium and bet.original_premium >= 1_000_000:
        score += 1

    # sig5 — was long-dated at open
    if bet.expiry and bet.original_date and (bet.expiry - bet.original_date).days >= 90:
        score += 1

    # sig6 — still has meaningful time
    if bet.expiry and bet.expiry > date.today() + timedelta(days=7):
        score += 1

    return score


async def score_dormant(
    ticker: str,
    session: AsyncSession,
    spot_price: float,
    current_chains: list,
    days_of_history: int = 30,
) -> FactorResult:
    if days_of_history < 30:
        return FactorResult(
            factor_id=_FACTOR_ID,
            firing=False,
            strength=0.0,
            label="ACCUMULATING",
            narrative=(
                f"Chain history {days_of_history}/30 days. "
                "Dormant radar activates after 30 days of data."
            ),
        )

    rows = await session.execute(select(DormantBet).where(DormantBet.ticker == ticker))
    bets = rows.scalars().all()

    if not bets:
        return FactorResult(
            factor_id=_FACTOR_ID,
            firing=False,
            strength=0.0,
            label="ACCUMULATING",
            detail={},
            narrative="No dormant bets tracked yet. Accumulating chain history.",
        )

    chain_index = _build_chain_index(current_chains)
    catalyst_near = await _has_catalyst_near(ticker, session)

    best_score = 0
    best_bet: DormantBet | None = None
    for bet in bets:
        s = _score_bet(bet, chain_index, spot_price, catalyst_near)
        if s > best_score:
            best_score = s
            best_bet = bet

    activation_probability = best_score / _MAX_SCORE
    fires = activation_probability >= settings.dormant_firing_threshold

    assert best_bet is not None  # guaranteed — bets is non-empty

    current_oi_val = chain_index.get((float(best_bet.strike), str(best_bet.call_put)))
    oi_growth_pct: float | None = None
    if current_oi_val is not None and best_bet.original_oi and best_bet.original_oi > 0:
        oi_growth_pct = (current_oi_val - best_bet.original_oi) / best_bet.original_oi * 100

    premium_m = (best_bet.original_premium or 0) / 1_000_000
    narrative_parts = [
        f"Dormant ${premium_m:.1f}M {best_bet.call_put} at ${best_bet.strike:.0f} (exp {best_bet.expiry}) activating."
    ]
    if oi_growth_pct is not None and oi_growth_pct > 0:
        narrative_parts.append(f"OI growing +{oi_growth_pct:.0f}%.")
    if catalyst_near:
        narrative_parts.append("Catalyst within 14 days.")
    if spot_price > 0 and abs(best_bet.strike - spot_price) / spot_price < 0.05:
        prox = abs(best_bet.strike - spot_price) / spot_price * 100
        narrative_parts.append(f"Strike within {prox:.1f}% of spot.")

    return FactorResult(
        factor_id=_FACTOR_ID,
        firing=fires,
        strength=activation_probability,
        label="ACTIVE" if fires else "DORMANT",
        detail={
            "activation_probability": round(activation_probability, 3),
            "best_bet_strike": best_bet.strike,
            "best_bet_expiry": str(best_bet.expiry),
            "best_score": best_score,
        },
        narrative=" ".join(narrative_parts),
    )
