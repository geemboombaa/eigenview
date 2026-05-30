"""Rate-limiter timing tests — real asyncio clock, no mocks, no external calls."""
from __future__ import annotations

import asyncio

from eigenview.data.news import AsyncRateLimiter


def test_limiter_spaces_concurrent_acquires():
    """Three concurrent acquires at 0.1s spacing take >= 0.2s wall time.

    First acquire fires immediately; the next two are each gated to >=0.1s
    after the prior, so total elapsed is at least 2 * interval.
    """
    limiter = AsyncRateLimiter(min_interval_secs=0.1)

    async def _run() -> float:
        loop = asyncio.get_event_loop()
        start = loop.time()
        await asyncio.gather(*(limiter.acquire() for _ in range(3)))
        return loop.time() - start

    elapsed = asyncio.run(_run())
    assert elapsed >= 0.2
