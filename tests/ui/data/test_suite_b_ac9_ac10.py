"""
Suite B — AC9, AC10: Data validation against real server + real DB.

Strategy: all tests connect to a real eigenview server backed by a real DB
with real picks written by daily_scan. No synthetic fixtures. No cassette replays.
Server started by conftest.py server fixture (subprocess uvicorn).

AC9: Pick card UI fields match DB values field-by-field.
AC10: Artifacts uploaded after every integration-live.yml run.

All tests raise NotImplementedError until green phase wires the server fixture.
"""
from __future__ import annotations

import os
import json
import pytest

BASE_URL = os.environ.get("EIGENVIEW_TEST_URL", "http://localhost:8000")


def _get_real_server_and_picks():
    """
    Returns (page, db_picks) where:
    - page: Playwright page connected to real server (real DB, real picks)
    - db_picks: list of pick dicts fetched from GET /api/picks

    Server uses the same DB path as daily_scan writes to.
    No pick injection — picks must already exist from a real scan run.
    Raises NotImplementedError until conftest.py server fixture implemented.
    """
    raise NotImplementedError(
        "AC9: Real server fixture not yet implemented. "
        "Implement in tests/ui/conftest.py: "
        "(1) Run daily_scan --universe test5 to populate DB, "
        "(2) Start uvicorn server pointing at that DB, "
        "(3) Return (playwright_page, picks_from_api). "
        "No synthetic data — picks must come from real scan."
    )


# ── AC9: Pick card fields match DB ────────────────────────────────────────────

def test_AC9_ticker_in_card_matches_db():
    """
    GIVEN server running with real picks
    WHEN pick cards rendered
    THEN each card's ticker text == picks[i].ticker from GET /api/picks
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: ticker field DB match not implemented")


def test_AC9_direction_badge_matches_db():
    """
    GIVEN pick cards rendered
    THEN direction badge text ('LONG' or 'SHORT') == db_pick.direction
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: direction badge DB match not implemented")


def test_AC9_conviction_dot_count_matches_db():
    """
    GIVEN pick cards rendered
    THEN number of filled conviction dots == db_pick.conviction (1-5)
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: conviction dot count DB match not implemented")


def test_AC9_entry_zone_matches_db():
    """
    GIVEN pick cards rendered
    THEN entry zone text == formatted(db_pick.entry_low / db_pick.entry_high)
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: entry zone DB match not implemented")


def test_AC9_stop_matches_db():
    """
    GIVEN pick cards rendered
    THEN stop level text == formatted(db_pick.stop)
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: stop level DB match not implemented")


def test_AC9_factor_strip_fired_dots_match_db():
    """
    GIVEN pick cards rendered, factor strip visible
    THEN green dots correspond to factors_json[factor].firing == True in DB
    AND gray dots correspond to factors_json[factor].firing == False
    No field-by-field mismatch tolerance — must be exact.
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: factor strip dot colors vs DB not implemented")


def test_AC9_caution_badge_matches_macro_regime():
    """
    GIVEN MACRO regime is YELLOW
    THEN CAUTION badge visible on pick card
    GIVEN MACRO regime is GREEN
    THEN no CAUTION badge on pick card
    Requires: real macro_daily row in DB with known regime.
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: CAUTION badge vs macro regime DB not implemented")


def test_AC9_thesis_text_matches_db():
    """
    GIVEN pick card rendered
    THEN thesis block first sentence == db_pick.thesis[:N] where N = visible truncation
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: thesis text DB match not implemented")


def test_AC9_setup_type_matches_db():
    """
    GIVEN pick card structure description visible
    THEN structure text contains db_pick.setup_type
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: setup_type DB match not implemented")


def test_AC9_all_pick_fields_zero_mismatches():
    """
    GIVEN all pick cards rendered
    THEN field-by-field comparison across ALL picks returns 0 mismatches
    Aggregate check — must pass if all individual field tests pass.
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: zero-mismatch aggregate check not implemented")


def test_AC9_pick_explanation_api_matches_card():
    """
    GIVEN GET /api/pick/{ticker}/explanation returns PickExplanation JSON
    THEN conviction in JSON == card conviction dots
    AND factor_contributions keys match factor strip dots
    (Requires intelligent layer implemented — AC-EXPLAIN-2)
    """
    page, db_picks = _get_real_server_and_picks()
    raise NotImplementedError("AC9: pick explanation API vs card not implemented")


# ── AC10: Artifact uploads ────────────────────────────────────────────────────

def test_AC10_playwright_report_artifact_in_workflow():
    """
    GIVEN .github/workflows/integration-live.yml
    THEN file contains upload-artifact step with path: playwright-report/
    Pure file-content check — no live CI required.
    """
    raise NotImplementedError(
        "AC10: Check integration-live.yml for playwright-report/ upload-artifact step. "
        "Implement: parse YAML, find upload-artifact actions, assert path present."
    )


def test_AC10_condition_coverage_json_artifact_in_workflow():
    """
    GIVEN integration-live.yml
    THEN upload-artifact step with path: condition-coverage.json exists
    """
    raise NotImplementedError("AC10: condition-coverage.json artifact check not implemented")


def test_AC10_junit_xml_artifact_in_workflow():
    """
    GIVEN integration-live.yml
    THEN upload-artifact step with path: results/junit-integration.xml exists
    """
    raise NotImplementedError("AC10: junit-integration.xml artifact check not implemented")


def test_AC10_all_artifacts_retention_30_days():
    """
    GIVEN integration-live.yml
    THEN all upload-artifact steps set retention-days: 30
    """
    raise NotImplementedError("AC10: 30-day retention check not implemented")


def test_AC10_artifacts_uploaded_on_failure_too():
    """
    GIVEN integration-live.yml
    THEN upload-artifact steps have 'if: always()' condition
    so artifacts are available even when tests fail (needed for debugging)
    """
    raise NotImplementedError(
        "AC10: 'if: always()' on upload steps not checked. "
        "Required: artifacts must upload even on test failure."
    )
