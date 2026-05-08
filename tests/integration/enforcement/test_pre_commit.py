"""
Pre-commit hook enforcement tests — AC9, AC10, AC11, AC12, AC13, AC14.

Harness: invoke_pre_commit() not yet implemented.
All tests fail until tests/enforcement/harness.py is written (green phase).

Harness must create a temp git repo with controlled staging state and run
the actual .git/hooks/pre-commit hook via subprocess.
"""


def _invoke_pre_commit(staged_src: bool, staged_new_tests: bool, existing_fail: bool, stubs_pass: bool) -> dict:
    """
    Stub: set up temp git repo, stage specified files, run pre-commit hook.
    Returns dict with keys: exit_code (int), stdout (str).
    Raises NotImplementedError until harness.py is implemented.

    Args:
        staged_src: whether src/ files are staged
        staged_new_tests: whether new test stub files are staged
        existing_fail: whether existing (non-stub) tests fail
        stubs_pass: whether the staged stub tests pass
    """
    raise NotImplementedError(
        "Pre-commit harness not implemented. "
        "Implement tests/enforcement/harness.py with invoke_pre_commit()."
    )


def test_AC9_pre_commit_red_phase_stubs_fail_allows_commit():
    """
    GIVEN tests/ only staged, stubs fail, existing tests pass
    THEN exit_code=0 (commit allowed)
    """
    result = _invoke_pre_commit(
        staged_src=False, staged_new_tests=True, existing_fail=False, stubs_pass=False
    )
    assert result["exit_code"] == 0


def test_AC10_pre_commit_red_phase_existing_regression_blocks():
    """
    GIVEN tests/ only staged, existing test fails
    THEN exit_code=1, output contains "existing tests regressed"
    """
    result = _invoke_pre_commit(
        staged_src=False, staged_new_tests=True, existing_fail=True, stubs_pass=False
    )
    assert result["exit_code"] == 1
    assert "existing tests regressed" in result["stdout"]


def test_AC11_pre_commit_red_phase_stubs_pass_blocks():
    """
    GIVEN tests/ only staged, stubs pass (implementation exists)
    THEN exit_code=1, output contains "stubs PASSED"
    """
    result = _invoke_pre_commit(
        staged_src=False, staged_new_tests=True, existing_fail=False, stubs_pass=True
    )
    assert result["exit_code"] == 1
    assert "stubs PASSED" in result["stdout"]


def test_AC12_pre_commit_green_phase_all_pass_allows():
    """
    GIVEN src/ staged, all tests pass
    THEN exit_code=0
    """
    result = _invoke_pre_commit(
        staged_src=True, staged_new_tests=False, existing_fail=False, stubs_pass=False
    )
    assert result["exit_code"] == 0


def test_AC13_pre_commit_green_phase_test_fails_blocks():
    """
    GIVEN src/ staged, a test fails
    THEN exit_code=1, output contains "tests failed"
    """
    result = _invoke_pre_commit(
        staged_src=True, staged_new_tests=False, existing_fail=True, stubs_pass=False
    )
    assert result["exit_code"] == 1
    assert "tests failed" in result["stdout"].lower()


def test_AC14_pre_commit_docs_phase_no_src_no_tests_allows():
    """
    GIVEN no src/ no tests/ staged, existing tests pass
    THEN exit_code=0, output contains "docs-only commit"
    """
    result = _invoke_pre_commit(
        staged_src=False, staged_new_tests=False, existing_fail=False, stubs_pass=False
    )
    assert result["exit_code"] == 0
    assert "docs-only commit" in result["stdout"]
