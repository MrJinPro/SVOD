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

            # Enrich events with agency code/state info (optional)
            if "code" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN code VARCHAR(16)"))
            if "code_group" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN code_group INTEGER"))
            if "code_text" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN code_text VARCHAR(500)"))
            if "state_name" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN state_name VARCHAR(60)"))
            if "state_is_over_process" not in col_names:
                await conn.execute(text("ALTER TABLE events ADD COLUMN state_is_over_process BOOLEAN"))

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

            # event_actions: ensure backward-compatible columns exist
            try:
                ea_cols = (await conn.execute(text("PRAGMA table_info(event_actions)"))).all()
                ea_col_names = {c[1] for c in ea_cols}
                for col_name, col_type in (
                    ("operator_name", "VARCHAR(200)"),
                    ("computer", "VARCHAR(70)"),
                    ("gbr_name", "VARCHAR(100)"),
                    ("date_key", "INTEGER"),
                    ("raw_event_id", "INTEGER"),
                    ("source_table", "VARCHAR(64)"),
                    ("source_pk", "INTEGER"),
                ):
                    if col_name not in ea_col_names:
                        await conn.execute(text(f"ALTER TABLE event_actions ADD COLUMN {col_name} {col_type}"))
            except Exception:
                # If table doesn't exist yet, Base.metadata.create_all will create it.
                pass

            # reports: optional stored files/history
            try:
                rep_cols = (await conn.execute(text("PRAGMA table_info(reports)"))).all()
                rep_names = {c[1] for c in rep_cols}
                for col_name, col_type in (
                    ("file_name", "VARCHAR(255)"),
                    ("mime_type", "VARCHAR(120)"),
                    ("storage_path", "VARCHAR(500)"),
                    ("params_json", "TEXT"),
                    ("error_message", "TEXT"),
                ):
                    if col_name not in rep_names:
                        await conn.execute(text(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}"))
            except Exception:
                # If table doesn't exist yet, Base.metadata.create_all will create it.
                pass
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

            for col_name, col_type in (
                ("code", "VARCHAR(16)"),
                ("code_group", "INTEGER"),
                ("code_text", "VARCHAR(500)"),
                ("state_name", "VARCHAR(60)"),
                ("state_is_over_process", "BOOLEAN"),
            ):
                col_exists = (
                    await conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name='events' AND column_name=:col
                            """
                        ),
                        {"col": col_name},
                    )
                ).first()
                if not col_exists:
                    await conn.execute(text(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}"))

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

            # event_actions: ensure backward-compatible columns exist
            for col_name, col_type in (
                ("operator_name", "VARCHAR(200)"),
                ("computer", "VARCHAR(70)"),
                ("gbr_name", "VARCHAR(100)"),
                ("date_key", "INTEGER"),
                ("raw_event_id", "INTEGER"),
                ("source_table", "VARCHAR(64)"),
                ("source_pk", "INTEGER"),
            ):
                col_exists = (
                    await conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name='event_actions' AND column_name=:col
                            """
                        ),
                        {"col": col_name},
                    )
                ).first()
                if not col_exists:
                    await conn.execute(text(f"ALTER TABLE event_actions ADD COLUMN {col_name} {col_type}"))

            # reports: optional stored files/history
            for col_name, col_type in (
                ("file_name", "VARCHAR(255)"),
                ("mime_type", "VARCHAR(120)"),
                ("storage_path", "VARCHAR(500)"),
                ("params_json", "TEXT"),
                ("error_message", "TEXT"),
            ):
                col_exists = (
                    await conn.execute(
                        text(
                            """
                            SELECT 1
                            FROM information_schema.columns
                            WHERE table_name='reports' AND column_name=:col
                            """
                        ),
                        {"col": col_name},
                    )
                ).first()
                if not col_exists:
                    await conn.execute(text(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}"))


async def _seed_rbac(session) -> None:
    from uuid import uuid4

    from sqlalchemy import insert, select

    from app.models.role import Permission, Role, role_permissions

    default_permissions = [
        ("rbac:manage", "Управление ролями и правами"),
        ("users:read", "Просмотр пользователей"),
        ("users:write", "Управление пользователями"),
        ("analytics:read", "Просмотр аналитики"),
    ]
    default_roles = [
        ("admin", "Администратор", True),
        ("operator", "Оператор", True),
        ("analyst", "Аналитик", True),
    ]

    perms_by_code: dict[str, Permission] = {}
    for code, name in default_permissions:
        perm = (
            await session.execute(select(Permission).where(Permission.code == code).limit(1))
        ).scalars().first()
        if perm is None:
            perm = Permission(
                id=str(uuid4()),
                code=code,
                name=name,
                description=None,
                is_system=True,
            )
            session.add(perm)
        perms_by_code[code] = perm

    roles_by_code: dict[str, Role] = {}
    for code, name, is_system in default_roles:
        role = (
            await session.execute(select(Role).where(Role.code == code).limit(1))
        ).scalars().first()
        if role is None:
            role = Role(
                id=str(uuid4()),
                code=code,
                name=name,
                description=None,
                is_system=bool(is_system),
            )
            session.add(role)
        roles_by_code[code] = role

    await session.flush()

    desired: dict[str, set[str]] = {
        "admin": {"rbac:manage", "users:read", "users:write", "analytics:read"},
        "operator": {"users:read"},
        "analyst": {"users:read", "analytics:read"},
    }

    for role_code, perm_codes in desired.items():
        role = roles_by_code[role_code]
        desired_perm_ids = {perms_by_code[c].id for c in perm_codes}
        existing_perm_ids = {
            r[0]
            for r in (
                await session.execute(
                    select(role_permissions.c.permission_id).where(role_permissions.c.role_id == role.id)
                )
            ).all()
        }
        missing = desired_perm_ids - existing_perm_ids
        if missing:
            await session.execute(
                insert(role_permissions),
                [{"role_id": role.id, "permission_id": pid} for pid in sorted(missing)],
            )


async def _migrate_legacy_user_role_to_rbac(session) -> None:
    from uuid import uuid4

    from sqlalchemy import insert, select

    from app.models.role import Role, user_roles
    from app.models.user import User

    rows = (await session.execute(select(User.id, User.role))).all()
    if not rows:
        return

    seen_codes = {str(r[1] or "").strip() for r in rows if str(r[1] or "").strip()}
    if not seen_codes:
        return

    existing_roles = (
        await session.execute(select(Role).where(Role.code.in_(sorted(seen_codes))))
    ).scalars().all()
    role_by_code = {r.code: r for r in existing_roles}

    for code in sorted(seen_codes):
        if code not in role_by_code:
            r = Role(
                id=str(uuid4()),
                code=code,
                name=code,
                description="Imported from legacy users.role",
                is_system=False,
            )
            session.add(r)
            role_by_code[code] = r

    await session.flush()

    existing_links = {
        (r[0], r[1])
        for r in (
            await session.execute(
                select(user_roles.c.user_id, user_roles.c.role_id).where(user_roles.c.role_id.in_([ro.id for ro in role_by_code.values()]))
            )
        ).all()
    }

    to_insert: list[dict[str, str]] = []
    for user_id, legacy_role in rows:
        code = str(legacy_role or "").strip()
        if not code:
            continue
        role = role_by_code.get(code)
        if role is None:
            continue
        key = (str(user_id), str(role.id))
        if key not in existing_links:
            to_insert.append({"user_id": str(user_id), "role_id": str(role.id)})

    if to_insert:
        await session.execute(insert(user_roles), to_insert)


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
        await _seed_rbac(session)
        await _migrate_legacy_user_role_to_rbac(session)
        await session.commit()

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
                from app.models.role import Role
                from app.models.role import user_roles
                from sqlalchemy import insert

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
                admin_role = (
                    await session.execute(select(Role).where(Role.code == "admin").limit(1))
                ).scalars().first()
                session.add(admin)
                await session.commit()

                if admin_role is not None:
                    await session.execute(
                        insert(user_roles),
                        [{"user_id": str(admin.id), "role_id": str(admin_role.id)}],
                    )
                    await session.commit()
            else:
                changed = False
                from app.models.role import Role
                from app.models.role import user_roles
                from sqlalchemy import insert
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

                # Ensure RBAC admin role link exists
                admin_role = (
                    await session.execute(select(Role).where(Role.code == "admin").limit(1))
                ).scalars().first()
                if admin_role is not None:
                    existing = (
                        await session.execute(
                            select(user_roles.c.user_id)
                            .where(user_roles.c.user_id == str(admin.id))
                            .where(user_roles.c.role_id == str(admin_role.id))
                            .limit(1)
                        )
                    ).first()
                    if existing is None:
                        await session.execute(
                            insert(user_roles),
                            [{"user_id": str(admin.id), "role_id": str(admin_role.id)}],
                        )
                        await session.commit()
