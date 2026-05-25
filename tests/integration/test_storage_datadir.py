"""
Integration test for storage.py SQLite data-dir creation.

Covers src/eigenview/data/storage.py: importing the module must ensure the
SQLite file's parent directory exists, so a fresh checkout (data/ is
gitignored, absent on CI runners) doesn't raise "unable to open database file".

Real filesystem + real config. No mocks.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from eigenview.config import settings


@pytest.mark.skipif(
    not (settings.database_url.startswith("sqlite") and "///" in settings.database_url),
    reason="only meaningful for a file-backed SQLite DSN",
)
def test_sqlite_parent_dir_created_on_import():
    import eigenview.data.storage  # noqa: F401  — import runs the dir-creation guard

    db_file = settings.database_url.split("///", 1)[1]
    assert db_file and db_file != ":memory:"
    parent = Path(db_file).expanduser().resolve().parent
    assert parent.is_dir(), f"SQLite parent dir not created: {parent}"


def test_create_tables_against_real_engine():
    import asyncio

    from sqlalchemy import inspect

    import eigenview.data.storage as storage

    async def _run() -> list[str]:
        await storage.create_tables()
        async with storage.engine.connect() as conn:
            return await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )

    tables = asyncio.run(_run())
    for expected in ("prices", "chains", "picks"):
        assert expected in tables, f"table '{expected}' missing after create_tables()"
