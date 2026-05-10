"""
Suite A — AC8: All UI functional paths covered by Playwright specs running against real server.

Strategy: each test invokes the existing JS spec file via pytest subprocess.
No mocked API, no synthetic data. Server must be running at BASE_URL.
Real picks injected via EV.Store.set() (Playwright-native store injection —
tests UI rendering behavior, not the data pipeline).

All tests raise NotImplementedError until green phase wires the subprocess runner.
"""
from __future__ import annotations

import os
import subprocess
import pytest

BASE_URL = os.environ.get("EIGENVIEW_TEST_URL", "http://localhost:8000")
SPECS_DIR = "tests/ui"


def _run_spec(spec_file: str, grep: str | None = None) -> subprocess.CompletedProcess:
    """
    Run a Playwright JS spec against the real server at BASE_URL.
    Server must be running (started by eigenview_server fixture or externally).
    Skips if npx/playwright not available.
    """
    cmd = ["npx", "playwright", "test", f"{SPECS_DIR}/{spec_file}",
           "--reporter=line", f"--base-url={BASE_URL}"]
    if grep:
        cmd += ["--grep", grep]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        pytest.skip("npx not available — install Node.js + playwright to run UI specs")
    if result.returncode != 0:
        pytest.fail(f"Playwright spec failed:\n{result.stdout[-2000:]}\n{result.stderr[-500:]}")
    return result


# ── Themes ────────────────────────────────────────────────────────────────────

def test_AC8_all_4_themes_css_vars():
    """
    GIVEN server running
    WHEN each of dark/light/glass/bento selected
    THEN CSS vars (--bg-primary, --panel, --radius-card) match design tokens
    Covered by: comprehensive.spec.js groups 2, 27, 28
    """
    _run_spec("comprehensive.spec.js", grep="theme")


def test_AC8_theme_persists_across_template_switch():
    """
    GIVEN theme=glass active
    WHEN template switched to MINIMAL
    THEN data-theme=glass still set on document
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="theme x template")


# ── Templates ─────────────────────────────────────────────────────────────────

def test_AC8_all_5_templates_keyboard_bindings():
    """
    GIVEN server running
    WHEN keys 1-5 pressed
    THEN STANDARD/MINIMAL/PRO/RESEARCH/FOCUS templates applied
    Covered by: comprehensive.spec.js group 3, full-ui.spec.js
    """
    _run_spec("comprehensive.spec.js", grep="template")


def test_AC8_template_layout_slots_visible_correct():
    """
    GIVEN each template active
    THEN correct slots visible/hidden per template definition
    Covered by: comprehensive.spec.js group 3
    """
    _run_spec("comprehensive.spec.js", grep="slot")


# ── Keyboard shortcuts ─────────────────────────────────────────────────────────

def test_AC8_ctrl_k_opens_search():
    _run_spec("comprehensive.spec.js", grep="Ctrl\\+K")


def test_AC8_slash_focuses_chat():
    _run_spec("comprehensive.spec.js", grep="/ key")


def test_AC8_e_toggles_edit_mode():
    _run_spec("comprehensive.spec.js", grep="E toggles")


def test_AC8_question_mark_opens_shortcuts():
    _run_spec("comprehensive.spec.js", grep="\\? opens")


def test_AC8_h_opens_help():
    _run_spec("comprehensive.spec.js", grep="H opens")


def test_AC8_arrow_navigation():
    _run_spec("comprehensive.spec.js", grep="ArrowDown")


def test_AC8_shortcuts_blocked_in_input():
    """Keys must not fire when focus is in search or chat input."""
    _run_spec("comprehensive.spec.js", grep="input-focus guard")


# ── Favorites / Mine tab ───────────────────────────────────────────────────────

def test_AC8_pin_card_appears_in_mine_tab():
    """
    GIVEN a pick card visible
    WHEN user clicks pin (★)
    THEN card appears in Mine tab (category nav filter)
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="mine tab: pin card")


def test_AC8_favorites_persist_localstorage():
    """
    GIVEN card pinned
    WHEN page.reload()
    THEN card still in localStorage after reload
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="favorites: persist")


# ── Edit mode ─────────────────────────────────────────────────────────────────

def test_AC8_edit_mode_drag_changes_position():
    """
    GIVEN edit mode active, module present
    WHEN drag handle used to drag module
    THEN module reordered in DOM or drag completes without error
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="edit mode: drag handle")


def test_AC8_edit_mode_resize_changes_height():
    """
    GIVEN edit mode active
    WHEN resize handle dragged downward
    THEN module height increases
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="edit mode: resize handle")


def test_AC8_edit_mode_close_removes_module():
    _run_spec("comprehensive.spec.js", grep="close button removes module")


def test_AC8_edit_mode_add_panel_palette():
    _run_spec("comprehensive.spec.js", grep="Add Panel")


# ── Factor strip ──────────────────────────────────────────────────────────────

def test_AC8_factor_strip_dots_fired_unfired():
    _run_spec("comprehensive.spec.js", grep="fired class")


def test_AC8_factor_strip_dot_click_opens_detail():
    _run_spec("comprehensive.spec.js", grep="expands detail panel")


def test_AC8_factor_strip_chat_prefill():
    _run_spec("comprehensive.spec.js", grep="populates chat textarea")


# ── Chart ─────────────────────────────────────────────────────────────────────

def test_AC8_gex_overlay_lines_on_chart():
    """
    GIVEN pick selected with GEX data (gamma_flip, call_wall, put_wall)
    WHEN price chart loads
    THEN data-gex-lines attribute set on chart container
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="chart: GEX overlay")


def test_AC8_chart_ema_toggle():
    """
    GIVEN chart loaded
    WHEN EMA21 toggle clicked OFF
    THEN button loses active class and localStorage reflects off state
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="chart: EMA21 toggle")


def test_AC8_chart_maximize_restore():
    _run_spec("comprehensive.spec.js", grep="maximize")


# ── Signal freshness ──────────────────────────────────────────────────────────

def test_AC8_signal_freshness_badge_fresh():
    """
    GIVEN pick with freshness='fresh'
    THEN pick card shows badge with data-freshness=fresh in green
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="pick card: fresh badge")


def test_AC8_signal_freshness_badge_stale():
    """
    GIVEN pick with freshness='stale'
    THEN pick card shows badge with data-freshness=stale in amber
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="pick card: stale badge")


# ── Help page ─────────────────────────────────────────────────────────────────

def test_AC8_help_page_all_tabs_render():
    _run_spec("comprehensive.spec.js", grep="help overlay has tabs")


def test_AC8_help_page_chip_links_navigate_to_correct_tab():
    _run_spec("comprehensive.spec.js", grep="chip links")


# ── Signal matrix ─────────────────────────────────────────────────────────────

def test_AC8_signal_matrix_star_column():
    """
    GIVEN SIGNAL MATRIX nav pill clicked
    THEN matrix view shows with star column indicating conviction
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="signal matrix: star column")


def test_AC8_signal_matrix_row_click_selects_pick():
    """
    GIVEN signal matrix visible
    WHEN row clicked
    THEN selectedTicker store updated to that ticker
    Covered by: functional/functional_gaps.spec.js
    """
    _run_spec("functional/functional_gaps.spec.js", grep="signal matrix: row click")


# ── Auto-refresh ──────────────────────────────────────────────────────────────

def test_AC8_auto_refresh_polls_api():
    _run_spec("comprehensive.spec.js", grep="setInterval.*picks")


def test_AC8_scan_badge_updates_after_refresh():
    _run_spec("comprehensive.spec.js", grep="scan badge updates")
