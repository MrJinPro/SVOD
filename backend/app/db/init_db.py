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
            # Improve SQLite concurrency: allow reads during writes and wait for locks.
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.execute(text("PRAGMA busy_timeout=180000"))

            cols = (await conn.execute(text("PRAGMA table_info(events)"))).all()
            col_names = {c[1] for c in cols}
            if "object_id" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN object_id VARCHAR(64)"))

            user_cols = (await conn.execute(text("PRAGMA table_info(users)"))).all()
            user_col_names = {c[1] for c in user_cols}
            if "password_hash" not in user_col_names:
                await conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
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

            user_hash_exists = (
                await conn.execute(
                    text(
                        """
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name='users' AND column_name='password_hash'
                        """
                    )
                )
            ).first()
            if not user_hash_exists:
                await conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))


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
    from app.core.config import settings
    from app.core.security import hash_password

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
                        password_hash=hash_password("password"),
                        last_login=None,
                    ),
                    User(
                        id="2",
                        username="petrov_s",
                        email="petrov@svod.ru",
                        role="operator",
                        is_active=True,
                        password_hash=hash_password("password"),
                        last_login=None,
                    ),
                    User(
                        id="3",
                        username="sidorova_m",
                        email="sidorova@svod.ru",
                        role="analyst",
                        is_active=True,
                        password_hash=hash_password("password"),
                        last_login=None,
                    ),
                    User(
                        id="4",
                        username="kozlov_d",
                        email="kozlov@svod.ru",
                        role="operator",
                        is_active=False,
                        password_hash=hash_password("password"),
                        last_login=None,
                    ),
                ]
            )
            await session.commit()

        # Optional bootstrap superadmin
        if settings.superadmin_username.strip() and settings.superadmin_password:
            admin_username = settings.superadmin_username.strip()
            admin = (
                await session.execute(select(User).where(User.username == admin_username).limit(1))
            ).scalars().first()
            if admin is None:
                import uuid

                admin_email = settings.superadmin_email.strip() or f"{admin_username}@svod.local"
                admin = User(
                    id=str(uuid.uuid4()),
                    username=admin_username,
                    email=admin_email,
                    role="admin",
                    is_active=True,
                    password_hash=hash_password(settings.superadmin_password),
                    last_login=None,
                )
                session.add(admin)
                await session.commit()
            elif not admin.password_hash:
                admin.password_hash = hash_password(settings.superadmin_password)
                await session.commit()
