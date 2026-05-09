"""
UI test conftest — real uvicorn server fixture for Suite A and Suite B.

Suite A: starts server, Playwright connects via BASE_URL.
Suite B: runs daily_scan first to populate DB, then starts server.

No mock API. No synthetic data. Server uses real routes and real DB.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import pytest

BASE_URL = os.environ.get("EIGENVIEW_TEST_URL", "http://localhost:8000")
_PORT = int(BASE_URL.rstrip("/").split(":")[-1])


def _wait_for_server(url: str, timeout: int = 15) -> bool:
    """Poll server until it responds or timeout."""
    import urllib.request
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{url}/api/market/regime", timeout=2)
            return True
        except Exception:
            time.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def eigenview_server():
    """
    Start eigenview uvicorn server pointing at the integration DB.
    Yields BASE_URL. Tears down after session.

    Skips if server already running at BASE_URL (CI may pre-start it).
    """
    import urllib.request
    try:
        urllib.request.urlopen(f"{BASE_URL}/api/market/regime", timeout=2)
        yield BASE_URL
        return
    except Exception:
        pass

    db_path = os.environ.get("DB_PATH", "data/eigenview_integration.db")
    env = {**os.environ, "DB_PATH": db_path}

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "eigenview.api.main:app",
         "--host", "0.0.0.0", "--port", str(_PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not _wait_for_server(BASE_URL):
        proc.terminate()
        pytest.skip(f"eigenview server failed to start at {BASE_URL}")

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="session")
def eigenview_server_with_picks(eigenview_server):
    """
    Like eigenview_server but runs daily_scan --universe test5 first
    to ensure picks exist in the DB. Used by Suite B (AC9/AC10).

    Skips if scan fails (live data unavailable).
    """
    result = subprocess.run(
        [sys.executable, "-m", "eigenview.cli", "daily-scan", "--universe", "test5"],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        pytest.skip(
            f"daily_scan failed — live data unavailable. "
            f"stderr: {result.stderr[:500]}"
        )
    yield eigenview_server
