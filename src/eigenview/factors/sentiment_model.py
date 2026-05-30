"""Financial-news sentiment classifier — FinBERT-tone primary, VADER fallback.

FinBERT-tone (yiyanghkust) won the 2026-05-29 benchmark on real EigenView headlines.
Its config.json predates `model_type`, so it is loaded via the explicit BERT classes
(AutoConfig fails on transformers 5.x). The pipeline is a lazy module-level singleton —
loaded once (~14s), reused for every ticker in a scan. VADER is the graceful fallback
if transformers/torch are unavailable, so sentiment never hard-fails the scan.
"""
from __future__ import annotations

import structlog

from eigenview.config import settings

log = structlog.get_logger(__name__)

_pipeline = None
_load_failed = False


def _get_pipeline():
    global _pipeline, _load_failed
    if _pipeline is not None or _load_failed:
        return _pipeline
    try:
        from transformers import (
            BertForSequenceClassification,
            BertTokenizer,
            pipeline,
        )
        tok = BertTokenizer.from_pretrained(settings.sentiment_model_id)
        mdl = BertForSequenceClassification.from_pretrained(settings.sentiment_model_id)
        _pipeline = pipeline("text-classification", model=mdl, tokenizer=tok)
        log.info("sentiment_model.loaded", model=settings.sentiment_model_id)
    except Exception as exc:
        log.warning("sentiment_model.load_failed", error=str(exc))
        _load_failed = True
    return _pipeline


def warm_up() -> None:
    """Load the FinBERT pipeline up front (~14s cold).

    Called once before a scan's per-ticker loop so the model load never counts
    against any single ticker's timeout budget (the cause of heavy-news names
    like AAPL/NVDA timing out and being dropped).
    """
    _get_pipeline()


def _vader(texts: list[str]) -> list[tuple[str, float]]:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        out: list[tuple[str, float]] = []
        for t in texts:
            c = analyzer.polarity_scores(t)["compound"]
            label = "positive" if c > 0.05 else "negative" if c < -0.05 else "neutral"
            out.append((label, abs(c)))
        return out
    except Exception as exc:
        log.warning("sentiment_model.vader_failed", error=str(exc))
        return [("neutral", 0.0) for _ in texts]


def classify(texts: list[str]) -> list[tuple[str, float]]:
    """Return [(label, confidence)] aligned to `texts`. label ∈ {positive, negative, neutral}.

    FinBERT-tone if available, else VADER. Never raises.
    """
    if not texts:
        return []
    clf = _get_pipeline()
    if clf is not None:
        try:
            out = clf(texts, truncation=True, max_length=128, batch_size=settings.sentiment_batch_size)
            return [(o["label"].lower(), float(o["score"])) for o in out]
        except Exception as exc:
            log.warning("sentiment_model.infer_failed", error=str(exc))
    return _vader(texts)
