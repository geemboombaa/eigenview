from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eigenview.config import settings
from eigenview.data.storage import Catalyst, NewsItem
from eigenview.factors.base import FactorResult
from eigenview.factors.sentiment_model import classify

log = structlog.get_logger(__name__)

_FACTOR_ID = "sentiment"


def _catalyst_score(catalysts) -> tuple[int, bool]:
    score = 0
    for cat in catalysts:
        dfn = cat.days_from_now or 0
        if 0 < dfn <= 7:
            score += 3
        elif 7 < dfn <= 30:
            score += 1
    return score, score >= 3


def aggregate_sentiment(
    classified: list[tuple[str, float]],
    ages_days: list[float],
    catalyst_score: int,
    news_count: int,
    lookback_days: int,
) -> FactorResult:
    """Pure aggregation of per-article (label, confidence) into a sentiment FactorResult.

    Recency-weighted (halflife from config), confidence-weighted net direction. Catalyst
    proximity is a bonus + an alternate fire path — never the sole signal. Testable with
    real computed inputs, no model/DB needed.
    """
    halflife = max(0.1, settings.sentiment_recency_halflife_days)
    num = 0.0
    den = 0.0
    bull = bear = neut = 0
    for (label, conf), age in zip(classified, ages_days):
        w = 0.5 ** (max(0.0, age) / halflife)
        if label == "positive":
            signed = conf
            bull += 1
        elif label == "negative":
            signed = -conf
            bear += 1
        else:
            signed = 0.0
            neut += 1
        num += signed * w
        den += w

    net = (num / den) if den > 0 else 0.0   # -1..1, recency+confidence weighted
    catalyst_near = catalyst_score >= 3

    if net > 0.05:
        direction = "bullish"
    elif net < -0.05:
        direction = "bearish"
    else:
        direction = "neutral"

    # strength = model conviction (|net|) + small catalyst nudge; honest 0..1
    catalyst_bonus = min(0.2, catalyst_score * 0.05)
    strength = max(0.0, min(1.0, abs(net) + catalyst_bonus))
    fires = abs(net) >= settings.sentiment_fire_strength or catalyst_near

    parts = [f"{news_count} article(s) in {lookback_days}d -> {direction} (net {net:+.2f})."]
    if catalyst_near:
        parts.append(f"catalyst within 7d (+{catalyst_score}).")

    return FactorResult(
        factor_id=_FACTOR_ID,
        firing=fires,
        strength=strength,
        label=direction,
        detail={
            "news_count": news_count,
            "net": round(net, 4),
            "bull": bull, "bear": bear, "neutral": neut,
            "catalyst_score": catalyst_score,
            "catalyst_near": catalyst_near,
        },
        narrative=" ".join(parts),
    )


async def score_sentiment(
    ticker: str,
    session: AsyncSession,
    lookback_days: int = 3,
) -> FactorResult:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    news_rows = await session.execute(
        select(NewsItem).where(NewsItem.ticker == ticker, NewsItem.timestamp >= cutoff)
    )
    news = news_rows.scalars().all()

    catalyst_rows = await session.execute(select(Catalyst).where(Catalyst.ticker == ticker))
    catalysts = catalyst_rows.scalars().all()
    catalyst_score, _ = _catalyst_score(catalysts)

    if len(news) < settings.sentiment_min_articles:
        # No news → catalyst can still fire on its own (real signal), else honest NO DATA.
        if catalyst_score >= 3:
            return aggregate_sentiment([], [], catalyst_score, 0, lookback_days)
        return FactorResult.no_data(_FACTOR_ID, "no recent news")

    texts = [f"{n.headline or ''}. {n.summary or ''}".strip() for n in news]
    ages = [max(0.0, (now - n.timestamp).total_seconds() / 86400.0) for n in news]
    classified = classify(texts)

    return aggregate_sentiment(classified, ages, catalyst_score, len(news), lookback_days)
