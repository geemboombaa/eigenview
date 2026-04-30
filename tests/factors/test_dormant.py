from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import Catalyst, DormantBet
from eigenview.factors.dormant import score_dormant


@dataclass
class MockChainRow:
    strike: float
    call_put: str
    oi: int | None


_id_counter = 0


def _next_id() -> int:
    global _id_counter
    _id_counter += 1
    return _id_counter


def _make_bet(
    ticker: str = "NVDA",
    strike: float = 650.0,
    call_put: str = "C",
    original_premium: float = 1_200_000,
    original_oi: int = 1000,
    current_oi: int | None = None,
    days_back: int = 60,
    dte_at_open: int = 120,
) -> DormantBet:
    original_date = date.today() - timedelta(days=days_back)
    expiry = original_date + timedelta(days=dte_at_open)
    contract = f"{ticker}{strike}{call_put}"
    return DormantBet(
        id=_next_id(),
        ticker=ticker,
        contract=contract,
        original_date=original_date,
        strike=strike,
        expiry=expiry,
        call_put=call_put,
        original_premium=original_premium,
        original_oi=original_oi,
        current_oi=current_oi,
    )


@pytest.mark.asyncio
async def test_accumulating_state(db_session: AsyncSession) -> None:
    result = await score_dormant(
        ticker="NVDA",
        session=db_session,
        spot_price=660.0,
        current_chains=[],
        days_of_history=10,
    )
    assert result.firing is False
    assert result.label == "ACCUMULATING"
    assert "10/30" in result.narrative


@pytest.mark.asyncio
async def test_no_bets_in_db(db_session: AsyncSession) -> None:
    result = await score_dormant(
        ticker="NVDA",
        session=db_session,
        spot_price=660.0,
        current_chains=[],
        days_of_history=45,
    )
    assert result.firing is False
    assert result.label == "NO DATA"


@pytest.mark.asyncio
async def test_high_score_fires(db_session: AsyncSession) -> None:
    """Bet with catalyst + OI growth + strike proximity → fires."""
    bet = _make_bet(strike=650.0, original_oi=1000, dte_at_open=120)
    db_session.add(bet)

    catalyst = Catalyst(
        id=_next_id(),
        ticker="NVDA",
        event_type="Earnings",
        event_date=date.today() + timedelta(days=5),
        days_from_now=5,
    )
    db_session.add(catalyst)
    await db_session.flush()

    # OI grew from 1000 → 1200 (+20%) and strike is close to spot
    current_chains = [MockChainRow(strike=650.0, call_put="C", oi=1200)]

    result = await score_dormant(
        ticker="NVDA",
        session=db_session,
        spot_price=645.0,  # within 5% of 650
        current_chains=current_chains,
        days_of_history=45,
    )
    assert result.firing is True
    assert result.label == "ACTIVE"
    assert result.detail["activation_probability"] >= 0.6


@pytest.mark.asyncio
async def test_low_score_no_fire(db_session: AsyncSession) -> None:
    """Bet with no catalyst, flat OI, strike far from spot → no fire."""
    bet = _make_bet(strike=400.0, original_oi=1000, original_premium=300_000)
    db_session.add(bet)
    await db_session.flush()

    # OI unchanged, no catalyst, strike far
    current_chains = [MockChainRow(strike=400.0, call_put="C", oi=1000)]

    result = await score_dormant(
        ticker="NVDA",
        session=db_session,
        spot_price=660.0,  # strike 400 is >35% away
        current_chains=current_chains,
        days_of_history=45,
    )
    assert result.firing is False
    assert result.detail["activation_probability"] < 0.6


@pytest.mark.asyncio
async def test_oi_growth_detected(db_session: AsyncSession) -> None:
    """OI growth from 1000 → 1200 should contribute +2 to score."""
    bet = _make_bet(strike=500.0, original_oi=1000, dte_at_open=120)
    db_session.add(bet)
    await db_session.flush()

    current_chains = [MockChainRow(strike=500.0, call_put="C", oi=1200)]

    result = await score_dormant(
        ticker="NVDA",
        session=db_session,
        spot_price=999.0,  # far away — only OI growth signal fires
        current_chains=current_chains,
        days_of_history=45,
    )
    # OI growth (+2) + long-dated (+1) + not expired (+1) = 4/9 = 0.44 → no fire but score > 0
    assert result.detail["best_score"] >= 2
    assert "activation_probability" in result.detail
