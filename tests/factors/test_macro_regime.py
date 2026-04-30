from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import MacroDaily
from eigenview.factors.macro_regime import score_macro_regime


@pytest.mark.asyncio
async def test_green_regime(db_session: AsyncSession) -> None:
    row = MacroDaily(
        id=1,
        date=date.today(),
        dix=0.50,
        gex_index=1.5,
        vix_contango_pct=0.05,
        vix_m1=15,
    )
    db_session.add(row)
    await db_session.commit()

    result = await score_macro_regime(db_session)
    assert result.firing is True
    assert result.label == "GREEN"
    assert result.detail["score"] == 10
    assert result.strength == 1.0


@pytest.mark.asyncio
async def test_yellow_regime(db_session: AsyncSession) -> None:
    row = MacroDaily(
        id=1,
        date=date.today(),
        dix=0.40,
        gex_index=1.0,
        vix_contango_pct=-0.02,
        vix_m1=22,
    )
    db_session.add(row)
    await db_session.commit()

    result = await score_macro_regime(db_session)
    assert result.firing is True
    assert result.label == "YELLOW"
    assert result.detail["score"] == 3
    assert result.strength == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_red_regime(db_session: AsyncSession) -> None:
    row = MacroDaily(
        id=1,
        date=date.today(),
        dix=0.38,
        gex_index=-0.5,
        vix_contango_pct=-0.05,
        vix_m1=28,
    )
    db_session.add(row)
    await db_session.commit()

    result = await score_macro_regime(db_session)
    assert result.firing is False
    assert result.label == "RED"
    assert result.detail["score"] == 0
    assert result.strength == 0.0


@pytest.mark.asyncio
async def test_no_data(db_session: AsyncSession) -> None:
    result = await score_macro_regime(db_session)
    assert result.firing is False
    assert result.label == "NO DATA"
    assert result.factor_id == "macro_regime"


@pytest.mark.asyncio
async def test_partial_data(db_session: AsyncSession) -> None:
    row = MacroDaily(
        id=1,
        date=date.today(),
        dix=None,
        gex_index=2.0,
        vix_m1=18,
        vix_contango_pct=0.03,
    )
    db_session.add(row)
    await db_session.commit()

    result = await score_macro_regime(db_session)
    assert result.factor_id == "macro_regime"
    assert result.detail["score"] == 7
    assert result.label == "GREEN"
    assert result.firing is True
