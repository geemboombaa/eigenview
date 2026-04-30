from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Catalyst, NewsItem
from eigenview.factors.base import FactorResult

log = structlog.get_logger(__name__)

_FACTOR_ID = "sentiment"

_BULLISH = {"beat", "record", "surge", "upgrade", "raised", "outperform", "strong", "rally", "bullish", "growth"}
_BEARISH = {"miss", "cut", "downgrade", "decline", "weak", "selloff", "loss", "warning", "risk", "concern"}


def _keyword_hits(text: str) -> tuple[int, int]:
    words = set(text.lower().split())
    return len(words & _BULLISH), len(words & _BEARISH)


async def score_sentiment(
    ticker: str,
    session: AsyncSession,
    lookback_days: int = 3,
) -> FactorResult:
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    news_rows = await session.execute(
        select(NewsItem).where(
            NewsItem.ticker == ticker,
            NewsItem.timestamp >= cutoff,
        )
    )
    news = news_rows.scalars().all()

    catalyst_rows = await session.execute(select(Catalyst).where(Catalyst.ticker == ticker))
    catalysts = catalyst_rows.scalars().all()

    if not news:
        return FactorResult.no_data(_FACTOR_ID, "no recent news")

    # Catalyst proximity
    catalyst_score = 0
    for cat in catalysts:
        dfn = cat.days_from_now or 0
        if 0 < dfn <= 7:
            catalyst_score += 3
        elif 7 < dfn <= 30:
            catalyst_score += 1
    catalyst_near = catalyst_score >= 3

    # Keyword scoring across all articles
    total_bull = 0
    total_bear = 0
    for item in news:
        text = f"{item.headline or ''} {item.summary or ''}"
        b, br = _keyword_hits(text)
        total_bull += b
        total_bear += br

    if total_bull > total_bear:
        sentiment_direction = "bullish"
    elif total_bear > total_bull:
        sentiment_direction = "bearish"
    else:
        sentiment_direction = "neutral"

    novelty_proxy = len(news) / max(1, lookback_days)
    novelty_z = novelty_proxy - 1.0

    fires = catalyst_near or (len(news) >= 3 and total_bull > total_bear)

    raw_strength = (catalyst_score / 3 + max(0.0, novelty_z)) / 2
    strength = max(0.0, min(1.0, raw_strength))

    # Build narrative
    parts: list[str] = []
    if news:
        parts.append(f"{len(news)} {sentiment_direction} article(s) in {lookback_days} days.")
    if catalyst_near:
        near_cats = [c for c in catalysts if 0 < (c.days_from_now or 0) <= 7]
        if near_cats:
            parts.append(f"{near_cats[0].event_type} in {near_cats[0].days_from_now} days.")

    return FactorResult(
        factor_id=_FACTOR_ID,
        firing=fires,
        strength=strength,
        label=sentiment_direction,
        detail={
            "news_count": len(news),
            "catalyst_near": catalyst_near,
            "catalyst_score": catalyst_score,
            "novelty_z": round(novelty_z, 3),
            "bull_hits": total_bull,
            "bear_hits": total_bear,
        },
        narrative=" ".join(parts) if parts else f"{len(news)} articles found.",
    )
