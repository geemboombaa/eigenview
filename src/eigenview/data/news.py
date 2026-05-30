from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timedelta, timezone

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as upsert
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from eigenview.config import settings
from eigenview.data.storage import AsyncSessionLocal, NewsItem

log = structlog.get_logger(__name__)

class AsyncRateLimiter:
    """Serialize awaiters to >= min_interval_secs apart (process-wide gate).

    First acquire fires immediately; each subsequent acquire waits until the
    interval has elapsed since the prior one. Shared across all coroutines so
    bounded concurrency cannot exceed the provider's per-minute ceiling.
    """

    def __init__(self, min_interval_secs: float):
        self._min_interval = min_interval_secs
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            loop = asyncio.get_event_loop()
            wait = self._min_interval - (loop.time() - self._last)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = loop.time()


# Alpha Vantage free tier: 25 calls/day → 1 call per 12 s to stay safe.
_AV_LIMITER = AsyncRateLimiter(min_interval_secs=12.0)
# Finnhub free tier: 60 req/min → 1 call per ~1.1 s leaves margin, no 429 storm.
_FINNHUB_LIMITER = AsyncRateLimiter(min_interval_secs=1.1)


def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:64]


def _parse_av_timestamp(ts: str) -> datetime | None:
    """AV format: '20240101T120000'"""
    try:
        return datetime.strptime(ts, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def _fetch_av(client: httpx.AsyncClient, ticker: str) -> list[dict]:
    await _AV_LIMITER.acquire()

    url = (
        "https://www.alphavantage.co/query"
        f"?function=NEWS_SENTIMENT&tickers={ticker}&limit=10"
        f"&apikey={settings.alpha_vantage_key}"
    )
    resp = await client.get(url, timeout=20.0)
    resp.raise_for_status()
    data = resp.json()

    articles = []
    for item in data.get("feed", []):
        raw_url = item.get("url", "")
        if not raw_url:
            continue
        articles.append(
            {
                "headline": item.get("title", ""),
                "summary": item.get("summary", ""),
                "url": raw_url,
                "url_hash": _url_hash(raw_url),
                "source": item.get("source", "alphavantage"),
                "timestamp": _parse_av_timestamp(item.get("time_published", "")),
                "ticker": ticker.upper(),
            }
        )
    log.info("fetch_news.av_done", ticker=ticker, count=len(articles))
    return articles


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
)
async def _fetch_finnhub(
    client: httpx.AsyncClient, ticker: str, lookback_days: int
) -> list[dict]:
    await _FINNHUB_LIMITER.acquire()

    today = datetime.now(tz=timezone.utc).date()
    from_date = today - timedelta(days=lookback_days)

    url = (
        "https://finnhub.io/api/v1/company-news"
        f"?symbol={ticker}&from={from_date}&to={today}"
        f"&token={settings.finnhub_key}"
    )
    resp = await client.get(url, timeout=20.0)
    resp.raise_for_status()
    data = resp.json()

    articles = []
    for item in data:
        raw_url = item.get("url", "")
        if not raw_url:
            continue
        ts_unix = item.get("datetime")
        timestamp = (
            datetime.fromtimestamp(ts_unix, tz=timezone.utc) if ts_unix else None
        )
        articles.append(
            {
                "headline": item.get("headline", ""),
                "summary": item.get("summary", ""),
                "url": raw_url,
                "url_hash": _url_hash(raw_url),
                "source": item.get("source", "finnhub"),
                "timestamp": timestamp,
                "ticker": ticker.upper(),
            }
        )
    log.info("fetch_news.finnhub_done", ticker=ticker, count=len(articles))
    return articles


async def fetch_news(
    ticker: str,
    lookback_days: int = 3,
    sources: tuple[str, ...] = ("av", "finnhub"),
) -> list[dict]:
    """Fetch news, deduplicate, upsert, return list.

    `sources` selects which providers run. Default uses both (Alpha Vantage +
    Finnhub). Pass ("finnhub",) for bulk runs so AV's 25/day budget is not
    burned — the news-refresh job uses this to keep AV for a small subset only.
    """
    ticker = ticker.upper()

    av_results: list[dict] | Exception = []
    fh_results: list[dict] | Exception = []
    async with httpx.AsyncClient() as client:
        tasks = []
        if "av" in sources:
            tasks.append(("av", asyncio.create_task(_fetch_av(client, ticker))))
        if "finnhub" in sources:
            tasks.append(
                ("finnhub", asyncio.create_task(_fetch_finnhub(client, ticker, lookback_days)))
            )
        gathered = await asyncio.gather(
            *(t for _, t in tasks), return_exceptions=True
        )
        for (name, _), result in zip(tasks, gathered, strict=True):
            if name == "av":
                av_results = result
            else:
                fh_results = result

    av_articles: list[dict] = av_results if isinstance(av_results, list) else []
    fh_articles: list[dict] = fh_results if isinstance(fh_results, list) else []

    if isinstance(av_results, Exception):
        log.warning("fetch_news.av_failed", ticker=ticker, error=str(av_results))
    if isinstance(fh_results, Exception):
        log.warning(
            "fetch_news.finnhub_failed", ticker=ticker, error=str(fh_results)
        )

    # Deduplicate by url_hash — AV wins on collision (already filtered by ticker)
    seen: dict[str, dict] = {}
    for article in av_articles + fh_articles:
        h = article["url_hash"]
        if h not in seen:
            seen[h] = article

    deduped = list(seen.values())
    log.info(
        "fetch_news.deduped",
        ticker=ticker,
        av=len(av_articles),
        finnhub=len(fh_articles),
        deduped=len(deduped),
    )

    if deduped:
        rows = [
            {
                "ticker": a["ticker"],
                "headline": a["headline"],
                "summary": a["summary"] or None,
                "url_hash": a["url_hash"],
                "source": a["source"],
                "timestamp": a["timestamp"].replace(tzinfo=None) if a["timestamp"] else None,
            }
            for a in deduped
        ]
        async with AsyncSessionLocal() as session:
            stmt = (
                upsert(NewsItem)
                .values(rows)
                .on_conflict_do_nothing()
            )
            await session.execute(stmt)
            await session.commit()

    return [
        {
            "headline": a["headline"],
            "summary": a["summary"],
            "url_hash": a["url_hash"],
            "source": a["source"],
            "timestamp": a["timestamp"],
            "ticker": a["ticker"],
        }
        for a in deduped
    ]


async def get_news(ticker: str, lookback_days: int = 3) -> list[dict]:
    """Read news from DB for ticker within lookback window."""
    ticker = ticker.upper()
    cutoff = datetime.utcnow() - timedelta(days=lookback_days)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(NewsItem)
            .where(
                NewsItem.ticker == ticker,
                NewsItem.timestamp >= cutoff,
            )
            .order_by(NewsItem.timestamp.desc())
        )
        rows = result.scalars().all()

    return [
        {
            "headline": r.headline,
            "summary": r.summary,
            "url_hash": r.url_hash,
            "source": r.source,
            "timestamp": r.timestamp,
            "ticker": r.ticker,
        }
        for r in rows
    ]
