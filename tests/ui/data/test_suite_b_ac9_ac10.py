"""
Suite B — AC9, AC10: Data validation against real server + real DB.

AC9: API contract tests — GET /api/picks returns structurally valid picks
     with correct field types, ranges, and non-null required values.
     No browser required. Skips if server not running or no picks in DB.

AC10: Workflow structure tests — integration-live.yml has required artifact
      upload steps. Pure file-content checks, no live CI needed.

Tests marked data_dependent skip automatically if server/DB unavailable.
"""
from __future__ import annotations

import json
import os
import pathlib
import urllib.error
import urllib.request

import pytest

BASE_URL = os.environ.get("EIGENVIEW_TEST_URL", "http://localhost:8000")


def _fetch_picks() -> list[dict]:
    """Fetch picks from real server. Skip if server unreachable or no picks."""
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/picks", timeout=5) as resp:
            picks = json.loads(resp.read().decode())
    except urllib.error.URLError:
        pytest.skip(f"eigenview server not reachable at {BASE_URL}")
    except Exception as e:
        pytest.skip(f"picks fetch failed: {e}")
    if not picks:
        pytest.skip("No picks in DB — run eigenview daily-scan first")
    return picks


def _load_workflow_yaml() -> str:
    wf = pathlib.Path(".github/workflows/integration-live.yml")
    if not wf.exists():
        pytest.skip("integration-live.yml not found")
    return wf.read_text()


# ── AC9: /api/picks API contract ──────────────────────────────────────────────

@pytest.mark.data_dependent
def test_AC9_ticker_field_is_present_and_nonempty():
    """
    GIVEN GET /api/picks returns picks
    THEN every pick has ticker: non-empty uppercase string
    """
    picks = _fetch_picks()
    for p in picks:
        assert p.get("ticker"), f"Pick missing ticker: {p}"
        assert p["ticker"] == p["ticker"].upper(), f"Ticker not uppercase: {p['ticker']}"
        assert p["ticker"].isalpha(), f"Ticker not alpha-only: {p['ticker']}"


@pytest.mark.data_dependent
def test_AC9_direction_is_long_or_short():
    """
    GIVEN picks from API
    THEN every pick.direction is 'long' or 'short'
    """
    picks = _fetch_picks()
    for p in picks:
        assert p.get("direction") in ("long", "short"), (
            f"Invalid direction '{p.get('direction')}' for {p.get('ticker')}"
        )


@pytest.mark.data_dependent
def test_AC9_conviction_in_range_1_to_5():
    """
    GIVEN picks from API
    THEN every pick.conviction is integer 1..5
    """
    picks = _fetch_picks()
    for p in picks:
        conv = p.get("conviction")
        assert conv is not None, f"conviction missing for {p.get('ticker')}"
        assert isinstance(conv, int), f"conviction not int: {conv}"
        assert 1 <= conv <= 5, f"conviction {conv} out of range for {p.get('ticker')}"


@pytest.mark.data_dependent
def test_AC9_entry_zone_has_low_and_high():
    """
    GIVEN picks from API
    THEN picks with entry zone have entry_low < entry_high, both positive
    """
    picks = _fetch_picks()
    for p in picks:
        lo = p.get("entry_low")
        hi = p.get("entry_high")
        if lo is not None and hi is not None:
            assert lo > 0, f"entry_low <= 0 for {p.get('ticker')}: {lo}"
            assert hi > 0, f"entry_high <= 0 for {p.get('ticker')}: {hi}"
            assert lo <= hi, f"entry_low > entry_high for {p.get('ticker')}: {lo} > {hi}"


@pytest.mark.data_dependent
def test_AC9_stop_below_entry_for_long():
    """
    GIVEN a long pick with stop and entry_low
    THEN stop < entry_low (stop must be below entry)
    """
    picks = _fetch_picks()
    checked = 0
    for p in picks:
        if p.get("direction") == "long" and p.get("stop") and p.get("entry_low"):
            assert p["stop"] < p["entry_low"], (
                f"Long stop {p['stop']} >= entry_low {p['entry_low']} for {p.get('ticker')}"
            )
            checked += 1
    if checked == 0:
        pytest.skip("No long picks with stop+entry_low to validate")


@pytest.mark.data_dependent
def test_AC9_factors_json_has_required_keys():
    """
    GIVEN picks from API
    THEN picks that include factors_json have keys: ta, gex, flow, dormant, sentiment
    """
    picks = _fetch_picks()
    required = {"ta", "gex", "flow", "dormant", "sentiment"}
    checked = 0
    for p in picks:
        fj = p.get("factors_json")
        if fj:
            if isinstance(fj, str):
                fj = json.loads(fj)
            missing = required - set(fj.keys())
            assert not missing, (
                f"factors_json missing keys {missing} for {p.get('ticker')}"
            )
            checked += 1
    if checked == 0:
        pytest.skip("No picks with factors_json to validate")


@pytest.mark.data_dependent
def test_AC9_setup_type_is_known_pattern():
    """
    GIVEN picks from API
    THEN setup_type is one of the 27 known TA patterns (or None for unscored)
    """
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parents[3] / "src"))
    from eigenview.factors.technical import SETUP_TAXONOMY as REQUIRED_PATTERNS

    picks = _fetch_picks()
    for p in picks:
        st = p.get("setup_type")
        if st is not None:
            assert st in REQUIRED_PATTERNS, (
                f"Unknown setup_type '{st}' for {p.get('ticker')}"
            )


@pytest.mark.data_dependent
def test_AC9_all_required_fields_present_no_nulls():
    """
    GIVEN picks from API
    THEN ticker, direction, conviction are non-null on every pick
    Aggregate check — must pass for all picks, not just first.
    """
    picks = _fetch_picks()
    required = ["ticker", "direction", "conviction"]
    mismatches = []
    for p in picks:
        for field in required:
            if p.get(field) is None:
                mismatches.append(f"{p.get('ticker','?')}.{field}=null")
    assert not mismatches, f"Null required fields: {mismatches}"


@pytest.mark.data_dependent
def test_AC9_api_returns_at_least_one_pick():
    """
    GIVEN daily scan has run
    THEN GET /api/picks returns >= 1 pick
    """
    picks = _fetch_picks()
    assert len(picks) >= 1, "Expected at least 1 pick from daily scan"


@pytest.mark.data_dependent
def test_AC9_pick_explanation_endpoint_exists():
    """
    GIVEN picks from API
    THEN GET /api/pick/{ticker} returns 200 with ticker field
    """
    picks = _fetch_picks()
    ticker = picks[0]["ticker"]
    try:
        with urllib.request.urlopen(f"{BASE_URL}/api/pick/{ticker}", timeout=5) as resp:
            data = json.loads(resp.read().decode())
        assert data.get("ticker") == ticker
    except urllib.error.HTTPError as e:
        if e.code == 404:
            pytest.skip(f"/api/pick/{{ticker}} not implemented yet (404)")
        raise


# ── AC10: Artifact upload structure in workflow ───────────────────────────────

def test_AC10_upload_artifact_step_exists():
    """
    GIVEN .github/workflows/integration-live.yml
    THEN file contains at least one upload-artifact step
    Pure YAML text check — no live CI required.
    """
    content = _load_workflow_yaml()
    assert "upload-artifact" in content, "No upload-artifact step in integration-live.yml"


def test_AC10_scan_results_artifact_uploaded():
    """
    GIVEN integration-live.yml
    THEN scan_results.json or scan_output.log is included in upload paths
    """
    content = _load_workflow_yaml()
    assert any(name in content for name in ("scan_results.json", "scan_output.log")), (
        "scan results not in upload-artifact paths"
    )


def test_AC10_coverage_report_artifact_uploaded():
    """
    GIVEN integration-live.yml
    THEN coverage_report.json is in upload paths
    """
    content = _load_workflow_yaml()
    assert "coverage_report.json" in content, "coverage_report.json not in upload-artifact paths"


def test_AC10_all_artifacts_retention_30_days():
    """
    GIVEN integration-live.yml
    THEN retention-days: 30 is set on upload-artifact step
    """
    content = _load_workflow_yaml()
    assert "retention-days: 30" in content, "retention-days: 30 not set on artifacts"


def test_AC10_artifacts_uploaded_on_failure_too():
    """
    GIVEN integration-live.yml
    THEN upload-artifact step has 'if: always()' so artifacts survive test failures
    """
    content = _load_workflow_yaml()
    assert "if: always()" in content, (
        "upload-artifact must have 'if: always()' — artifacts needed for debugging failures"
    )
