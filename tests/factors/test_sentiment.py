from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.data.storage import Catalyst, NewsItem
from eigenview.factors.sentiment import score_sentiment

_id_counter = 0


def _next_id() -> int:
    global _id_counter
    _id_counter += 1
    return _id_counter


def _make_news(
    ticker: str = "NVDA",
    headline: str = "NVDA beats earnings, record revenue",
    summary: str = "",
    age_days: float = 1.0,
) -> NewsItem:
    ts = datetime.now(timezone.utc) - timedelta(days=age_days)
    url = f"http://example.com/{ticker}/{headline[:20]}/{age_days}/{_next_id()}"
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:64]
    return NewsItem(
        id=_next_id(),
        ticker=ticker,
        headline=headline,
        summary=summary,
        url_hash=url_hash,
        source="test",
        timestamp=ts,
    )


@pytest.mark.asyncio
async def test_bullish_news_fires(db_session: AsyncSession) -> None:
    for i in range(3):
        db_session.add(_make_news(headline=f"NVDA beats earnings record revenue growth {i}"))
    db_session.add(Catalyst(
        id=_next_id(),
        ticker="NVDA",
        event_type="Earnings",
        event_date=date.today() + timedelta(days=5),
        days_from_now=5,
    ))
    await db_session.flush()

    result = await score_sentiment("NVDA", db_session, lookback_days=3)
    assert result.firing is True
    assert result.label == "bullish"
    assert result.detail["news_count"] == 3


@pytest.mark.asyncio
async def test_no_news_no_fire(db_session: AsyncSession) -> None:
    result = await score_sentiment("NVDA", db_session, lookback_days=3)
    assert result.firing is False
    assert result.label == "NO DATA"


@pytest.mark.asyncio
async def test_catalyst_near_fires(db_session: AsyncSession) -> None:
    """Only 1 news article but catalyst in 3 days → fires due to catalyst."""
    db_session.add(_make_news(headline="NVDA update"))
    db_session.add(Catalyst(
        id=_next_id(),
        ticker="NVDA",
        event_type="Earnings",
        event_date=date.today() + timedelta(days=3),
        days_from_now=3,
    ))
    await db_session.flush()

    result = await score_sentiment("NVDA", db_session, lookback_days=3)
    assert result.firing is True
    assert result.detail["catalyst_near"] is True


@pytest.mark.asyncio
async def test_bearish_sentiment(db_session: AsyncSession) -> None:
    for i in range(3):
        db_session.add(_make_news(headline=f"NVDA downgrade miss warning concern {i}"))
    await db_session.flush()

    result = await score_sentiment("NVDA", db_session, lookback_days=3)
    assert result.label == "bearish"
    assert result.detail["bear_score"] > result.detail["bull_score"]


@pytest.mark.asyncio
async def test_old_news_ignored(db_session: AsyncSession) -> None:
    """News older than lookback_days should not be counted."""
    for i in range(3):
        db_session.add(_make_news(
            headline=f"NVDA beats earnings record {i}",
            age_days=5.0,  # older than lookback_days=3
        ))
    await db_session.flush()

    result = await score_sentiment("NVDA", db_session, lookback_days=3)
    assert result.firing is False
    assert result.label == "NO DATA"
