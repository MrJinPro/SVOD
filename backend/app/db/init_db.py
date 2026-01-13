from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.base import Base


async def _ensure_schema(engine: AsyncEngine) -> None:
    # Для прототипа у нас нет миграций. Этот хелпер аккуратно добавляет
    # новые колонки в уже существующие таблицы (SQLite/Postgres).
    from sqlalchemy import text

    async with engine.begin() as conn:
        dialect = getattr(conn, "dialect", None)
        dialect_name = getattr(dialect, "name", "") if dialect is not None else ""

        if dialect_name == "sqlite":
            cols = (await conn.execute(text("PRAGMA table_info(events)"))).all()
            col_names = {c[1] for c in cols}
            if "object_id" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN object_id VARCHAR(64)"))
        elif dialect_name == "postgresql":
            exists = (
                await conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name='events' AND column_name='object_id'
                        """
                    )
                )
            ).first()
            if not exists:
                await conn.execute(text("ALTER TABLE events ADD COLUMN object_id VARCHAR(64)"))


async def init_db(engine: AsyncEngine) -> None:
    # Ensure models are imported so SQLAlchemy registers tables
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_schema(engine)

    # Seed minimal users for prototype if DB is empty
    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.user import User

    async with SessionLocal() as session:
        existing = (await session.execute(select(User).limit(1))).scalars().first()
        if existing is None:
            session.add_all(
                [
                    User(
                        id="1",
                        username="ivanov_a",
                        email="ivanov@svod.ru",
                        role="admin",
                        is_active=True,
                        last_login=None,
                    ),
                    User(
                        id="2",
                        username="petrov_s",
                        email="petrov@svod.ru",
                        role="operator",
                        is_active=True,
                        last_login=None,
                    ),
                    User(
                        id="3",
                        username="sidorova_m",
                        email="sidorova@svod.ru",
                        role="analyst",
                        is_active=True,
                        last_login=None,
                    ),
                    User(
                        id="4",
                        username="kozlov_d",
                        email="kozlov@svod.ru",
                        role="operator",
                        is_active=False,
                        last_login=None,
                    ),
                ]
            )
            await session.commit()
