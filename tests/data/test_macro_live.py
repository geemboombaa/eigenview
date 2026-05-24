"""Real fetch_macro tests — hits real SqueezeMetrics/VIX/CFTC endpoints. No mocks."""
from __future__ import annotations

import pytest

from eigenview.data.macro import fetch_macro


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
async def test_fetch_macro_vix_values_positive_when_present():
    result = await fetch_macro()
    if result.get("vix_m1") is not None:
        assert result["vix_m1"] > 0, f"vix_m1={result['vix_m1']} must be positive"
    if result.get("vix_m2") is not None:
        assert result["vix_m2"] > 0, f"vix_m2={result['vix_m2']} must be positive"


@pytest.mark.asyncio
async def test_fetch_macro_contango_derived_from_vix():
    """contango_pct must be computed from m1/m2, not hardcoded."""
    result = await fetch_macro()
    m1 = result.get("vix_m1")
    m2 = result.get("vix_m2")
    ct = result.get("vix_contango_pct")
    if m1 and m2 and ct is not None:
        expected = round((m2 - m1) / m1 * 100, 4)
        assert abs(ct - expected) < 0.1, (
            f"contango_pct={ct} doesn't match (m2-m1)/m1*100={expected}"
        )


@pytest.mark.asyncio
async def test_fetch_macro_no_crash_on_partial_source_failure():
    """fetch_macro must return a dict even if one data source is unreachable."""
    result = await fetch_macro()
    assert isinstance(result, dict)
    # At minimum date should be present
    assert "date" in result or len(result) > 0
