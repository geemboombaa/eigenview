"""
Pre-commit check logic — extracted as pure functions for testability.

Used by:
  - .git/hooks/pre-commit GREEN phase (via subprocess or direct call)
  - tests/integration/test_precommit_enforcement_ac11.py
"""
from __future__ import annotations


def check_integration_test_required(staged_files: list[str]) -> tuple[int, str]:
    """
    AC11: If src/ files are staged, at least one tests/integration/ or tests/ui/ file
    must also be staged. Enforces the rule that every src change ships with a test.

    Returns (exit_code, message).
    exit_code=0: OK. exit_code=1: BLOCKED.
    """
    src_staged = [f for f in staged_files if f.startswith("src/")]
    integration_staged = [
        f for f in staged_files
        if f.startswith("tests/integration/") or f.startswith("tests/ui/")
    ]

    if src_staged and not integration_staged:
        missing = ", ".join(src_staged[:3])
        if len(src_staged) > 3:
            missing += f" (+{len(src_staged) - 3} more)"
        return (
            1,
            f"COMMIT BLOCKED: src/ change requires integration test in "
            f"tests/integration/ or tests/ui/\n"
            f"  src/ staged: {missing}\n"
            f"  Add a test file to tests/integration/ or tests/ui/ and stage it."
        )
    return 0, "OK"
