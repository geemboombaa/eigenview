import asyncio
import sys
import os

sys.path.insert(0, "src")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:Baba08baba^^@db.vjmsugzvfhgfakvzznxa.supabase.co:5432/postgres")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    async with engine.connect() as conn:
        r = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' ORDER BY table_name"
        ))
        tables = [row[0] for row in r.fetchall()]
        print("TABLES:", tables)
        for t in tables:
            r2 = await conn.execute(text(f'SELECT COUNT(*) FROM "{t}"'))
            count = r2.scalar()
            # get latest row timestamp if possible
            try:
                r3 = await conn.execute(text(f'SELECT * FROM "{t}" LIMIT 1'))
                cols = list(r3.keys())
                sample = r3.fetchone()
            except Exception:
                cols = []
                sample = None
            print(f"  {t}: {count} rows | cols: {cols}")
            if sample:
                print(f"    sample: {dict(zip(cols, sample))}")
    await engine.dispose()

asyncio.run(main())
