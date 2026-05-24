"""Real Anthropic API thesis tests — no mocked client, no fake responses."""
from __future__ import annotations

import pytest

from eigenview.llm.thesis import _factor_summary, _fallback, generate_thesis


# ── Pure function tests (no I/O — real computed inputs) ────────────────────

def _real_factors(firing: bool = True) -> dict:
    return {
        "technical": {"firing": firing, "label": "pullback_in_trend", "detail": {"rsi": 42.5, "adx": 28.0}},
        "gex": {"firing": firing, "label": "long_gamma", "detail": {"net_gex": 1_200_000_000.0}},
        "flow": {"firing": False, "label": "no_signal", "detail": {}},
    }


def test_factor_summary_includes_firing_labels():
    result = _factor_summary(_real_factors(firing=True))
    assert "technical" in result
    assert "gex" in result


def test_factor_summary_excludes_non_firing():
    result = _factor_summary(_real_factors(firing=True))
    assert "flow" not in result


def test_factor_summary_empty_returns_fallback_string():
    result = _factor_summary({})
    assert isinstance(result, str)
    assert len(result) > 0


def test_fallback_contains_ticker():
    result = _fallback("NVDA", _real_factors())
    assert "NVDA" in result


def test_fallback_mentions_ta_and_gex():
    result = _fallback("AAPL", _real_factors())
    assert "TA" in result
    assert "GEX" in result


def test_fallback_is_nonempty_string():
    result = _fallback("AMD", _real_factors())
    assert isinstance(result, str)
    assert len(result) > 0


# ── Real Anthropic API call ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_thesis_returns_nonempty_string():
    factors = _real_factors(firing=True)
    result = await generate_thesis("NVDA", factors, price=207.50, catalyst="earnings in 22 days")
    assert isinstance(result, str)
    assert len(result) > 10, f"thesis too short: '{result}'"


@pytest.mark.asyncio
async def test_generate_thesis_mentions_ticker():
    factors = _real_factors(firing=True)
    result = await generate_thesis("NVDA", factors, price=207.50, catalyst=None)
    assert "NVDA" in result or "nvda" in result.lower()


@pytest.mark.asyncio
async def test_generate_thesis_no_firing_factors_returns_something():
    factors = _real_factors(firing=False)
    result = await generate_thesis("AMD", factors, price=235.0, catalyst=None)
    assert isinstance(result, str)
    assert len(result) > 0
