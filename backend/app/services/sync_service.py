from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.agency_mysql import fetch_alarms_since
from app.integrations.agency_mssql import fetch_archive_events_recent, fetch_archive_events_since, fetch_objects_snapshot
from app.integrations.agency_mssql import (
    fetch_eventservice_actions_for_event_pairs as fetch_eventservice_actions_for_event_pairs_mssql,
)
from app.integrations.agency_sqlite import (
    fetch_archive_events_since as fetch_archive_events_since_sqlite,
)
from app.integrations.agency_sqlite import fetch_objects_snapshot as fetch_objects_snapshot_sqlite
from app.integrations.agency_sqlite import (
    fetch_eventservice_actions_for_event_pairs as fetch_eventservice_actions_for_event_pairs_sqlite,
)
from app.core.config import settings
from app.models.event import Event
from app.models.event_action import EventAction
from app.models.object import Object, ObjectGroup, Responsible, ResponsiblePhone
from app.models.sync_state import SyncState


logger = logging.getLogger(__name__)


SYNC_KEY_LAST_ALARM_ID = "agency_mysql.last_alarm_id"
SYNC_KEY_MSSQL_EVENT_CURSOR = "agency_mssql.archive.cursor"
SYNC_KEY_SQLITE_EVENT_CURSOR = "agency_sqlite.archive.cursor"


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
                "object_id": None,
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

        insert_stmt = pg_insert(Event).values(events_to_insert)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[Event.id],
            set_={
                "timestamp": insert_stmt.excluded.timestamp,
                "type": insert_stmt.excluded.type,
                "object_id": insert_stmt.excluded.object_id,
                "object_name": insert_stmt.excluded.object_name,
                "client_name": insert_stmt.excluded.client_name,
                "severity": insert_stmt.excluded.severity,
                "status": insert_stmt.excluded.status,
                "description": insert_stmt.excluded.description,
                "location": insert_stmt.excluded.location,
                "operator_id": insert_stmt.excluded.operator_id,
                "code": insert_stmt.excluded.code,
                "code_group": insert_stmt.excluded.code_group,
                "code_text": insert_stmt.excluded.code_text,
                "state_name": insert_stmt.excluded.state_name,
                "state_is_over_process": insert_stmt.excluded.state_is_over_process,
            },
        )
        result = await session.execute(stmt)
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy import bindparam
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # For SQLite, avoid generating a single massive VALUES (...) statement
        # which can exceed SQLite's variable limit (~999) for large batches.
        stmt = (
            sqlite_insert(Event)
            .values(
                id=bindparam("id"),
                timestamp=bindparam("timestamp"),
                type=bindparam("type"),
                object_id=bindparam("object_id"),
                object_name=bindparam("object_name"),
                client_name=bindparam("client_name"),
                severity=bindparam("severity"),
                status=bindparam("status"),
                description=bindparam("description"),
                location=bindparam("location"),
                operator_id=bindparam("operator_id"),
            )
            .on_conflict_do_nothing(index_elements=[Event.id])
        )
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
        rc = getattr(result, "rowcount", None)
        inserted = len(events_to_insert) if (rc is None or rc < 0) else int(rc)
    else:
        inserted = len(events_to_insert)
    return {"status": "ok", "processed": int(inserted), "lastId": max_id}


def _safe_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _coerce_dt(v: Any) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        # Typical SQL Server formats: "YYYY-MM-DD HH:MM:SS[.fff]" or ISO.
        try:
            return datetime.fromisoformat(s.replace(" ", "T", 1))
        except Exception:
            pass

        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None
    return None


async def sync_recent_events_from_agency_mssql_archives(
    session: AsyncSession,
    agency_mssql_url: str,
    *,
    archives_db_name: str,
    lookback_days: int = 2,
    batch_limit: int = 500,
) -> dict[str, Any]:
    """Подхватывает самые свежие события за окно lookback_days.

    Не зависит от курсора: нужно, чтобы новые события появлялись сразу,
    пока исторический backfill ещё идёт.
    """

    if batch_limit <= 0:
        return {"status": "ok", "processed": 0, "actionsProcessed": 0, "actionsFetched": 0}

    lb = max(0, int(lookback_days))
    d_to = date.today()
    d_from = d_to - timedelta(days=lb)

    date_to_key = int(d_to.strftime("%Y%m%d"))
    date_from_key = int(d_from.strftime("%Y%m%d"))

    rows = fetch_archive_events_recent(
        agency_mssql_url,
        archives_db_name=archives_db_name,
        date_from_key=date_from_key,
        date_to_key=date_to_key,
        limit=batch_limit,
    )
    if not rows:
        return {"status": "ok", "processed": 0, "actionsProcessed": 0, "actionsFetched": 0}

    panel_ids: set[str] = set()
    for r in rows:
        pid = _safe_str(r.get("Panel_id"))
        if pid:
            panel_ids.add(pid)

    objects_by_id: dict[str, Object] = {}
    if panel_ids:
        objs = (
            await session.execute(select(Object).where(Object.id.in_(list(panel_ids))))
        ).scalars().all()
        objects_by_id = {o.id: o for o in objs}

    events_to_insert: list[dict[str, Any]] = []
    event_pairs: set[tuple[int, int]] = set()

    for r in rows:
        try:
            date_key = int(r.get("Date_Key"))
            event_id = int(r.get("Event_id"))
        except Exception:
            continue

        event_pairs.add((date_key, event_id))

        ts = r.get("TimeEvent")
        if not isinstance(ts, datetime):
            continue

        panel_id = _safe_str(r.get("Panel_id"))
        obj = objects_by_id.get(panel_id) if panel_id else None

        code = _safe_str(r.get("Code"))
        code_text = _safe_str(r.get("CodeText"))
        zone = r.get("Zone")
        line = _safe_str(r.get("Line"))
        result_text = _safe_str(r.get("Result_Text"))

        state_event = r.get("StateEvent")
        state_name = _safe_str(r.get("StateName"))
        state_is_over = r.get("StateIsOverProcess")

        name_state = _safe_str(r.get("NameState"))
        person = _safe_str(r.get("PersonName"))
        gbr = _safe_str(r.get("GrResponseName"))

        desc_parts: list[str] = []
        desc_parts.append(f"Event_id: {event_id}")
        desc_parts.append(f"Date_Key: {date_key}")
        if panel_id:
            desc_parts.append(f"Panel_id: {panel_id}")

        if code:
            if code_text:
                desc_parts.append(f"Код: {code} — {code_text}")
            else:
                desc_parts.append(f"Код: {code}")
        if zone is not None:
            desc_parts.append(f"Зона: {zone}")
        if line:
            desc_parts.append(f"Шлейф: {line}")

        if state_event is not None or state_name:
            st_id = str(state_event) if state_event is not None else ""
            st_label = state_name or name_state or ""
            if st_id and st_label:
                desc_parts.append(f"Статус: {st_label} (StateEvent={st_id})")
            elif st_label:
                desc_parts.append(f"Статус: {st_label}")
            elif st_id:
                desc_parts.append(f"StateEvent: {st_id}")

        if person:
            desc_parts.append(f"Оператор: {person}")
        if gbr:
            desc_parts.append(f"ГБР: {gbr}")
        if result_text:
            desc_parts.append(result_text)

        is_over = bool(state_is_over) if state_is_over is not None else False
        if is_over:
            status = "resolved"
        elif state_event is not None or state_name or name_state:
            status = "pending"
        else:
            status = "active"

        events_to_insert.append(
            {
                "id": f"mssql:{date_key}:{event_id}",
                "timestamp": ts,
                "type": "alarm",
                "object_id": panel_id,
                "object_name": (obj.name if obj and obj.name else None) or panel_id or "Объект",
                "client_name": (obj.client_name if obj and obj.client_name else None) or panel_id or "Не указан",
                "severity": "info",
                "status": status,
                "code": code,
                "code_group": int(r.get("CodeGroup")) if r.get("CodeGroup") is not None else None,
                "code_text": code_text,
                "state_name": state_name,
                "state_is_over_process": bool(state_is_over) if state_is_over is not None else None,
                "description": "\n".join(desc_parts) if desc_parts else "",
                "result_text": result_text,
                "location": (obj.address if obj and obj.address else None),
                "operator_id": person,
            }
        )

    if not events_to_insert:
        return {"status": "ok", "processed": 0, "actionsProcessed": 0, "actionsFetched": 0}

    actions_to_insert: list[dict[str, Any]] = []
    actions_fetched = 0
    if event_pairs:
        try:
            action_rows = fetch_eventservice_actions_for_event_pairs_mssql(
                agency_mssql_url,
                archives_db_name=archives_db_name,
                event_pairs=list(event_pairs),
            )
            actions_fetched = len(action_rows)
        except Exception:
            logger.exception("Failed to fetch mssql eventservice actions (recent)")
            action_rows = []

        for ar in action_rows:
            try:
                dk = int(ar.get("Date_Key"))
                eid = int(ar.get("Event_id"))
                sid = int(ar.get("Service_id"))
            except Exception:
                continue

            action_name = _safe_str(ar.get("NameState"))
            if not action_name:
                continue

            action_time = _coerce_dt(ar.get("OperationTime"))
            if not isinstance(action_time, datetime):
                continue

            source_table = _eventservice_source_table(dk)
            actions_to_insert.append(
                {
                    "id": _uuid_for_source(source_table, sid),
                    "event_id": f"mssql:{dk}:{eid}",
                    "action_name": action_name,
                    "action_time": action_time,
                    "operator_name": _safe_str(ar.get("PersonName")),
                    "computer": _safe_str(ar.get("Computer")),
                    "gbr_name": _safe_str(ar.get("GrResponseName")),
                    "date_key": dk,
                    "raw_event_id": eid,
                    "source_table": source_table,
                    "source_pk": sid,
                }
            )

    dialect = None
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
    except Exception:
        dialect = None

    result = None
    actions_result = None
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        result = await session.execute(
            pg_insert(Event).values(events_to_insert).on_conflict_do_nothing(index_elements=[Event.id])
        )
        if actions_to_insert:
            actions_result = await session.execute(
                pg_insert(EventAction)
                .values(actions_to_insert)
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy import bindparam
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = (
            sqlite_insert(Event)
            .values(
                id=bindparam("id"),
                timestamp=bindparam("timestamp"),
                type=bindparam("type"),
                object_id=bindparam("object_id"),
                object_name=bindparam("object_name"),
                client_name=bindparam("client_name"),
                severity=bindparam("severity"),
                status=bindparam("status"),
                code=bindparam("code"),
                code_group=bindparam("code_group"),
                code_text=bindparam("code_text"),
                state_name=bindparam("state_name"),
                state_is_over_process=bindparam("state_is_over_process"),
                description=bindparam("description"),
                location=bindparam("location"),
                operator_id=bindparam("operator_id"),
            )
            .on_conflict_do_update(
                index_elements=[Event.id],
                set_={
                    "timestamp": sqlite_insert(Event).excluded.timestamp,
                    "type": sqlite_insert(Event).excluded.type,
                    "object_id": sqlite_insert(Event).excluded.object_id,
                    "object_name": sqlite_insert(Event).excluded.object_name,
                    "client_name": sqlite_insert(Event).excluded.client_name,
                    "severity": sqlite_insert(Event).excluded.severity,
                    "status": sqlite_insert(Event).excluded.status,
                    "description": sqlite_insert(Event).excluded.description,
                    "location": sqlite_insert(Event).excluded.location,
                    "operator_id": sqlite_insert(Event).excluded.operator_id,
                    "code": sqlite_insert(Event).excluded.code,
                    "code_group": sqlite_insert(Event).excluded.code_group,
                    "code_text": sqlite_insert(Event).excluded.code_text,
                    "state_name": sqlite_insert(Event).excluded.state_name,
                    "state_is_over_process": sqlite_insert(Event).excluded.state_is_over_process,
                },
            )
        )
        result = await session.execute(stmt, events_to_insert)

        if actions_to_insert:
            a_stmt = (
                sqlite_insert(EventAction)
                .values(
                    id=bindparam("id"),
                    event_id=bindparam("event_id"),
                    action_name=bindparam("action_name"),
                    action_time=bindparam("action_time"),
                    operator_name=bindparam("operator_name"),
                    computer=bindparam("computer"),
                    gbr_name=bindparam("gbr_name"),
                    date_key=bindparam("date_key"),
                    raw_event_id=bindparam("raw_event_id"),
                    source_table=bindparam("source_table"),
                    source_pk=bindparam("source_pk"),
                )
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
            actions_result = await session.execute(a_stmt, actions_to_insert)
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

        if actions_to_insert:
            existing_src: set[tuple[str, int]] = set()
            by_table: dict[str, list[int]] = {}
            for r in actions_to_insert:
                by_table.setdefault(r["source_table"], []).append(int(r["source_pk"]))
            for st, pks in by_table.items():
                found = (
                    await session.execute(
                        select(EventAction.source_pk).where(
                            (EventAction.source_table == st) & (EventAction.source_pk.in_(pks))
                        )
                    )
                ).scalars().all()
                for pk in found:
                    existing_src.add((st, int(pk)))
            for r in actions_to_insert:
                key = (r["source_table"], int(r["source_pk"]))
                if key in existing_src:
                    continue
                session.add(EventAction(**r))

    await session.commit()

    inserted = 0
    if result is not None:
        rc = getattr(result, "rowcount", None)
        inserted = len(events_to_insert) if (rc is None or rc < 0) else int(rc)
    else:
        inserted = len(events_to_insert)

    actions_inserted = 0
    if actions_to_insert:
        if actions_result is not None:
            rc = getattr(actions_result, "rowcount", None)
            actions_inserted = len(actions_to_insert) if (rc is None or rc < 0) else int(rc)
        else:
            actions_inserted = len(actions_to_insert)

    return {
        "status": "ok",
        "processed": int(inserted),
        "actionsProcessed": int(actions_inserted),
        "actionsFetched": int(actions_fetched),
        "window": {"from": date_from_key, "to": date_to_key},
    }


def _eventservice_source_table(date_key: int) -> str:
    s = str(int(date_key))
    suffix = (s[:6] + "01") if len(s) >= 6 else s
    return f"eventservice{suffix}"


def _uuid_for_source(source_table: str, source_pk: int) -> str:
    # Stable deterministic UUID: allows safe re-sync without churn.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_table}:{int(source_pk)}"))


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


async def get_sqlite_event_cursor(session: AsyncSession) -> tuple[int, int]:
    """Возвращает (Date_Key, Event_id) для SQLite архивов."""
    row = await session.get(SyncState, SYNC_KEY_SQLITE_EVENT_CURSOR)
    if not row or not row.value:
        start_key = int(settings.agency_sqlite_archive_start_date_key or 20230101)
        return (start_key, 0)
    try:
        parts = row.value.split(":", 1)
        return (int(parts[0]), int(parts[1] if len(parts) > 1 else 0))
    except Exception:
        start_key = int(settings.agency_sqlite_archive_start_date_key or 20230101)
        return (start_key, 0)


async def set_sqlite_event_cursor(session: AsyncSession, date_key: int, event_id: int) -> None:
    value = f"{int(date_key)}:{int(event_id)}"
    row = await session.get(SyncState, SYNC_KEY_SQLITE_EVENT_CURSOR)
    if row is None:
        row = SyncState(key=SYNC_KEY_SQLITE_EVENT_CURSOR, value=value, updated_at=datetime.utcnow())
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


async def sync_objects_from_agency_sqlite(
    session: AsyncSession,
    agency_sqlite_url: str,
) -> dict[str, Any]:
    """Синхронизирует объекты/группы/ответственных из SQLite-слепка агентства."""

    snap = fetch_objects_snapshot_sqlite(agency_sqlite_url)
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

        await session.execute(delete(ObjectGroup).where(ObjectGroup.object_id == panel_id))
        await session.execute(delete(Responsible).where(Responsible.object_id == panel_id))

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
            await session.flush()

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


async def sync_events_from_agency_sqlite_archives(
    session: AsyncSession,
    agency_sqlite_url: str,
    *,
    batch_limit: int = 500,
) -> dict[str, Any]:
    cur_date_key, cur_event_id = await get_sqlite_event_cursor(session)
    rows = fetch_archive_events_since_sqlite(
        agency_sqlite_url,
        cursor_date_key=cur_date_key,
        cursor_event_id=cur_event_id,
        limit=batch_limit,
    )
    if not rows:
        return {"status": "ok", "processed": 0, "cursor": f"{cur_date_key}:{cur_event_id}"}

    panel_ids: set[str] = set()
    for r in rows:
        pid = _safe_str(r.get("Panel_id"))
        if pid:
            panel_ids.add(pid)

    objects_by_id: dict[str, Object] = {}
    if panel_ids:
        objs = (await session.execute(select(Object).where(Object.id.in_(list(panel_ids))))).scalars().all()
        objects_by_id = {o.id: o for o in objs}

    events_to_insert: list[dict[str, Any]] = []
    event_pairs: set[tuple[int, int]] = set()
    max_date_key = cur_date_key
    max_event_id = cur_event_id

    for r in rows:
        try:
            date_key = int(r.get("Date_Key"))
            event_id = int(r.get("Event_id"))
        except Exception:
            continue

        max_date_key, max_event_id = (date_key, event_id)
        event_pairs.add((date_key, event_id))

        ts = r.get("TimeEvent")
        if not isinstance(ts, datetime):
            continue

        panel_id = _safe_str(r.get("Panel_id"))
        obj = objects_by_id.get(panel_id) if panel_id else None

        code = _safe_str(r.get("Code"))
        code_text = _safe_str(r.get("CodeText"))
        zone = r.get("Zone")
        line = _safe_str(r.get("Line"))
        result_text = _safe_str(r.get("Result_Text"))

        state_event = r.get("StateEvent")
        state_name = _safe_str(r.get("StateName"))
        state_is_over = r.get("StateIsOverProcess")

        name_state = _safe_str(r.get("NameState"))
        person = _safe_str(r.get("PersonName"))
        gbr = _safe_str(r.get("GrResponseName"))

        desc_parts: list[str] = []
        desc_parts.append(f"Event_id: {event_id}")
        desc_parts.append(f"Date_Key: {date_key}")
        if panel_id:
            desc_parts.append(f"Panel_id: {panel_id}")

        if code:
            if code_text:
                desc_parts.append(f"Код: {code} — {code_text}")
            else:
                desc_parts.append(f"Код: {code}")
        if zone is not None:
            desc_parts.append(f"Зона: {zone}")
        if line:
            desc_parts.append(f"Шлейф: {line}")

        if state_event is not None or state_name:
            st_id = str(state_event) if state_event is not None else ""
            st_label = state_name or name_state or ""
            if st_id and st_label:
                desc_parts.append(f"Статус: {st_label} (StateEvent={st_id})")
            elif st_label:
                desc_parts.append(f"Статус: {st_label}")
            elif st_id:
                desc_parts.append(f"StateEvent: {st_id}")

        if person:
            desc_parts.append(f"Оператор: {person}")
        if gbr:
            desc_parts.append(f"ГБР: {gbr}")
        if result_text:
            desc_parts.append(result_text)

        is_over = bool(state_is_over) if state_is_over is not None else False
        if is_over:
            status = "resolved"
        elif state_event is not None or state_name or name_state:
            status = "pending"
        else:
            status = "active"

        events_to_insert.append(
            {
                "id": f"mssql:{date_key}:{event_id}",
                "timestamp": ts,
                "type": "alarm",
                "object_id": panel_id,
                "object_name": (obj.name if obj and obj.name else None) or panel_id or "Объект",
                "client_name": (obj.client_name if obj and obj.client_name else None) or panel_id or "Не указан",
                "severity": "info",
                "status": status,
                "code": code,
                "code_group": int(r.get("CodeGroup")) if r.get("CodeGroup") is not None else None,
                "code_text": code_text,
                "state_name": state_name,
                "state_is_over_process": bool(state_is_over) if state_is_over is not None else None,
                "description": "\n".join(desc_parts) if desc_parts else "",
                "result_text": result_text,
                "location": (obj.address if obj and obj.address else None),
                "operator_id": person,
            }
        )

    if not events_to_insert:
        return {"status": "ok", "processed": 0, "cursor": f"{cur_date_key}:{cur_event_id}"}

    actions_to_insert: list[dict[str, Any]] = []
    actions_fetched = 0
    if event_pairs:
        try:
            action_rows = fetch_eventservice_actions_for_event_pairs_sqlite(
                agency_sqlite_url,
                event_pairs=list(event_pairs),
            )
            actions_fetched = len(action_rows)
        except Exception:
            logger.exception("Failed to fetch sqlite eventservice actions")
            action_rows = []

        for ar in action_rows:
            try:
                dk = int(ar.get("Date_Key"))
                eid = int(ar.get("Event_id"))
                sid = int(ar.get("Service_id"))
            except Exception:
                continue

            action_name = _safe_str(ar.get("NameState"))
            if not action_name:
                continue

            action_time = _coerce_dt(ar.get("OperationTime"))
            if not isinstance(action_time, datetime):
                continue

            source_table = _eventservice_source_table(dk)
            actions_to_insert.append(
                {
                    "id": _uuid_for_source(source_table, sid),
                    "event_id": f"mssql:{dk}:{eid}",
                    "action_name": action_name,
                    "action_time": action_time,
                    "operator_name": _safe_str(ar.get("PersonName")),
                    "computer": _safe_str(ar.get("Computer")),
                    "gbr_name": _safe_str(ar.get("GrResponseName")),
                    "date_key": dk,
                    "raw_event_id": eid,
                    "source_table": source_table,
                    "source_pk": sid,
                }
            )

    dialect = None
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
    except Exception:
        dialect = None

    result = None
    actions_result = None
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Event).values(events_to_insert).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt)

        if actions_to_insert:
            a_stmt = (
                pg_insert(EventAction)
                .values(actions_to_insert)
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
            actions_result = await session.execute(a_stmt)
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy import bindparam
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        stmt = (
            sqlite_insert(Event)
            .values(
                id=bindparam("id"),
                timestamp=bindparam("timestamp"),
                type=bindparam("type"),
                object_id=bindparam("object_id"),
                object_name=bindparam("object_name"),
                client_name=bindparam("client_name"),
                severity=bindparam("severity"),
                status=bindparam("status"),
                code=bindparam("code"),
                code_group=bindparam("code_group"),
                code_text=bindparam("code_text"),
                state_name=bindparam("state_name"),
                state_is_over_process=bindparam("state_is_over_process"),
                description=bindparam("description"),
                location=bindparam("location"),
                operator_id=bindparam("operator_id"),
            )
            .on_conflict_do_update(
                index_elements=[Event.id],
                set_={
                    "timestamp": sqlite_insert(Event).excluded.timestamp,
                    "type": sqlite_insert(Event).excluded.type,
                    "object_id": sqlite_insert(Event).excluded.object_id,
                    "object_name": sqlite_insert(Event).excluded.object_name,
                    "client_name": sqlite_insert(Event).excluded.client_name,
                    "severity": sqlite_insert(Event).excluded.severity,
                    "status": sqlite_insert(Event).excluded.status,
                    "description": sqlite_insert(Event).excluded.description,
                    "location": sqlite_insert(Event).excluded.location,
                    "operator_id": sqlite_insert(Event).excluded.operator_id,
                    "code": sqlite_insert(Event).excluded.code,
                    "code_group": sqlite_insert(Event).excluded.code_group,
                    "code_text": sqlite_insert(Event).excluded.code_text,
                    "state_name": sqlite_insert(Event).excluded.state_name,
                    "state_is_over_process": sqlite_insert(Event).excluded.state_is_over_process,
                },
            )
        )
        result = await session.execute(stmt, events_to_insert)

        if actions_to_insert:
            a_stmt = (
                sqlite_insert(EventAction)
                .values(
                    id=bindparam("id"),
                    event_id=bindparam("event_id"),
                    action_name=bindparam("action_name"),
                    action_time=bindparam("action_time"),
                    operator_name=bindparam("operator_name"),
                    computer=bindparam("computer"),
                    gbr_name=bindparam("gbr_name"),
                    date_key=bindparam("date_key"),
                    raw_event_id=bindparam("raw_event_id"),
                    source_table=bindparam("source_table"),
                    source_pk=bindparam("source_pk"),
                )
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
            actions_result = await session.execute(a_stmt, actions_to_insert)
    else:
        existing_ids = set(
            (await session.execute(select(Event.id).where(Event.id.in_([r["id"] for r in events_to_insert]))))
            .scalars()
            .all()
        )
        for rr in events_to_insert:
            if rr["id"] in existing_ids:
                continue
            session.add(Event(**rr))

        if actions_to_insert:
            existing_src: set[tuple[str, int]] = set()
            by_table: dict[str, list[int]] = {}
            for r in actions_to_insert:
                by_table.setdefault(r["source_table"], []).append(int(r["source_pk"]))

            for st, pks in by_table.items():
                found = (
                    await session.execute(
                        select(EventAction.source_pk).where(
                            (EventAction.source_table == st) & (EventAction.source_pk.in_(pks))
                        )
                    )
                ).scalars().all()
                for pk in found:
                    existing_src.add((st, int(pk)))

            for r in actions_to_insert:
                key = (r["source_table"], int(r["source_pk"]))
                if key in existing_src:
                    continue
                session.add(EventAction(**r))

    await set_sqlite_event_cursor(session, max_date_key, max_event_id)
    await session.commit()

    inserted = 0
    if result is not None:
        rc = getattr(result, "rowcount", None)
        inserted = len(events_to_insert) if (rc is None or rc < 0) else int(rc)
    else:
        inserted = len(events_to_insert)

    actions_inserted = 0
    if actions_to_insert:
        if actions_result is not None:
            rc = getattr(actions_result, "rowcount", None)
            actions_inserted = len(actions_to_insert) if (rc is None or rc < 0) else int(rc)
        else:
            actions_inserted = len(actions_to_insert)

    return {
        "status": "ok",
        "processed": int(inserted),
        "actionsProcessed": int(actions_inserted),
        "actionsFetched": int(actions_fetched),
        "cursor": f"{max_date_key}:{max_event_id}",
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

    # Try to enrich events with local object snapshot (names/addresses/clients).
    panel_ids: set[str] = set()
    for r in rows:
        pid = _safe_str(r.get("Panel_id"))
        if pid:
            panel_ids.add(pid)

    objects_by_id: dict[str, Object] = {}
    if panel_ids:
        objs = (
            await session.execute(select(Object).where(Object.id.in_(list(panel_ids))))
        ).scalars().all()
        objects_by_id = {o.id: o for o in objs}

    events_to_insert: list[dict[str, Any]] = []
    event_pairs: set[tuple[int, int]] = set()
    max_date_key = cur_date_key
    max_event_id = cur_event_id

    for r in rows:
        try:
            date_key = int(r.get("Date_Key"))
            event_id = int(r.get("Event_id"))
        except Exception:
            continue

        max_date_key, max_event_id = (date_key, event_id)
        event_pairs.add((date_key, event_id))

        ts = r.get("TimeEvent")
        if not isinstance(ts, datetime):
            continue

        panel_id = _safe_str(r.get("Panel_id"))
        obj = objects_by_id.get(panel_id) if panel_id else None

        code = _safe_str(r.get("Code"))
        code_text = _safe_str(r.get("CodeText"))
        zone = r.get("Zone")
        line = _safe_str(r.get("Line"))
        result_text = _safe_str(r.get("Result_Text"))

        state_event = r.get("StateEvent")
        state_name = _safe_str(r.get("StateName"))
        state_is_over = r.get("StateIsOverProcess")

        name_state = _safe_str(r.get("NameState"))
        person = _safe_str(r.get("PersonName"))
        gbr = _safe_str(r.get("GrResponseName"))

        desc_parts: list[str] = []
        # Preserve key archive identifiers for audit/debugging.
        desc_parts.append(f"Event_id: {event_id}")
        desc_parts.append(f"Date_Key: {date_key}")
        if panel_id:
            desc_parts.append(f"Panel_id: {panel_id}")

        if code:
            if code_text:
                desc_parts.append(f"Код: {code} — {code_text}")
            else:
                desc_parts.append(f"Код: {code}")
        if zone is not None:
            desc_parts.append(f"Зона: {zone}")
        if line:
            desc_parts.append(f"Шлейф: {line}")

        if state_event is not None or state_name:
            st_id = str(state_event) if state_event is not None else ""
            st_label = state_name or name_state or ""
            if st_id and st_label:
                desc_parts.append(f"Статус: {st_label} (StateEvent={st_id})")
            elif st_label:
                desc_parts.append(f"Статус: {st_label}")
            elif st_id:
                desc_parts.append(f"StateEvent: {st_id}")

        if person:
            desc_parts.append(f"Оператор: {person}")
        if gbr:
            desc_parts.append(f"ГБР: {gbr}")
        if result_text:
            desc_parts.append(result_text)

        # Map MSSQL StateEvent to UI-friendly statuses.
        # - isOverProcess=1 => resolved
        # - any explicit state => pending
        # - otherwise => active
        is_over = bool(state_is_over) if state_is_over is not None else False
        if is_over:
            status = "resolved"
        elif state_event is not None or state_name or name_state:
            status = "pending"
        else:
            status = "active"

        events_to_insert.append(
            {
                "id": f"mssql:{date_key}:{event_id}",
                "timestamp": ts,
                "type": "alarm",
                "object_id": panel_id,
                "object_name": (obj.name if obj and obj.name else None) or panel_id or "Объект",
                "client_name": (obj.client_name if obj and obj.client_name else None) or panel_id or "Не указан",
                "severity": "info",
                "status": status,
                "code": code,
                "code_group": int(r.get("CodeGroup")) if r.get("CodeGroup") is not None else None,
                "code_text": code_text,
                "state_name": state_name,
                "state_is_over_process": bool(state_is_over) if state_is_over is not None else None,
                "description": "\n".join(desc_parts) if desc_parts else "",
                "result_text": result_text,
                "location": (obj.address if obj and obj.address else None),
                "operator_id": person,
            }
        )

    if not events_to_insert:
        return {"status": "ok", "processed": 0, "cursor": f"{cur_date_key}:{cur_event_id}"}

    actions_to_insert: list[dict[str, Any]] = []
    actions_fetched = 0
    if event_pairs:
        try:
            action_rows = fetch_eventservice_actions_for_event_pairs_mssql(
                agency_mssql_url,
                archives_db_name=archives_db_name,
                event_pairs=list(event_pairs),
            )
            actions_fetched = len(action_rows)
        except Exception:
            logger.exception("Failed to fetch mssql eventservice actions")
            action_rows = []

        for ar in action_rows:
            try:
                dk = int(ar.get("Date_Key"))
                eid = int(ar.get("Event_id"))
                sid = int(ar.get("Service_id"))
            except Exception:
                continue

            action_name = _safe_str(ar.get("NameState"))
            if not action_name:
                continue

            action_time = _coerce_dt(ar.get("OperationTime"))
            if not isinstance(action_time, datetime):
                continue

            source_table = _eventservice_source_table(dk)
            actions_to_insert.append(
                {
                    "id": _uuid_for_source(source_table, sid),
                    "event_id": f"mssql:{dk}:{eid}",
                    "action_name": action_name,
                    "action_time": action_time,
                    "operator_name": _safe_str(ar.get("PersonName")),
                    "computer": _safe_str(ar.get("Computer")),
                    "gbr_name": _safe_str(ar.get("GrResponseName")),
                    "date_key": dk,
                    "raw_event_id": eid,
                    "source_table": source_table,
                    "source_pk": sid,
                }
            )

    dialect = None
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
    except Exception:
        dialect = None

    result = None
    actions_result = None
    if dialect is not None and getattr(dialect, "name", None) == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(Event).values(events_to_insert).on_conflict_do_nothing(index_elements=[Event.id])
        result = await session.execute(stmt)

        if actions_to_insert:
            a_stmt = (
                pg_insert(EventAction)
                .values(actions_to_insert)
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
            actions_result = await session.execute(a_stmt)
    elif dialect is not None and getattr(dialect, "name", None) == "sqlite":
        from sqlalchemy import bindparam
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert

        # For SQLite, avoid generating a single massive VALUES (...) statement
        # which can exceed SQLite's variable limit (~999) for large batches.
        stmt = (
            sqlite_insert(Event)
            .values(
                id=bindparam("id"),
                timestamp=bindparam("timestamp"),
                type=bindparam("type"),
                object_id=bindparam("object_id"),
                object_name=bindparam("object_name"),
                client_name=bindparam("client_name"),
                severity=bindparam("severity"),
                status=bindparam("status"),
                code=bindparam("code"),
                code_group=bindparam("code_group"),
                code_text=bindparam("code_text"),
                state_name=bindparam("state_name"),
                state_is_over_process=bindparam("state_is_over_process"),
                description=bindparam("description"),
                location=bindparam("location"),
                operator_id=bindparam("operator_id"),
            )
            .on_conflict_do_update(
                index_elements=[Event.id],
                set_={
                    "timestamp": sqlite_insert(Event).excluded.timestamp,
                    "type": sqlite_insert(Event).excluded.type,
                    "object_id": sqlite_insert(Event).excluded.object_id,
                    "object_name": sqlite_insert(Event).excluded.object_name,
                    "client_name": sqlite_insert(Event).excluded.client_name,
                    "severity": sqlite_insert(Event).excluded.severity,
                    "status": sqlite_insert(Event).excluded.status,
                    "description": sqlite_insert(Event).excluded.description,
                    "location": sqlite_insert(Event).excluded.location,
                    "operator_id": sqlite_insert(Event).excluded.operator_id,
                    "code": sqlite_insert(Event).excluded.code,
                    "code_group": sqlite_insert(Event).excluded.code_group,
                    "code_text": sqlite_insert(Event).excluded.code_text,
                    "state_name": sqlite_insert(Event).excluded.state_name,
                    "state_is_over_process": sqlite_insert(Event).excluded.state_is_over_process,
                },
            )
        )
        result = await session.execute(stmt, events_to_insert)

        if actions_to_insert:
            a_stmt = (
                sqlite_insert(EventAction)
                .values(
                    id=bindparam("id"),
                    event_id=bindparam("event_id"),
                    action_name=bindparam("action_name"),
                    action_time=bindparam("action_time"),
                    operator_name=bindparam("operator_name"),
                    computer=bindparam("computer"),
                    gbr_name=bindparam("gbr_name"),
                    date_key=bindparam("date_key"),
                    raw_event_id=bindparam("raw_event_id"),
                    source_table=bindparam("source_table"),
                    source_pk=bindparam("source_pk"),
                )
                .on_conflict_do_nothing(index_elements=["source_table", "source_pk"])
            )
            actions_result = await session.execute(a_stmt, actions_to_insert)
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

        if actions_to_insert:
            existing_src: set[tuple[str, int]] = set()
            by_table: dict[str, list[int]] = {}
            for r in actions_to_insert:
                by_table.setdefault(r["source_table"], []).append(int(r["source_pk"]))

            for st, pks in by_table.items():
                found = (
                    await session.execute(
                        select(EventAction.source_pk).where(
                            (EventAction.source_table == st) & (EventAction.source_pk.in_(pks))
                        )
                    )
                ).scalars().all()
                for pk in found:
                    existing_src.add((st, int(pk)))

            for r in actions_to_insert:
                key = (r["source_table"], int(r["source_pk"]))
                if key in existing_src:
                    continue
                session.add(EventAction(**r))

    await set_mssql_event_cursor(session, max_date_key, max_event_id)
    await session.commit()

    inserted = 0
    if result is not None:
        rc = getattr(result, "rowcount", None)
        inserted = len(events_to_insert) if (rc is None or rc < 0) else int(rc)
    else:
        inserted = len(events_to_insert)

    actions_inserted = 0
    if actions_to_insert:
        if actions_result is not None:
            rc = getattr(actions_result, "rowcount", None)
            actions_inserted = len(actions_to_insert) if (rc is None or rc < 0) else int(rc)
        else:
            actions_inserted = len(actions_to_insert)

    return {
        "status": "ok",
        "processed": int(inserted),
        "actionsProcessed": int(actions_inserted),
        "actionsFetched": int(actions_fetched),
        "cursor": f"{max_date_key}:{max_event_id}",
    }
