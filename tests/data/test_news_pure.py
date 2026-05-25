"""Pure-function + real-DB tests for news helpers (no network)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from eigenview.data.news import _parse_av_timestamp, _url_hash, get_news


class TestUrlHash:

    def test_deterministic(self):
        assert _url_hash("https://example.com/a") == _url_hash("https://example.com/a")

    def test_distinct_urls_distinct_hashes(self):
        assert _url_hash("https://example.com/a") != _url_hash("https://example.com/b")

    def test_length_capped_at_64(self):
        assert len(_url_hash("https://example.com/very/long/path")) == 64


class TestParseAvTimestamp:

    def test_valid_av_format(self):
        ts = _parse_av_timestamp("20240101T120000")
        assert ts is not None
        assert ts.year == 2024 and ts.month == 1 and ts.day == 1
        assert ts.tzinfo == timezone.utc

    def test_invalid_returns_none(self):
        assert _parse_av_timestamp("not-a-timestamp") is None

    def test_empty_returns_none(self):
        assert _parse_av_timestamp("") is None


@pytest.mark.asyncio
async def test_get_news_unknown_ticker_empty_list():
    rows = await get_news("ZZZZNOPE", lookback_days=3)
    assert rows == []
