"""
Condition coverage tests — AC3, AC4.

AC3: NEVER_FIRED detection exits non-zero when a required pattern is absent
AC4: condition_coverage exits 0 when all required patterns fire at least once

NOTE: Tests AC3/AC4 use constructed scan_output dicts (not real DB data).
This tests the checker LOGIC correctly. A separate @pytest.mark.data_dependent
test (test_AC3_against_real_signal_triggers) tests the full pipeline with
real signal_triggers rows from a completed daily scan.
"""
from __future__ import annotations

import json
import sys
import pathlib

import pytest

# Ensure src/ on path for direct import
sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))
from eigenview.ci.condition_coverage import check_coverage, REQUIRED_PATTERNS


def _run_condition_coverage(scan_output: dict) -> tuple[int, dict]:
    """Run condition_coverage checker against scan_output dict."""
    return check_coverage(scan_output)


def _make_scan_output_missing_pattern(missing_pattern: str) -> dict:
    """Build scan output where missing_pattern fired 0 times."""
    other_patterns = [p for p in REQUIRED_PATTERNS if p != missing_pattern]
    picks = [{"ticker": "NVDA", "setup_type": p, "conviction": 3, "direction": "long"}
             for p in other_patterns]
    return {"picks_count": len(picks), "picks": picks}


def _make_scan_output_all_patterns_fired() -> dict:
    """Build scan output where every required TA pattern fires >= 1 time."""
    picks = [{"ticker": "NVDA", "setup_type": p, "conviction": 3, "direction": "long"}
             for p in REQUIRED_PATTERNS]
    return {"picks_count": len(picks), "picks": picks}


def test_AC3_never_fired_detection_reports_missing_pattern():
    """
    GIVEN a scan output JSON where pullback_in_trend fired 0 times
    WHEN the condition_coverage checker runs
    THEN it reports pullback_in_trend: NEVER_FIRED
    """
    scan_output = _make_scan_output_missing_pattern("pullback_in_trend")
    exit_code, report = _run_condition_coverage(scan_output)
    assert report.get("pullback_in_trend") == "NEVER_FIRED"


def test_AC3_never_fired_exits_nonzero():
    """
    GIVEN a scan output JSON where a required pattern fired 0 times
    WHEN condition_coverage runs
    THEN exits with non-zero code
    """
    scan_output = _make_scan_output_missing_pattern("pullback_in_trend")
    exit_code, report = _run_condition_coverage(scan_output)
    assert exit_code != 0, f"Expected non-zero exit but got {exit_code}"


def test_AC4_all_patterns_fired_shows_fired_status():
    """
    GIVEN a scan output JSON where every required TA pattern fires at least once
    WHEN condition_coverage checker runs
    THEN all rows show FIRED
    """
    scan_output = _make_scan_output_all_patterns_fired()
    exit_code, report = _run_condition_coverage(scan_output)
    for pattern, status in report.items():
        assert status == "FIRED", f"Pattern {pattern} shows {status}, expected FIRED"


def test_AC4_all_patterns_fired_exits_zero():
    """
    GIVEN a scan output where every required pattern fires
    WHEN condition_coverage runs
    THEN exits with code 0
    """
    scan_output = _make_scan_output_all_patterns_fired()
    exit_code, report = _run_condition_coverage(scan_output)
    assert exit_code == 0, f"Expected exit 0 but got {exit_code}"


@pytest.mark.data_dependent
def test_AC3_against_real_signal_triggers():
    """
    GIVEN a completed daily_scan has run (signal_triggers table has rows)
    WHEN condition_coverage runs against real signal_triggers data
    THEN report contains only FIRED or NEVER_FIRED statuses
    Skips if no scan data available.
    """
    import asyncio
    try:
        from eigenview.data.storage import AsyncSessionLocal, SignalTrigger
        from sqlalchemy import select

        async def _get_real_scan_output() -> dict:
            async with AsyncSessionLocal() as session:
                rows = (await session.execute(select(SignalTrigger))).scalars().all()
                if not rows:
                    return {}
                picks = [{"ticker": r.ticker, "setup_type": r.setup_type,
                          "conviction": 3, "direction": r.direction}
                         for r in rows]
                return {"picks_count": len(picks), "picks": picks}

        scan_output = asyncio.run(_get_real_scan_output())
        if not scan_output:
            pytest.skip("signal_triggers table empty — run eigenview daily-scan first")
        _, report = check_coverage(scan_output)
        for pattern, status in report.items():
            assert status in ("FIRED", "NEVER_FIRED"), f"Unknown status {status} for {pattern}"
    except ImportError:
        pytest.skip("eigenview not importable")


def test_AC3_required_patterns_include_all_21_setups():
    """
    GIVEN the condition_coverage checker
    THEN it checks at least the 21 TA setups defined in CLAUDE.md taxonomy
    """
    # The 21 setup names from CLAUDE.md
    required_21 = {
        "pullback_in_trend", "pullback_deep", "pullback_to_structure",
        "flag_continuation", "rally_in_downtrend",
        "breakout", "breakdown", "compression_break", "compression_break_down",
        "base_breakout", "base_breakdown", "ema_reclaim", "ema_rejection",
        "bos_bullish", "bos_bearish",
        "bullish_reversal", "bearish_reversal", "overbought_reversal",
        "oversold_bounce", "failed_breakdown", "failed_breakout",
    }
    checked = set(REQUIRED_PATTERNS)
    missing = required_21 - checked
    assert not missing, f"condition_coverage missing these setups: {missing}"
