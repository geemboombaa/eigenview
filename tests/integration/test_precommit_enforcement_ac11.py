"""
Pre-commit enforcement tests — AC11.

AC11: pre-commit GREEN phase blocks commit if src/ changed but no integration
      or playwright tests are staged.

Tests call check_integration_test_required() directly (pure function from
src/eigenview/ci/precommit_checks.py) so no subprocess/git-staging simulation needed.
The same function is called by .git/hooks/pre-commit GREEN phase.
"""
from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parents[2] / "src"))
from eigenview.ci.precommit_checks import check_integration_test_required


def _invoke_precommit_green(staged_files: list[str]) -> dict:
    """
    Simulate the pre-commit GREEN phase check for given staged file list.
    Returns dict with keys: exit_code, output.
    """
    exit_code, output = check_integration_test_required(staged_files)
    return {"exit_code": exit_code, "output": output}


def test_AC11_blocks_when_src_staged_but_no_integration_test():
    """
    GIVEN files under src/ are staged
    AND no new file is staged under tests/integration/
    AND no new file is staged under tests/ui/
    WHEN the pre-commit GREEN phase runs
    THEN exit code is 1
    """
    staged = ["src/eigenview/factors/technical.py"]
    result = _invoke_precommit_green(staged)
    assert result["exit_code"] == 1


def test_AC11_output_contains_commit_blocked_message():
    """
    GIVEN src/ staged without integration tests
    THEN output contains 'COMMIT BLOCKED: src/ change requires integration test'
    """
    staged = ["src/eigenview/factors/technical.py"]
    result = _invoke_precommit_green(staged)
    assert "COMMIT BLOCKED: src/ change requires integration test" in result["output"]


def test_AC11_allows_when_src_staged_with_integration_test():
    """
    GIVEN src/ file staged AND a new tests/integration/*.py is also staged
    THEN exit code is 0 (not blocked)
    """
    staged = [
        "src/eigenview/factors/technical.py",
        "tests/integration/test_technical_integration.py",
    ]
    result = _invoke_precommit_green(staged)
    assert result["exit_code"] == 0


def test_AC11_allows_when_src_staged_with_playwright_test():
    """
    GIVEN src/ file staged AND a new tests/ui/**/*.spec.js is also staged
    THEN exit code is 0
    """
    staged = [
        "src/eigenview/api/routes/chart.py",
        "tests/ui/functional/test_chart.spec.js",
    ]
    result = _invoke_precommit_green(staged)
    assert result["exit_code"] == 0


def test_AC11_allows_when_only_tests_staged():
    """
    GIVEN no src/ files staged (only tests/ staged)
    THEN exit code is 0 — not blocked
    """
    staged = ["tests/integration/test_new_coverage.py"]
    result = _invoke_precommit_green(staged)
    assert result["exit_code"] == 0


def test_AC11_allows_when_only_docs_staged():
    """
    GIVEN only docs/ or non-src files staged
    THEN exit code is 0
    """
    staged = ["docs/07-decisions.md", ".boss/spec.md"]
    result = _invoke_precommit_green(staged)
    assert result["exit_code"] == 0
