from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_AV_FEED = [
    {
        "title": "Apple beats earnings",
        "summary": "AAPL reported strong Q4 results.",
        "url": "https://example.com/apple-earnings",
        "time_published": "20240101T120000",
        "source": "MarketWatch",
    }
]

_FH_FEED = [
    {
        "headline": "Apple supply chain news",
        "summary": "Supply chain update.",
        "url": "https://finnhub.io/apple-supply",
        "datetime": 1704067200,  # 2024-01-01 00:00:00 UTC
        "source": "Reuters",
    }
]

# Same URL as AV article — used for dedup test
_FH_FEED_DUPE = [
    {
        "headline": "Apple beats earnings (FH copy)",
        "summary": "Duplicate.",
        "url": "https://example.com/apple-earnings",
        "datetime": 1704067200,
        "source": "Finnhub",
    }
]


def _make_httpx_response(json_data, status_code: int = 200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        from httpx import HTTPStatusError, Request, Response  # noqa: PLC0415

        resp.raise_for_status.side_effect = HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    return resp


# ---------------------------------------------------------------------------
# Test 1: fetch_news returns list with expected keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_news_returns_expected_keys():
    av_resp = _make_httpx_response({"feed": _AV_FEED})
    fh_resp = _make_httpx_response(_FH_FEED)

    async def _get(url: str, **kwargs):
        if "alphavantage" in url:
            return av_resp
        return fh_resp

    mock_client = AsyncMock()
    mock_client.get = _get

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.news.httpx.AsyncClient") as mock_client_cls,
        patch("eigenview.data.news.AsyncSessionLocal") as mock_session_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from eigenview.data.news import fetch_news

        results = await fetch_news("AAPL", lookback_days=3)

    assert isinstance(results, list)
    assert len(results) > 0
    required_keys = {"headline", "url_hash", "source", "timestamp", "ticker", "summary"}
    for item in results:
        assert required_keys.issubset(item.keys()), f"Missing keys in {item.keys()}"


# ---------------------------------------------------------------------------
# Test 2: dedup — same URL from AV + Finnhub = 1 item
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_news_deduplicates_same_url():
    av_resp = _make_httpx_response({"feed": _AV_FEED})
    fh_resp = _make_httpx_response(_FH_FEED_DUPE)

    # Route by URL so concurrent tasks get the right response regardless of order
    async def _get(url: str, **kwargs):
        if "alphavantage" in url:
            return av_resp
        return fh_resp

    mock_client = AsyncMock()
    mock_client.get = _get

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.news.httpx.AsyncClient") as mock_client_cls,
        patch("eigenview.data.news.AsyncSessionLocal") as mock_session_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from eigenview.data.news import fetch_news

        results = await fetch_news("AAPL", lookback_days=3)

    # Both sources had the same URL — should be deduplicated to 1
    url_hashes = [r["url_hash"] for r in results]
    target_hash = hashlib.sha256(
        "https://example.com/apple-earnings".encode()
    ).hexdigest()[:64]
    assert url_hashes.count(target_hash) == 1


# ---------------------------------------------------------------------------
# Test 3: AV returns empty feed → returns empty list, no crash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_news_av_empty_feed():
    av_resp = _make_httpx_response({"feed": []})
    fh_resp = _make_httpx_response([])

    async def _get(url: str, **kwargs):
        if "alphavantage" in url:
            return av_resp
        return fh_resp

    mock_client = AsyncMock()
    mock_client.get = _get

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    with (
        patch("eigenview.data.news.httpx.AsyncClient") as mock_client_cls,
        patch("eigenview.data.news.AsyncSessionLocal") as mock_session_cls,
    ):
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        from eigenview.data.news import fetch_news

        results = await fetch_news("AAPL", lookback_days=3)

    assert results == []


# ---------------------------------------------------------------------------
# Test 4: url_hash is a 64-char hex string
# ---------------------------------------------------------------------------


def test_url_hash_is_64_char_hex():
    from eigenview.data.news import _url_hash

    url = "https://example.com/some-article"
    h = _url_hash(url)

    assert isinstance(h, str)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)

    # Verify it matches the expected hash
    expected = hashlib.sha256(url.encode()).hexdigest()[:64]
    assert h == expected
