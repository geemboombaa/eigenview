"""
Pre-build-gate enforcement tests — AC4, AC5, AC6, AC7, AC8.

Harness: invoke_pre_build_gate() not yet implemented.
All tests fail until tests/enforcement/harness.py is written (green phase).
"""


def _invoke_pre_build_gate(
    branch: str,
    has_open_pr: bool,
    pr_labels: list,
    file_path: str,
    tool_name: str = "Write",
) -> dict:
    """
    Stub: invoke pre-build-gate.ps1 with mock payload.
    Returns parsed JSON output, or {} if no output (allow).
    Raises NotImplementedError until harness.py is implemented.
    """
    raise NotImplementedError(
        "Pre-build-gate harness not implemented. "
        "Implement tests/enforcement/harness.py with invoke_pre_build_gate()."
    )


def test_AC4_pre_build_gate_master_branch_blocks():
    """
    GIVEN branch = master, tool = Write
    THEN decision=block, reason mentions branch name
    """
    result = _invoke_pre_build_gate(
        branch="master", has_open_pr=False, pr_labels=[], file_path="/repo/src/foo.py"
    )
    assert result.get("decision") == "block"
    assert "master" in result.get("reason", "")


def test_AC5_pre_build_gate_no_pr_blocks():
    """
    GIVEN branch != master, no open PR
    THEN decision=block, reason mentions no open PR
    """
    result = _invoke_pre_build_gate(
        branch="feature/test-branch", has_open_pr=False, pr_labels=[], file_path="/repo/src/foo.py"
    )
    assert result.get("decision") == "block"
    assert "PR" in result.get("reason", "") or "pr" in result.get("reason", "").lower()


def test_AC6_pre_build_gate_awaiting_step21_label_blocks_feature():
    """
    GIVEN feature/ branch, open PR, label gate:awaiting-step21
    THEN decision=block, reason mentions gate:awaiting-step21
    """
    result = _invoke_pre_build_gate(
        branch="feature/my-thing",
        has_open_pr=True,
        pr_labels=["gate:awaiting-step21"],
        file_path="/repo/src/foo.py",
    )
    assert result.get("decision") == "block"
    assert "gate:awaiting-step21" in result.get("reason", "")


def test_AC7_pre_build_gate_fix_branch_bypasses_gate_label():
    """
    GIVEN fix/ branch, open PR, label gate:awaiting-step21
    THEN NOT blocked (fix/ is lightweight path)
    """
    result = _invoke_pre_build_gate(
        branch="fix/some-bug",
        has_open_pr=True,
        pr_labels=["gate:awaiting-step21"],
        file_path="/repo/src/foo.py",
    )
    assert result.get("decision") != "block"


def test_AC8_pre_build_gate_boss_dir_always_allowed():
    """
    GIVEN file_path inside .boss/, branch = master
    THEN NOT blocked
    """
    result = _invoke_pre_build_gate(
        branch="master",
        has_open_pr=False,
        pr_labels=[],
        file_path="/repo/.boss/spec.md",
    )
    assert result.get("decision") != "block"
