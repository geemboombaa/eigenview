"""Real tests for universe loader — unknown-name path needs no network."""
from __future__ import annotations

import pytest

from eigenview.data import universe


@pytest.mark.asyncio
async def test_unknown_universe_returns_empty():
    assert await universe.get_universe("not-a-real-universe") == []


@pytest.mark.asyncio
async def test_cached_value_returned_without_refetch(monkeypatch):
    from datetime import date

    # Seed the in-process cache directly (real data structure, no network).
    universe._cache["test-cache"] = (date.today(), ["AAA", "BBB"])
    result = await universe.get_universe("test-cache")
    assert result == ["AAA", "BBB"]
