from __future__ import annotations

import asyncio
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL не задан. Скопируй .env.example в .env и заполни.")

    engine = create_async_engine(database_url, pool_pre_ping=True)
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text(
                    """
                    SELECT table_schema, table_name
                    FROM information_schema.tables
                    WHERE table_type='BASE TABLE'
                      AND table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name
                    """
                )
            )
        ).mappings().all()

    await engine.dispose()

    print(f"Tables: {len(rows)}")
    for r in rows:
        print(f"{r['table_schema']}.{r['table_name']}")


if __name__ == "__main__":
    asyncio.run(main())
