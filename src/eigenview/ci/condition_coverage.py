"""
Condition coverage checker — verifies every TA setup pattern fired at least once.

Usage (called by integration-live.yml):
    python src/eigenview/ci/condition_coverage.py scan_results.json

Exits 0 if all required patterns fired; exits 1 if any pattern is NEVER_FIRED.
Writes JSON report to stdout.
"""
from __future__ import annotations

import json
import sys

REQUIRED_PATTERNS: list[str] = [
    # Trend Continuation
    "pullback_in_trend",
    "pullback_deep",
    "pullback_to_structure",
    "flag_continuation",
    "rally_in_downtrend",
    # Breakout
    "breakout",
    "breakdown",
    "compression_break",
    "compression_break_down",
    "base_breakout",
    "base_breakdown",
    "ema_reclaim",
    "ema_rejection",
    "bos_bullish",
    "bos_bearish",
    # Reversal
    "bullish_reversal",
    "bearish_reversal",
    "overbought_reversal",
    "oversold_bounce",
    "failed_breakdown",
    "failed_breakout",
    "choch_bullish",
    "choch_bearish",
    # Mean Reversion
    "bb_mean_reversion_long",
    "bb_mean_reversion_short",
    "ema200_snap_long",
    "ema200_snap_short",
]


def check_coverage(scan_output: dict) -> tuple[int, dict[str, str]]:
    """
    Check which required patterns fired in scan_output.

    scan_output: dict with 'picks' list, each pick has 'setup_type'.
    Returns (exit_code, report) where exit_code=0 means all fired.
    """
    picks = scan_output.get("picks", [])
    fired: set[str] = {p["setup_type"] for p in picks if p.get("setup_type")}

    report: dict[str, str] = {}
    any_missing = False
    for pattern in REQUIRED_PATTERNS:
        if pattern in fired:
            report[pattern] = "FIRED"
        else:
            report[pattern] = "NEVER_FIRED"
            any_missing = True

    return (1 if any_missing else 0, report)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: condition_coverage.py <scan_results.json>"}))
        sys.exit(2)

    with open(sys.argv[1]) as f:
        data = json.load(f)

    exit_code, report = check_coverage(data)
    print(json.dumps(report, indent=2))
    sys.exit(exit_code)
