from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.agency_mysql import fetch_alarms_since
from app.integrations.agency_mssql import fetch_archive_events_since, fetch_objects_snapshot
from app.core.config import settings
from app.models.event import Event
from app.models.object import Object, ObjectGroup, Responsible, ResponsiblePhone
from app.models.sync_state import SyncState


SYNC_KEY_LAST_ALARM_ID = "agency_mysql.last_alarm_id"
SYNC_KEY_MSSQL_EVENT_CURSOR = "agency_mssql.archive.cursor"


def _derive_severity(row: dict[str, Any]) -> str:
    # Minimal MVP heuristic
    if row.get("IS_PROPAZHA"):
        return "critical"
    if row.get("IS_SHTRAF"):
        return "warning"
    return "info"


def _derive_status(row: dict[str, Any]) -> str:
    if row.get("IS_DONE"):
        return "resolved"
    if row.get("IS_ZAYAVKA"):
        return "pending"
    return "active"


def _build_description(row: dict[str, Any]) -> str:
    parts: list[str] = []
    for label, key in (
        ("Осмотр", "OSMOTR"),
        ("Результат", "RESULT_OSMOTR"),
        ("Заметки", "ZAMETKI"),
        ("Заявка", "RESULT_ZAYAVKA"),
        ("Шлейф", "NUMBER_SHLEIF"),
        ("Штраф", "NUM_SHTRAF"),
        ("ГБР", "NUMBER_CAR"),
        ("Инженер", "FIO_ENGINEERS"),
        ("Оператор", "FIO_OPERATORS"),
    ):
        v = row.get(key)
        if isinstance(v, str) and v.strip():
            parts.append(f"{label}: {v.strip()}")
    return "\n".join(parts) if parts else ""


def _object_name(row: dict[str, Any]) -> str:
    num = (row.get("OBJ_NUMBER") or "").strip()
    if num:
        return f"Объект {num}"
    obj_id = row.get("ID_OBJECTS")
    return f"Объект {obj_id}" if obj_id is not None else "Объект"


async def get_last_alarm_id(session: AsyncSession) -> int:
    row = await session.get(SyncState, SYNC_KEY_LAST_ALARM_ID)
    if not row:
        return 0
    try:
        return int(row.value)
    except Exception:
        return 0


async def set_last_alarm_id(session: AsyncSession, value: int) -> None:
    row = await session.get(SyncState, SYNC_KEY_LAST_ALARM_ID)
    if row is None:
        row = SyncState(key=SYNC_KEY_LAST_ALARM_ID, value=str(value), updated_at=datetime.utcnow())
        session.add(row)
    else:
        row.value = str(value)
        row.updated_at = datetime.utcnow()


async def sync_events_from_agency_mysql(
    session: AsyncSession,
    agency_mysql_url: str,
    batch_limit: int = 500,
) -> dict[str, Any]:
    last_id = await get_last_alarm_id(session)
    rows = fetch_alarms_since(mysql_url=agency_mysql_url, last_id=last_id, limit=batch_limit)
    if not rows:
        return {"status": "ok", "processed": 0, "lastId": last_id}

    events_to_insert: list[dict[str, Any]] = []
    max_id = last_id

    for r in rows:
        alarm_id = r.get("ID_ALARMS")
        if alarm_id is None:
            continue
        try:
            alarm_id_int = int(alarm_id)
        except Exception:
            continue
        max_id = max(max_id, alarm_id_int)

        ts = r.get("_TS")
        if not isinstance(ts, datetime):
            continue

        events_to_insert.append(
            {
                "id": str(alarm_id_int),
                "timestamp": ts,
                "type": "alarm",
                "object_name": _object_name(r),
                "client_name": (r.get("OBJ_FIO") or "").strip() or "Не указан",
                "severity": _derive_severity(r),
                "status": _derive_status(r),
                "description": _build_description(r),
                "location": (r.get("OBJ_ADRESS") or "").strip() or None,
                "operator_id": (r.get("FIO_OPERATORS") or "").strip() or None,
            }
        )

    if not events_to_insert:
        return {"status": "ok", "processed": 0, "lastId": last_id}

    dialect = None
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
    except Exception:
        dialect = None

    result = None
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Event).values(events_to_insert).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt)
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # For SQLite, avoid generating a single massive VALUES (...) statement
        # which can exceed SQLite's variable limit (~999) for large batches.
        stmt = sqlite_insert(Event).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt, events_to_insert)
    else:
        # Fallback: insert one by one, ignoring duplicates
        existing_ids = set(
            (await session.execute(select(Event.id).where(Event.id.in_([r["id"] for r in events_to_insert])))).scalars().all()
        )
        for r in events_to_insert:
            if r["id"] in existing_ids:
                continue
            session.add(Event(**r))

    await set_last_alarm_id(session, max_id)
    await session.commit()

    # rowcount can be None for some drivers; fall back to len
    inserted = 0
    if result is not None:
        inserted = result.rowcount if result.rowcount is not None else len(events_to_insert)
    else:
        inserted = len(events_to_insert)
    return {"status": "ok", "processed": int(inserted), "lastId": max_id}


def _safe_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


async def get_mssql_event_cursor(session: AsyncSession) -> tuple[int, int]:
    """Возвращает (Date_Key, Event_id)."""
    row = await session.get(SyncState, SYNC_KEY_MSSQL_EVENT_CURSOR)
    if not row or not row.value:
        # По умолчанию: стартуем с первого числа текущего месяца,
        # либо с явно заданного Date_Key через env.
        if settings.agency_mssql_archive_start_date_key is not None:
            return (int(settings.agency_mssql_archive_start_date_key), 0)
        month_start_key = int(datetime.utcnow().strftime("%Y%m01"))
        return (month_start_key, 0)
    try:
        parts = row.value.split(":", 1)
        return (int(parts[0]), int(parts[1] if len(parts) > 1 else 0))
    except Exception:
        today_key = int(datetime.utcnow().strftime("%Y%m%d"))
        return (today_key, 0)


async def set_mssql_event_cursor(session: AsyncSession, date_key: int, event_id: int) -> None:
    value = f"{int(date_key)}:{int(event_id)}"
    row = await session.get(SyncState, SYNC_KEY_MSSQL_EVENT_CURSOR)
    if row is None:
        row = SyncState(key=SYNC_KEY_MSSQL_EVENT_CURSOR, value=value, updated_at=datetime.utcnow())
        session.add(row)
    else:
        row.value = value
        row.updated_at = datetime.utcnow()


async def sync_objects_from_agency_mssql(
    session: AsyncSession,
    agency_mssql_url: str,
) -> dict[str, Any]:
    """Синхронизирует объекты/группы/ответственных из MSSQL агентства в локальную БД SVOD."""

    snap = fetch_objects_snapshot(agency_mssql_url)
    objects = snap.get("objects") or []
    groups = snap.get("groups") or []
    responsibles = snap.get("responsibles") or []
    phones = snap.get("phones") or []

    # Индексы для быстрого связывания
    groups_by_panel: dict[str, list[dict[str, Any]]] = {}
    for g in groups:
        pid = _safe_str(g.get("Panel_id"))
        if not pid:
            continue
        groups_by_panel.setdefault(pid, []).append(g)

    resp_by_panel: dict[str, list[dict[str, Any]]] = {}
    for r in responsibles:
        pid = _safe_str(r.get("Panel_id"))
        if not pid:
            continue
        resp_by_panel.setdefault(pid, []).append(r)

    phones_by_list: dict[int, list[dict[str, Any]]] = {}
    for p in phones:
        try:
            lid = int(p.get("ListId"))
        except Exception:
            continue
        phones_by_list.setdefault(lid, []).append(p)

    from sqlalchemy import delete

    upserted = 0
    for o in objects:
        panel_id = _safe_str(o.get("Panel_id"))
        if not panel_id:
            continue

        # Delete children first to avoid SQLAlchemy autoflush inserting/updating
        # the parent object before the cleanup statements run.
        await session.execute(delete(ObjectGroup).where(ObjectGroup.object_id == panel_id))
        await session.execute(delete(Responsible).where(Responsible.object_id == panel_id))

        # Upsert основной карточки
        obj = await session.get(Object, panel_id)
        if obj is None:
            obj = Object(id=panel_id)
            session.add(obj)

        company_name = _safe_str(o.get("CompanyName"))
        company_address = _safe_str(o.get("CompanyAddress"))
        company_memo = _safe_str(o.get("CompanyMemo"))

        obj.name = company_name or panel_id
        obj.address = company_address
        obj.client_name = company_name
        obj.disabled = bool(o.get("Disabled") or False)
        obj.remarks = _safe_str(o.get("Remarks"))
        obj.additional_info = _safe_str(o.get("AdditionalTechnicalInformation")) or company_memo
        obj.latitude = _safe_str(o.get("Latitude"))
        obj.longitude = _safe_str(o.get("Longtitude"))
        obj.created_at = o.get("CreateDate") if isinstance(o.get("CreateDate"), datetime) else obj.created_at
        obj.updated_at = datetime.utcnow()

        for g in groups_by_panel.get(panel_id, []):
            try:
                group_no = int(g.get("GroupNo"))
            except Exception:
                continue
            session.add(
                ObjectGroup(
                    object_id=panel_id,
                    group_no=group_no,
                    name=str(g.get("GroupName") or ""),
                    is_open=g.get("IsOpen"),
                    time_event=g.get("TimeEvent") if isinstance(g.get("TimeEvent"), datetime) else None,
                )
            )

        # Ответственные + телефоны
        for r in resp_by_panel.get(panel_id, []):
            try:
                group_no = int(r.get("GroupNo"))
            except Exception:
                group_no = None
            try:
                order_no = int(r.get("OrderNo"))
            except Exception:
                order_no = None

            resp = Responsible(
                object_id=panel_id,
                group_no=group_no,
                order_no=order_no,
                name=str(r.get("ResponsibleName") or ""),
                address=_safe_str(r.get("ResponsibleAddress")),
            )
            session.add(resp)
            await session.flush()  # получить resp.id для телефонов

            try:
                list_id = int(r.get("ListId"))
            except Exception:
                list_id = None

            if list_id is not None:
                for ph in phones_by_list.get(list_id, []):
                    phone = _safe_str(ph.get("PhoneNo"))
                    if not phone:
                        continue
                    type_id = ph.get("TypeId")
                    type_name = f"type:{type_id}" if type_id is not None else None
                    session.add(ResponsiblePhone(responsible_id=resp.id, phone=phone, type_name=type_name))

        upserted += 1

    await session.commit()
    return {
        "status": "ok",
        "objects": int(upserted),
        "sourceObjects": int(len(objects)),
        "sourceGroups": int(len(groups)),
        "sourceResponsibles": int(len(responsibles)),
        "sourcePhones": int(len(phones)),
    }


async def sync_events_from_agency_mssql_archives(
    session: AsyncSession,
    agency_mssql_url: str,
    *,
    archives_db_name: str,
    batch_limit: int = 500,
) -> dict[str, Any]:
    """Синхронизирует события из месячных архивных таблиц MSSQL (pult4db_archives)."""

    cur_date_key, cur_event_id = await get_mssql_event_cursor(session)
    rows = fetch_archive_events_since(
        agency_mssql_url,
        archives_db_name=archives_db_name,
        cursor_date_key=cur_date_key,
        cursor_event_id=cur_event_id,
        limit=batch_limit,
    )
    if not rows:
        return {"status": "ok", "processed": 0, "cursor": f"{cur_date_key}:{cur_event_id}"}

    events_to_insert: list[dict[str, Any]] = []
    max_date_key = cur_date_key
    max_event_id = cur_event_id

    for r in rows:
        try:
            date_key = int(r.get("Date_Key"))
            event_id = int(r.get("Event_id"))
        except Exception:
            continue

        max_date_key, max_event_id = (date_key, event_id)

        ts = r.get("TimeEvent")
        if not isinstance(ts, datetime):
            continue

        panel_id = _safe_str(r.get("Panel_id"))

        code = _safe_str(r.get("Code"))
        zone = r.get("Zone")
        line = _safe_str(r.get("Line"))
        result_text = _safe_str(r.get("Result_Text"))

        name_state = _safe_str(r.get("NameState"))
        person = _safe_str(r.get("PersonName"))
        gbr = _safe_str(r.get("GrResponseName"))

        desc_parts: list[str] = []
        if code:
            desc_parts.append(f"Code: {code}")
        if zone is not None:
            desc_parts.append(f"Zone: {zone}")
        if line:
            desc_parts.append(f"Line: {line}")
        if name_state:
            desc_parts.append(f"State: {name_state}")
        if person:
            desc_parts.append(f"Person: {person}")
        if gbr:
            desc_parts.append(f"GBR: {gbr}")
        if result_text:
            desc_parts.append(result_text)

        status = "resolved" if name_state else "active"

        events_to_insert.append(
            {
                "id": f"mssql:{date_key}:{event_id}",
                "timestamp": ts,
                "type": "alarm",
                "object_id": panel_id,
                "object_name": panel_id or "Объект",
                "client_name": None,
                "severity": "info",
                "status": status,
                "description": "\n".join(desc_parts) if desc_parts else "",
                "location": None,
                "operator_id": person,
            }
        )

    if not events_to_insert:
        return {"status": "ok", "processed": 0, "cursor": f"{cur_date_key}:{cur_event_id}"}

    dialect = None
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
    except Exception:
        dialect = None

    result = None
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Event).values(events_to_insert).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt)
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # For SQLite, avoid generating a single massive VALUES (...) statement
        # which can exceed SQLite's variable limit (~999) for large batches.
        stmt = sqlite_insert(Event).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt, events_to_insert)
    else:
        existing_ids = set(
            (
                await session.execute(select(Event.id).where(Event.id.in_([r["id"] for r in events_to_insert])))
            )
            .scalars()
            .all()
        )
        for r in events_to_insert:
            if r["id"] in existing_ids:
                continue
            session.add(Event(**r))

    await set_mssql_event_cursor(session, max_date_key, max_event_id)
    await session.commit()

    inserted = 0
    if result is not None:
        inserted = result.rowcount if result.rowcount is not None else len(events_to_insert)
    else:
        inserted = len(events_to_insert)

    return {
        "status": "ok",
        "processed": int(inserted),
        "cursor": f"{max_date_key}:{max_event_id}",
    }
