"""tests/synthesis/test_scanner.py — scanner unit tests with all I/O mocked."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import DormantBet
from eigenview.factors.base import FactorResult
from eigenview.synthesis.gate import TickerScorecard
from eigenview.synthesis.scanner import _identify_dormant_bets, _score_ticker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fr(factor_id: str, firing: bool = True, strength: float = 0.75) -> FactorResult:
    return FactorResult(
        factor_id=factor_id,
        firing=firing,
        strength=strength,
        label="TEST",
        detail={},
        narrative="test",
    )


@dataclass
class MockChain:
    ticker: str
    strike: float
    call_put: str
    expiry: date
    bid: float
    ask: float
    oi: int
    snapshot_date: date = date.today()


def _make_macro() -> FactorResult:
    return FactorResult(
        factor_id="macro_regime",
        firing=True,
        strength=0.8,
        label="GREEN",
        detail={"score": 8},
        narrative="GREEN regime.",
    )


# ---------------------------------------------------------------------------
# _identify_dormant_bets
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_identify_dormant_bets_skips_low_premium(db_session: AsyncSession) -> None:
    """Chains below $300K premium threshold must not be upserted."""
    today = date.today()
    chains = [
        MockChain(
            ticker="NVDA", strike=500.0, call_put="C",
            expiry=today + timedelta(days=90),
            bid=0.5, ask=1.0, oi=100,  # premium = 0.75 * 100 * 100 = $7,500
        )
    ]
    await _identify_dormant_bets("NVDA", chains, today, db_session)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(select(DormantBet).where(DormantBet.ticker == "NVDA"))
    rows = result.scalars().all()
    assert len(rows) == 0


@pytest.mark.asyncio
async def test_identify_dormant_bets_inserts_qualifying(db_session: AsyncSession) -> None:
    """Chain with DTE >= 60 and premium >= $300K is upserted as dormant bet."""
    today = date.today()
    chains = [
        MockChain(
            ticker="AAPL",
            strike=200.0,
            call_put="C",
            expiry=today + timedelta(days=90),
            bid=14.0, ask=16.0, oi=300,   # mid=15, premium = 15*300*100 = $450K
        )
    ]
    await _identify_dormant_bets("AAPL", chains, today, db_session)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(select(DormantBet).where(DormantBet.ticker == "AAPL"))
    rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].strike == pytest.approx(200.0)
    assert rows[0].original_oi == 300


@pytest.mark.asyncio
async def test_identify_dormant_bets_skips_low_dte(db_session: AsyncSession) -> None:
    """Chains with DTE < 60 must not be tracked as dormant bets."""
    today = date.today()
    chains = [
        MockChain(
            ticker="TSLA",
            strike=300.0,
            call_put="P",
            expiry=today + timedelta(days=30),  # 30 DTE < 60
            bid=14.0, ask=16.0, oi=300,
        )
    ]
    await _identify_dormant_bets("TSLA", chains, today, db_session)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(select(DormantBet).where(DormantBet.ticker == "TSLA"))
    rows = result.scalars().all()
    assert len(rows) == 0


# ---------------------------------------------------------------------------
# _score_ticker (fully mocked I/O)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_score_ticker_returns_scorecard(db_session: AsyncSession) -> None:
    """_score_ticker with all I/O mocked returns a TickerScorecard."""
    import pandas as pd
    import numpy as np

    today = date.today()
    dates = [today - timedelta(days=i) for i in range(90, 0, -1)]
    fake_df = pd.DataFrame({
        "open": np.full(90, 100.0),
        "high": np.full(90, 105.0),
        "low": np.full(90, 95.0),
        "close": np.full(90, 102.0),
        "volume": np.full(90, 1_000_000),
    }, index=pd.to_datetime(dates))

    macro = _make_macro()

    with (
        patch("eigenview.synthesis.scanner.get_prices", return_value=fake_df),
        patch("eigenview.synthesis.scanner.get_chain", return_value={"calls": MagicMock(), "puts": MagicMock(), "iv_rank": 0.3}),
        patch("eigenview.synthesis.scanner.score_technical", return_value=_fr("technical")),
        patch("eigenview.synthesis.scanner.score_gex",       return_value=_fr("gex")),
        patch("eigenview.synthesis.scanner.score_flow",      return_value=_fr("flow")),
        patch("eigenview.synthesis.scanner.score_dormant",   new_callable=AsyncMock, return_value=_fr("dormant", firing=False)),
        patch("eigenview.synthesis.scanner.score_sentiment", new_callable=AsyncMock, return_value=_fr("sentiment")),
        patch("eigenview.synthesis.scanner.fetch_news",      new_callable=AsyncMock),
        patch("eigenview.synthesis.scanner.get_catalysts",   new_callable=AsyncMock, return_value=[]),
        patch("eigenview.synthesis.scanner._identify_dormant_bets", new_callable=AsyncMock),
        patch("eigenview.data.storage.AsyncSessionLocal") as mock_sl,
    ):
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_sl.return_value = mock_session

        result = await _score_ticker("NVDA", macro, 8, db_session)

    assert result is not None
    assert isinstance(result, TickerScorecard)
    assert result.ticker == "NVDA"
    assert result.technical.firing is True
    assert result.spot_price == pytest.approx(102.0)


@pytest.mark.asyncio
async def test_score_ticker_returns_none_on_empty_prices(db_session: AsyncSession) -> None:
    """_score_ticker returns None when get_prices returns empty DataFrame."""
    import pandas as pd

    macro = _make_macro()

    with patch("eigenview.synthesis.scanner.get_prices", return_value=pd.DataFrame()):
        result = await _score_ticker("BADTICKER", macro, 8, db_session)

    assert result is None


@pytest.mark.asyncio
async def test_score_ticker_returns_none_on_exception(db_session: AsyncSession) -> None:
    """_score_ticker returns None and logs warning when any fetch raises."""
    macro = _make_macro()

    with patch("eigenview.synthesis.scanner.get_prices", side_effect=RuntimeError("network error")):
        result = await _score_ticker("ERRORTICKER", macro, 8, db_session)

    assert result is None
