from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.sync_service import (
    sync_events_from_agency_mssql_archives,
    sync_events_from_agency_mysql,
    sync_objects_from_agency_mssql,
)
from app.prototype_data import mock_events
from app.models.event import Event
from app.models.object import Object

from app.db.session import get_session

router = APIRouter()

# SQLite allows only one writer at a time. If users click buttons quickly or
# multiple clients run sync concurrently, the DB can get locked.
_SYNC_LOCK = asyncio.Lock()


@router.post("/sync/events")
async def sync_events_once(limit: int = Query(500, ge=1, le=5000)) -> dict[str, Any]:
    """Запускает один пакет синхронизации событий из агентской БД в локальную БД SVOD.

    Это удобно для быстрого демо без Celery/beat: дернуть 1 раз и увидеть реальные события во фронте.
    """
    if not settings.agency_database_url:
        return {"status": "skipped", "reason": "AGENCY_DATABASE_URL not set"}

    url = settings.agency_database_url
    scheme = (url.split(":", 1)[0] or "").lower()

    async with _SYNC_LOCK:
        async for session in get_session():
            session = session  # type: ignore[no-redef]
            if scheme.startswith("mysql"):
                return await sync_events_from_agency_mysql(
                    session=session,
                    agency_mysql_url=url,
                    batch_limit=limit,
                )
            if scheme.startswith("mssql"):
                return await sync_events_from_agency_mssql_archives(
                    session=session,
                    agency_mssql_url=url,
                    archives_db_name=settings.agency_archives_db_name,
                    batch_limit=limit,
                )
            return {"status": "error", "reason": f"Unsupported AGENCY_DATABASE_URL scheme: {scheme}"}
    return {"status": "error", "reason": "No DB session"}


@router.post("/sync/objects")
async def sync_objects_once() -> dict[str, Any]:
    """Синхронизирует справочник объектов (Panel/Groups/Responsibles) из MSSQL агентства."""

    if not settings.agency_database_url:
        return {"status": "skipped", "reason": "AGENCY_DATABASE_URL not set"}

    url = settings.agency_database_url
    scheme = (url.split(":", 1)[0] or "").lower()
    if not scheme.startswith("mssql"):
        return {"status": "error", "reason": "AGENCY_DATABASE_URL must be MSSQL for /sync/objects"}

    async with _SYNC_LOCK:
        async for session in get_session():
            session = session  # type: ignore[no-redef]
            return await sync_objects_from_agency_mssql(session=session, agency_mssql_url=url)
    return {"status": "error", "reason": "No DB session"}


@router.post("/seed/demo-events")
async def seed_demo_events(count: int = Query(300, ge=1, le=5000)) -> dict[str, Any]:
    """Заполняет Postgres демо-событиями.

    Нужен для демонстрации UI, когда нет сетевого доступа к MySQL агентства.
    """
    from datetime import date as date_type
    from datetime import datetime
    import random

    if not settings.enable_demo_seed:
        raise HTTPException(status_code=404, detail="Demo seed disabled")

    async for session in get_session():
        today = date_type.today()
        rows: list[dict[str, Any]] = []
        if not mock_events:
            return {"status": "skipped", "reason": "no demo templates"}

        # Создаём демо-объекты на основе шаблонов, чтобы можно было
        # показывать карточку объекта и события по объекту.
        by_name: dict[str, str] = {}
        object_rows: list[dict[str, Any]] = []
        for tpl in mock_events:
            name = str(tpl.get("objectName") or "")
            if not name or name in by_name:
                continue
            obj_id = f"demo-obj-{len(by_name) + 1}"
            by_name[name] = obj_id
            object_rows.append(
                {
                    "id": obj_id,
                    "name": name,
                    "address": tpl.get("location"),
                    "client_name": tpl.get("clientName"),
                    "disabled": False,
                    "remarks": None,
                    "additional_info": None,
                    "latitude": None,
                    "longitude": None,
                    "created_at": datetime.combine(today, datetime.min.time()),
                    "updated_at": datetime.combine(today, datetime.min.time()),
                }
            )

        # Генерируем достаточно событий для демонстрации UI (графики/таблицы/поиск).
        # Времена распределяем по текущим суткам.
        for i in range(count):
            tpl = random.choice(mock_events)

            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            ts = datetime.combine(today, datetime.min.time()).replace(hour=hour, minute=minute, second=second)

            rows.append(
                {
                    "id": f"demo-{i+1}",
                    "timestamp": ts,
                    "type": str(tpl.get("type")),
                    "object_id": by_name.get(str(tpl.get("objectName") or "")),
                    "object_name": str(tpl.get("objectName")),
                    "client_name": str(tpl.get("clientName")),
                    "severity": str(tpl.get("severity")),
                    "status": str(tpl.get("status")),
                    "description": str(tpl.get("description")),
                    "location": tpl.get("location"),
                    "operator_id": tpl.get("operatorId"),
                }
            )

        if not rows:
            return {"status": "skipped", "reason": "no demo rows"}

        # Идемпотентность: удаляем предыдущий демо-сид.
        from sqlalchemy import delete

        await session.execute(delete(Event).where(Event.id.like("demo-%")))
        await session.execute(delete(Object).where(Object.id.like("demo-obj-%")))

        # Сначала объекты
        if object_rows:
            try:
                bind = session.get_bind()
                dialect = getattr(bind, "dialect", None)
            except Exception:
                dialect = None

            if dialect is not None and getattr(dialect, "name", None) == "postgresql":
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                await session.execute(pg_insert(Object).values(object_rows))
            elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
                from sqlalchemy.dialects.sqlite import insert as sqlite_insert

                # Use executemany to avoid SQLite variable limit for large batches.
                await session.execute(sqlite_insert(Object), object_rows)
            else:
                for r in object_rows:
                    session.add(Object(**r))

        try:
            bind = session.get_bind()
            dialect = getattr(bind, "dialect", None)
        except Exception:
            dialect = None

        if dialect is not None and getattr(dialect, "name", None) == "postgresql":
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(Event).values(rows)
            await session.execute(stmt)
        elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            # Use executemany to avoid SQLite variable limit for large batches.
            await session.execute(sqlite_insert(Event), rows)
        else:
            for r in rows:
                session.add(Event(**r))
        await session.commit()
        return {"status": "ok", "objects": int(len(object_rows)), "events": int(len(rows))}

    return {"status": "error", "reason": "No DB session"}


@router.get("/tables")
async def list_tables(
    include_system: bool = Query(False, description="Включать системные схемы PostgreSQL"),
) -> dict[str, Any]:
    """Быстрый просмотр таблиц в подключенной БД.

    Это специально сделано, чтобы вы могли параллельно разбираться
    с большой схемой (50+ таблиц) без ручного лазания по клиенту.
    """
    async for session in get_session():
        session: AsyncSession
        if include_system:
            q = text(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                ORDER BY table_schema, table_name
                """
            )
        else:
            q = text(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type='BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """
            )
        rows = (await session.execute(q)).mappings().all()
        return {"count": len(rows), "tables": [dict(r) for r in rows]}

    return {"count": 0, "tables": []}


@router.get("/columns")
async def list_columns(
    table_schema: str = Query(..., description="Напр. public"),
    table_name: str = Query(..., description="Имя таблицы"),
) -> dict[str, Any]:
    async for session in get_session():
        session: AsyncSession
        q = text(
            """
            SELECT
              column_name,
              data_type,
              is_nullable,
              column_default
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
            ORDER BY ordinal_position
            """
        )
        rows = (
            await session.execute(q, {"schema": table_schema, "table": table_name})
        ).mappings().all()
        return {"count": len(rows), "columns": [dict(r) for r in rows]}

    return {"count": 0, "columns": []}
