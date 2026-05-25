"""Real CLI command tests via typer CliRunner — in-process, real DB, no network commands."""
from __future__ import annotations

from typer.testing import CliRunner

from eigenview.cli import app

runner = CliRunner()


def test_help_lists_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.output


def test_init_db_exits_zero():
    result = runner.invoke(app, ["init-db"])
    assert result.exit_code == 0


def test_status_runs_and_lists_tables():
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "prices" in result.output
    assert "chains" in result.output
    assert "picks" in result.output
