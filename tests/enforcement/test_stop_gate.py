"""
Stop-gate enforcement tests — AC1, AC2, AC3.

Harness: invoke_stop_gate() not yet implemented.
All tests fail until tests/enforcement/harness.py is written (green phase).
"""
import json


def _invoke_stop_gate(dirty_src: bool, tests_pass: bool) -> dict:
    """
    Stub: invoke stop-gate.ps1 with a mock payload and repo state.
    Returns parsed JSON output from the hook, or {} if no output (allow).
    Raises NotImplementedError until harness.py is implemented.
    """
    raise NotImplementedError(
        "Stop-gate harness not implemented. "
        "Implement tests/enforcement/harness.py with invoke_stop_gate()."
    )


def test_AC1_stop_gate_dirty_src_blocks_instantly():
    """
    GIVEN src/ has uncommitted changes
    THEN decision=block, reason mentions dirty files, fires in <10s (no pytest run)
    """
    result = _invoke_stop_gate(dirty_src=True, tests_pass=True)
    assert result.get("decision") == "block"
    assert "src/" in result.get("reason", "") or "not committed" in result.get("reason", "")


def test_AC2_stop_gate_clean_src_passing_tests_allows():
    """
    GIVEN src/ clean AND all tests pass
    THEN no block decision
    """
    result = _invoke_stop_gate(dirty_src=False, tests_pass=True)
    assert result.get("decision") != "block"


def test_AC3_stop_gate_clean_src_failing_tests_blocks():
    """
    GIVEN src/ clean AND at least one test fails
    THEN decision=block, reason contains test failure output
    """
    result = _invoke_stop_gate(dirty_src=False, tests_pass=False)
    assert result.get("decision") == "block"
    assert "fail" in result.get("reason", "").lower() or "FAILED" in result.get("reason", "")
