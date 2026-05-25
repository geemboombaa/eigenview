"""tests/llm/test_thesis.py — thesis generation unit tests (Anthropic client mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _factors(firing: bool = True) -> dict:
    return {
        "technical": {"firing": firing, "label": "pullback_in_trend", "detail": {"rsi": 42.5, "adx": 28.0}},
        "gex": {"firing": firing, "label": "long_gamma", "detail": {"net_gex": 1.2e9}},
        "flow": {"firing": False, "label": "no_signal", "detail": {}},
    }


# ---------------------------------------------------------------------------
# _factor_summary
# ---------------------------------------------------------------------------

def test_factor_summary_includes_firing_factors():
    from eigenview.llm.thesis import _factor_summary
    result = _factor_summary(_factors(firing=True))
    assert "technical" in result
    assert "gex" in result


def test_factor_summary_excludes_non_firing():
    from eigenview.llm.thesis import _factor_summary
    result = _factor_summary(_factors(firing=True))
    assert "flow" not in result


def test_factor_summary_empty_factors():
    from eigenview.llm.thesis import _factor_summary
    result = _factor_summary({})
    assert result == "multiple factors firing"


# ---------------------------------------------------------------------------
# _fallback
# ---------------------------------------------------------------------------

def test_fallback_contains_ticker():
    from eigenview.llm.thesis import _fallback
    result = _fallback("NVDA", _factors())
    assert "NVDA" in result


def test_fallback_mentions_ta_and_gex():
    from eigenview.llm.thesis import _fallback
    result = _fallback("AAPL", _factors())
    assert "TA" in result
    assert "GEX" in result


# ---------------------------------------------------------------------------
# generate_thesis — success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_thesis_returns_string():
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="NVDA is set up for a pullback continuation.")]
    mock_msg.usage.input_tokens = 100
    mock_msg.usage.output_tokens = 20

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("eigenview.llm.thesis._get_client", return_value=mock_client),
        patch("eigenview.llm.thesis.AsyncSessionLocal", return_value=mock_session),
    ):
        from eigenview.llm.thesis import generate_thesis
        result = await generate_thesis("NVDA", _factors(), 132.50, "Earnings in 14 days")

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# generate_thesis — API failure falls back to template
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_thesis_falls_back_on_error():
    from eigenview.llm.thesis import generate_thesis

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        side_effect=RuntimeError("rate limit exceeded")
    )

    with patch("eigenview.llm.thesis._get_client", return_value=mock_client):
        result = await generate_thesis("TSLA", _factors(), 250.0, None)

    assert "TSLA" in result


@pytest.mark.asyncio
async def test_generate_thesis_falls_back_on_generic_exception():
    from eigenview.llm.thesis import generate_thesis

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=RuntimeError("network timeout"))

    with patch("eigenview.llm.thesis._get_client", return_value=mock_client):
        result = await generate_thesis("META", _factors(), 500.0, None)

    assert "META" in result
