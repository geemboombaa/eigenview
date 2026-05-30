"""Real Anthropic API thesis tests — no mocked client, no fake responses."""
from __future__ import annotations

import pytest

from eigenview.llm.thesis import _contradicts, _fallback, generate_thesis


def _ctx(ticker: str = "NVDA", direction: str = "long", firing: bool = True) -> dict:
    return {
        "ticker": ticker,
        "direction": direction,
        "setup": "breakdown" if direction == "short" else "pullback_in_trend",
        "entry_low": 200.0, "entry_high": 207.0,
        "stop": 195.0 if direction == "long" else 214.0,
        "target": 225.0 if direction == "long" else 185.0,
        "rr": 3.0, "conviction": 4, "price": 207.5,
        "catalyst": "earnings in 22 days", "macro_label": "GREEN",
        "factors": {
            "technical": {"firing": firing,
                          "label": "pullback_in_trend" if direction == "long" else "breakdown",
                          "detail": {"weekly_state": "BULLISH" if direction == "long" else "BEARISH_STRONG",
                                     "rsi": 42.5, "adx": 28.0}},
            "gex": {"firing": firing, "label": "long_gamma" if direction == "long" else "short_gamma",
                    "detail": {"gamma_flip": 205.0, "call_wall": 220.0, "put_wall": 195.0}},
            "flow": {"firing": False, "label": "no_signal", "detail": {}},
            "dormant": {"firing": False, "label": "DORMANT", "detail": {}},
            "sentiment": {"firing": firing, "label": "bullish" if direction == "long" else "bearish",
                          "detail": {"net": 0.4 if direction == "long" else -0.4,
                                     "top_headline": "NVDA data-center demand accelerates"}},
        },
    }


# ── Pure function tests (no I/O — real computed inputs) ────────────────────

def test_fallback_contains_ticker():
    assert "NVDA" in _fallback(_ctx("NVDA"))


def test_fallback_mentions_direction_and_stop():
    fb = _fallback(_ctx("AAPL", direction="short"))
    assert "short" in fb.lower()
    assert "214.00" in fb


def test_fallback_is_nonempty_string():
    fb = _fallback(_ctx("AMD"))
    assert isinstance(fb, str) and len(fb) > 0


# ── Real Anthropic API call ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_thesis_returns_nonempty_string():
    result = await generate_thesis(_ctx("NVDA", direction="long"))
    assert isinstance(result, str)
    assert len(result) > 10, f"thesis too short: '{result}'"


@pytest.mark.asyncio
async def test_generate_thesis_mentions_ticker():
    result = await generate_thesis(_ctx("NVDA", direction="long"))
    assert "nvda" in result.lower()


@pytest.mark.asyncio
async def test_generate_thesis_short_pick_is_not_bullish():
    # The whole point of the grounding fix: a SHORT pick must never come back arguing long.
    result = await generate_thesis(_ctx("CRM", direction="short"))
    assert isinstance(result, str) and len(result) > 10
    assert _contradicts("short", result) is False, f"short thesis argued long: {result}"
