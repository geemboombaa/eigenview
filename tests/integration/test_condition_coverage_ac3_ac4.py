"""
Condition coverage tests — AC3, AC4.

AC3: NEVER_FIRED detection exits non-zero when a required pattern is absent
AC4: condition_coverage exits 0 when all required patterns fire at least once

All tests raise NotImplementedError until implementation (green phase).
"""
from __future__ import annotations

import json


def _run_condition_coverage(scan_output: dict) -> tuple[int, dict]:
    """
    Run condition_coverage checker against scan_output JSON.
    Returns (exit_code, report_dict).
    Raises NotImplementedError until checker is implemented.
    """
    raise NotImplementedError(
        "AC3/AC4: tests/integration/condition_coverage.py not yet created. "
        "Implement the NEVER_FIRED checker in green phase."
    )


def _make_scan_output_missing_pattern(missing_pattern: str) -> dict:
    """Build a scan output dict where missing_pattern fired 0 times."""
    raise NotImplementedError(
        "AC3: scan output fixture factory not yet implemented."
    )


def _make_scan_output_all_patterns_fired() -> dict:
    """Build a scan output dict where every required TA pattern fires >= 1 time."""
    raise NotImplementedError(
        "AC4: scan output fixture factory not yet implemented."
    )


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


def test_AC3_required_patterns_include_all_21_setups():
    """
    GIVEN the condition_coverage checker
    THEN it checks all 21 TA setups defined in CLAUDE.md taxonomy
    """
    raise NotImplementedError(
        "AC3: required_patterns list must include all 21 setups. "
        "Verify against CLAUDE.md 21-setup taxonomy in green phase."
    )
