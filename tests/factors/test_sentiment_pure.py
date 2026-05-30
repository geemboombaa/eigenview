"""Sentiment aggregation — pure logic with real computed inputs. Plus one real-model
inference test (FinBERT-tone) proving the classifier is wired, not faked. No mocks."""
from __future__ import annotations

import pytest

from eigenview.config import settings
from eigenview.factors.sentiment import aggregate_sentiment
from eigenview.factors.sentiment_model import classify


def test_bullish_news_fires_bullish():
    r = aggregate_sentiment([("positive", 0.9), ("positive", 0.8)], [0.0, 0.0], 0, 2, 3)
    assert r.label == "bullish"
    assert r.firing is True
    assert r.strength > settings.sentiment_fire_strength


def test_bearish_news_fires_bearish():
    r = aggregate_sentiment([("negative", 0.9), ("negative", 0.85)], [0.0, 1.0], 0, 2, 3)
    assert r.label == "bearish"
    assert r.firing is True


def test_recent_outweighs_stale():
    # stale bearish (10d) vs fresh bullish (0d) → recency weighting flips net positive
    r = aggregate_sentiment([("negative", 0.9), ("positive", 0.9)], [10.0, 0.0], 0, 2, 3)
    assert r.label == "bullish", f"recent should dominate, net={r.detail['net']}"


def test_neutral_does_not_fire():
    r = aggregate_sentiment([("neutral", 0.9)], [0.0], 0, 1, 3)
    assert r.label == "neutral"
    assert r.firing is False


def test_catalyst_alone_can_fire_without_news():
    r = aggregate_sentiment([], [], catalyst_score=3, news_count=0, lookback_days=3)
    assert r.firing is True
    assert r.detail["catalyst_near"] is True


def test_strength_is_bounded_and_derived():
    r = aggregate_sentiment([("positive", 1.0)], [0.0], 5, 1, 3)
    assert 0.0 <= r.strength <= 1.0
    # |net|=1.0 capped at 1.0 even with catalyst bonus
    assert r.strength == 1.0


@pytest.mark.slow
def test_real_model_classifies_direction():
    """Real FinBERT-tone inference — earnings beat = positive, plunge = negative."""
    out = classify([
        "Company beats earnings and raises full-year guidance",
        "Company misses badly, cuts outlook, shares plunge",
    ])
    assert len(out) == 2
    labels = [o[0] for o in out]
    assert labels[0] == "positive", f"beat should be positive, got {out[0]}"
    assert labels[1] == "negative", f"plunge should be negative, got {out[1]}"
