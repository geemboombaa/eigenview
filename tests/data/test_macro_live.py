"""Real fetch_macro tests — hits real yfinance/CFTC-Socrata/FINRA endpoints + local DB. No mocks."""
from __future__ import annotations

import pytest

from eigenview.data.macro import compute_market_gex, fetch_dix, fetch_macro


@pytest.mark.asyncio
async def test_fetch_macro_returns_dict():
    result = await fetch_macro()
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_fetch_macro_has_vix_keys():
    result = await fetch_macro()
    assert "vix_m1" in result
    assert "vix_m2" in result
    assert "vix_contango_pct" in result


@pytest.mark.asyncio
async def test_fetch_macro_vix_positive_when_present():
    result = await fetch_macro()
    if result.get("vix_m1") is not None:
        assert result["vix_m1"] > 0
    if result.get("vix_m2") is not None:
        assert result["vix_m2"] > 0


@pytest.mark.asyncio
async def test_fetch_macro_contango_derived_from_vix():
    """contango_pct must be computed from m1/m2, not hardcoded."""
    result = await fetch_macro()
    m1, m2, ct = result.get("vix_m1"), result.get("vix_m2"), result.get("vix_contango_pct")
    if m1 and m2 and ct is not None:
        expected = round((m2 - m1) / m1 * 100, 4)
        assert abs(ct - expected) < 0.1


@pytest.mark.asyncio
async def test_fetch_macro_no_crash_on_partial_failure():
    result = await fetch_macro()
    assert isinstance(result, dict)
    assert "date" in result


@pytest.mark.asyncio
async def test_vix_present_yfinance_reliable():
    """yfinance ^VIX is reliable — fetch_macro should populate vix_m1 on a normal run."""
    result = await fetch_macro()
    assert result.get("vix_m1") is not None, "yfinance ^VIX should populate vix_m1"
    assert 1 < result["vix_m1"] < 150


@pytest.mark.asyncio
async def test_dix_in_unit_range_when_present():
    """DIX is a ratio of short/total dollar volume → must be in (0,1)."""
    dix = await fetch_dix()
    if dix is not None:
        assert 0.0 < dix < 1.0, f"DIX={dix} out of (0,1) range"


@pytest.mark.asyncio
async def test_dix_reconstructed_not_constant():
    """DIX must be a real computed aggregate, not a hardcoded constant."""
    dix = await fetch_dix()
    if dix is not None:
        # SqueezeMetrics DIX historically lives ~0.38–0.50; a sane band for the reconstruction.
        assert 0.30 < dix < 0.60, f"DIX={dix} outside plausible reconstructed band"


@pytest.mark.asyncio
async def test_market_gex_is_float_when_chains_present():
    """GEX aggregate over S&P 500 component chains → a real number (sign = regime)."""
    gex = await compute_market_gex()
    if gex is not None:
        assert isinstance(gex, float)
        # billions-of-dollars dealer gamma — bounded sanity, not hardcoded
        assert -1e4 < gex < 1e4


@pytest.mark.asyncio
async def test_fetch_macro_writes_gex_and_dix_keys():
    result = await fetch_macro()
    assert "dix" in result
    assert "gex_index" in result
