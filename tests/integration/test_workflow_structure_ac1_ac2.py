"""
Integration workflow structure tests — AC1, AC2.

AC1: integration-live.yml has nightly cron + workflow_dispatch triggers
AC2: workflow uses real API secrets, no placeholders, fails fast if absent

All tests raise NotImplementedError until implementation (green phase).
"""
from __future__ import annotations

import pathlib


def _load_workflow_yaml() -> str:
    """Read .github/workflows/integration-live.yml."""
    wf = pathlib.Path(".github/workflows/integration-live.yml")
    if not wf.exists():
        raise FileNotFoundError(f"{wf} not found — create workflow in green phase")
    return wf.read_text()


def test_AC1_workflow_has_schedule_trigger():
    """
    GIVEN .github/workflows/integration-live.yml exists
    THEN it has a schedule: trigger with a cron expression
    """
    content = _load_workflow_yaml()
    assert "schedule:" in content
    assert "cron:" in content


def test_AC1_workflow_has_workflow_dispatch_trigger():
    """
    GIVEN .github/workflows/integration-live.yml exists
    THEN it has a workflow_dispatch: trigger
    """
    content = _load_workflow_yaml()
    assert "workflow_dispatch:" in content


def test_AC1_schedule_fires_post_market():
    """
    GIVEN .github/workflows/integration-live.yml exists
    THEN the cron expression fires after 20:00 UTC (post-market US close)
    """
    content = _load_workflow_yaml()
    # cron: '0 21 * * 1-5' or similar — hour must be >= 20
    import re
    match = re.search(r"cron:\s*['\"](\S+)\s+(\d+)", content)
    assert match is not None, "No cron expression found"
    hour = int(match.group(2))
    assert hour >= 20, f"Cron fires at hour {hour} UTC — must be >= 20 (post-market)"


def test_AC2_workflow_reads_alpha_vantage_key_from_secrets():
    """
    GIVEN the integration-live.yml workflow runs
    THEN it reads ALPHA_VANTAGE_KEY from secrets.*
    """
    content = _load_workflow_yaml()
    assert "secrets.ALPHA_VANTAGE_KEY" in content


def test_AC2_workflow_reads_finnhub_key_from_secrets():
    """
    GIVEN the integration-live.yml workflow runs
    THEN it reads FINNHUB_KEY from secrets.*
    """
    content = _load_workflow_yaml()
    assert "secrets.FINNHUB_KEY" in content


def test_AC2_workflow_contains_no_placeholder_values():
    """
    GIVEN the integration-live.yml workflow
    THEN it does NOT contain the string "placeholder" in any env var value
    """
    content = _load_workflow_yaml()
    assert "placeholder" not in content.lower()


def test_AC2_workflow_fails_fast_if_secrets_absent():
    """
    GIVEN the integration-live.yml workflow
    THEN it has a step that checks secrets are non-empty and exits with clear message if absent
    """
    content = _load_workflow_yaml()
    assert "ALPHA_VANTAGE_KEY" in content
    # Must have a validation step or conditional that handles empty secrets
    assert any(kw in content for kw in ["if: env.", "exit 1", "fail-fast", "required:"]), \
        "Workflow must fail fast with clear message when secrets absent"
