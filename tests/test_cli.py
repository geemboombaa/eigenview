"""tests/test_cli.py — CLI command tests (all I/O mocked)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from eigenview.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# fetch
# ---------------------------------------------------------------------------

def test_fetch_runs_without_error():
    with (
        patch("eigenview.data.prices.fetch_prices", new_callable=AsyncMock, return_value=MagicMock(__len__=lambda s: 90)),
        patch("eigenview.data.chains.fetch_chain", new_callable=AsyncMock, return_value=MagicMock(__len__=lambda s: 200)),
        patch("eigenview.data.news.fetch_news", new_callable=AsyncMock, return_value=[]),
    ):
        result = runner.invoke(app, ["fetch", "NVDA"])
    assert result.exit_code == 0


def test_fetch_prints_summary():
    with (
        patch("eigenview.data.prices.fetch_prices", new_callable=AsyncMock, return_value=MagicMock(__len__=lambda s: 90)),
        patch("eigenview.data.chains.fetch_chain", new_callable=AsyncMock, return_value=MagicMock(__len__=lambda s: 200)),
        patch("eigenview.data.news.fetch_news", new_callable=AsyncMock, return_value=[]),
    ):
        result = runner.invoke(app, ["fetch", "NVDA"])
    assert "Fetch summary" in result.output


def test_fetch_handles_partial_failure():
    """fetch should still complete if one data source errors."""
    with (
        patch("eigenview.data.prices.fetch_prices", new_callable=AsyncMock, side_effect=RuntimeError("timeout")),
        patch("eigenview.data.chains.fetch_chain", new_callable=AsyncMock, return_value=MagicMock(__len__=lambda s: 200)),
        patch("eigenview.data.news.fetch_news", new_callable=AsyncMock, return_value=[]),
    ):
        result = runner.invoke(app, ["fetch", "NVDA"])
    assert result.exit_code == 0
    assert "ERROR" in result.output


# ---------------------------------------------------------------------------
# fetch-macro
# ---------------------------------------------------------------------------

def test_fetch_macro_runs():
    fake_data = {
        "date": "2026-05-06",
        "dix": 0.44, "gex_index": 1.2e9,
        "vix_m1": 14.5, "vix_m2": 16.0, "vix_m3": 17.2,
        "vix_contango_pct": 0.03,
        "cot_es_net_long_pct": 0.62,
    }
    with patch("eigenview.data.macro.fetch_macro", new_callable=AsyncMock, return_value=fake_data):
        result = runner.invoke(app, ["fetch-macro"])
    assert result.exit_code == 0
    assert "dix" in result.output


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_runs():
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_scalar = MagicMock()
    mock_scalar.scalar_one.return_value = 42
    mock_session.execute = AsyncMock(return_value=mock_scalar)

    with patch("eigenview.cli.AsyncSessionLocal", return_value=mock_session):
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "prices" in result.output


# ---------------------------------------------------------------------------
# init-db
# ---------------------------------------------------------------------------

def test_init_db_runs():
    with patch("eigenview.data.storage.create_tables", new_callable=AsyncMock):
        result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0
