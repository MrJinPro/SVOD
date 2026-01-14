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

            # Make users.email nullable to allow accounts without email.
            # SQLite can't ALTER COLUMN, so we rebuild the table when needed.
            # PRAGMA table_info: (cid, name, type, notnull, dflt_value, pk)
            email_col = next((c for c in user_cols if c[1] == "email"), None)
            email_notnull = bool(email_col[3]) if email_col is not None else False
            if email_col is not None and email_notnull:
                await conn.execute(text("PRAGMA foreign_keys=OFF"))
                await conn.execute(text("ALTER TABLE users RENAME TO users_old"))
                await conn.execute(
                    text(
                        """
                        CREATE TABLE users (
                            id VARCHAR(64) NOT NULL,
                            username VARCHAR(64) NOT NULL,
                            email VARCHAR(255) NULL,
                            role VARCHAR(32) NOT NULL,
                            is_active BOOLEAN NOT NULL,
                            password_hash VARCHAR(255) NULL,
                            last_login VARCHAR(32) NULL,
                            PRIMARY KEY (id),
                            UNIQUE (username),
                            UNIQUE (email)
                        )
                        """
                    )
                )
                await conn.execute(
                    text(
                        """
                        INSERT INTO users (id, username, email, role, is_active, password_hash, last_login)
                        SELECT id, username, email, role, is_active, password_hash, last_login
                        FROM users_old
                        """
                    )
                )
                await conn.execute(text("DROP TABLE users_old"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_username ON users (username)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_email ON users (email)"))
                await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_role ON users (role)"))
                await conn.execute(text("PRAGMA foreign_keys=ON"))
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

            email_nullable = (
                await conn.execute(
                    text(
                        """
                        SELECT is_nullable
                        FROM information_schema.columns
                        WHERE table_name='users' AND column_name='email'
                        """
                    )
                )
            ).first()
            if email_nullable and str(email_nullable[0]).upper() == "NO":
                await conn.execute(text("ALTER TABLE users ALTER COLUMN email DROP NOT NULL"))


async def init_db(engine: AsyncEngine) -> None:
    # Ensure models are imported so SQLAlchemy registers tables
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await _ensure_schema(engine)

    from sqlalchemy import select
    from app.db.session import SessionLocal
    from app.models.user import User
    from app.core.config import settings
    from app.core.security import hash_password

    async with SessionLocal() as session:
        # Cleanup legacy prototype seed users (from older versions) to avoid confusion in real deployments.
        # These users were created with fixed ids "1".."4" and should not exist in real data.
        from sqlalchemy import delete

        keep_seed = (settings.__dict__.get("keep_prototype_users") or "").strip().lower() in {"1", "true", "yes"}
        if not keep_seed:
            await session.execute(
                delete(User).where(User.id.in_(["1", "2", "3", "4"]))
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

                admin_email = settings.superadmin_email.strip() or None
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
            else:
                changed = False
                if not admin.password_hash:
                    admin.password_hash = hash_password(settings.superadmin_password)
                    changed = True
                if admin.role != "admin":
                    admin.role = "admin"
                    changed = True
                if not admin.is_active:
                    admin.is_active = True
                    changed = True
                if settings.superadmin_email.strip() and not admin.email:
                    admin.email = settings.superadmin_email.strip()
                    changed = True
                if changed:
                    await session.commit()
