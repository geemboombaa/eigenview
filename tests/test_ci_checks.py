"""Pure-function unit tests for CI check helpers — real computed inputs, no mocks."""
from __future__ import annotations

from eigenview.ci.condition_coverage import REQUIRED_PATTERNS, check_coverage
from eigenview.ci.precommit_checks import check_integration_test_required


class TestConditionCoverage:

    def test_all_patterns_fired_exit_zero(self):
        scan = {"picks": [{"setup_type": p} for p in REQUIRED_PATTERNS]}
        code, report = check_coverage(scan)
        assert code == 0
        assert all(v == "FIRED" for v in report.values())

    def test_missing_pattern_exit_one(self):
        code, report = check_coverage({"picks": [{"setup_type": "breakout"}]})
        assert code == 1
        assert report["breakout"] == "FIRED"
        assert report["pullback_in_trend"] == "NEVER_FIRED"

    def test_empty_picks_all_never_fired(self):
        code, report = check_coverage({"picks": []})
        assert code == 1
        assert set(report.values()) == {"NEVER_FIRED"}

    def test_pick_without_setup_type_ignored(self):
        code, report = check_coverage({"picks": [{"ticker": "NVDA"}]})
        assert code == 1
        assert report["breakout"] == "NEVER_FIRED"


class TestPrecommitChecks:

    def test_src_without_integration_blocks(self):
        code, msg = check_integration_test_required(["src/eigenview/foo.py"])
        assert code == 1
        assert "BLOCKED" in msg

    def test_src_with_integration_ok(self):
        code, msg = check_integration_test_required(
            ["src/eigenview/foo.py", "tests/integration/test_x.py"]
        )
        assert code == 0
        assert msg == "OK"

    def test_src_with_ui_ok(self):
        code, _ = check_integration_test_required(
            ["src/eigenview/foo.py", "tests/ui/test_x.py"]
        )
        assert code == 0

    def test_no_src_ok(self):
        code, _ = check_integration_test_required(["docs/readme.md"])
        assert code == 0

    def test_many_src_files_message_truncated(self):
        files = [f"src/eigenview/m{i}.py" for i in range(5)]
        code, msg = check_integration_test_required(files)
        assert code == 1
        assert "more" in msg
