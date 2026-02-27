from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.responses import StreamingResponse
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.integrations.agency_mssql import (
    fetch_eventservice_actions_for_event_pairs as fetch_eventservice_actions_for_event_pairs_mssql,
)
from app.integrations.agency_sqlite import (
    fetch_eventservice_actions_for_event_pairs as fetch_eventservice_actions_for_event_pairs_sqlite,
)
from app.models.event import Event
from app.models.event_action import EventAction

router = APIRouter(prefix="/events")


def _is_operator_handled_predicate() -> Any:
    """Heuristic: event is handled by an operator (not purely system)."""

    # Historically we relied on Event.operator_id being filled for operator-handled alarms.
    # This is more robust than joining actions: some deployments may not have event_actions
    # synced yet, or IDs may not match during migration.
    return and_(Event.operator_id.is_not(None), Event.operator_id != "")


def _accept_action_predicate() -> Any:
    """Best-effort match for operator action: accepted for processing."""

    # In agency logs this can vary a bit; we match by substrings.
    return or_(
        EventAction.action_name == "Прием на обработку",
        EventAction.action_name.ilike("%прин%в обработ%"),
        EventAction.action_name.ilike("%прием%обработ%"),
    )


def _accepted_action_exists() -> Any:
    return exists(
        select(1)
        .select_from(EventAction)
        .where(EventAction.event_id == Event.id)
        .where(EventAction.operator_name.is_not(None))
        .where(EventAction.operator_name != "")
        .where(_accept_action_predicate())
    )


def _csv_bytes_to_xlsx_bytes(content: bytes) -> bytes:
    from openpyxl import Workbook

    text = content.decode("utf-8-sig", errors="replace")
    wb = Workbook()
    ws = wb.active
    ws.title = "data"

    reader = csv.reader(io.StringIO(text), delimiter=";")
    for row in reader:
        ws.append(list(row))

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _event_to_out(e: Event) -> dict[str, Any]:
    return {
        "id": e.id,
        "timestamp": e.timestamp.isoformat(),
        "type": e.type,
        "objectId": e.object_id,
        "objectName": e.object_name,
        "clientName": e.client_name,
        "severity": e.severity,
        "status": e.status,
        "code": getattr(e, "code", None),
        "codeText": getattr(e, "code_text", None),
        "stateName": getattr(e, "state_name", None),
        "resultText": getattr(e, "result_text", None),
        "meterCount": getattr(e, "meter_count", None),
        "timeMeterCount": (
            getattr(e, "time_meter_count", None).isoformat()
            if getattr(e, "time_meter_count", None) is not None
            else None
        ),
        "description": e.description,
        "location": e.location,
        "operatorId": e.operator_id,
    }


def _action_to_out(a: EventAction) -> dict[str, Any]:
    return {
        "actionName": a.action_name,
        "actionTime": a.action_time.isoformat(),
        "operatorName": a.operator_name,
        "computer": a.computer,
        "gbrName": a.gbr_name,
        "dateKey": a.date_key,
        "rawEventId": a.raw_event_id,
        "sourceTable": a.source_table,
        "sourcePk": a.source_pk,
    }


def _parse_agency_event_key(event_id: str) -> tuple[int, int] | None:
    parts = str(event_id).split(":")
    if len(parts) < 3:
        return None
    try:
        date_key = int(parts[-2])
        raw_event_id = int(parts[-1])
    except Exception:
        return None
    return (date_key, raw_event_id)


def _eventservice_source_table(date_key: int) -> str:
    s = str(int(date_key))
    if len(s) != 8:
        suffix = s[:6] + "01"
    else:
        suffix = s[:6] + "01"
    return f"eventservice{suffix}"


def _coerce_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


def _action_row_to_out(row: dict[str, Any]) -> dict[str, Any] | None:
    action_name = str(row.get("NameState") or "").strip()
    if not action_name:
        return None

    action_time = _coerce_dt(row.get("OperationTime"))
    if action_time is None:
        return None

    try:
        date_key = int(row.get("Date_Key"))
        raw_event_id = int(row.get("Event_id"))
        source_pk = int(row.get("Service_id"))
    except Exception:
        return None

    return {
        "actionName": action_name,
        "actionTime": action_time.isoformat(),
        "operatorName": str(row.get("PersonName") or "").strip() or None,
        "computer": str(row.get("Computer") or "").strip() or None,
        "gbrName": str(row.get("GrResponseName") or "").strip() or None,
        "dateKey": date_key,
        "rawEventId": raw_event_id,
        "sourceTable": _eventservice_source_table(date_key),
        "sourcePk": source_pk,
    }


@router.get("/{event_id}")
async def get_event_details(
    event_id: str,
    actionsLimit: int = Query(500, ge=0, le=5000),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    e = await session.get(Event, event_id)
    if not e:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Event not found"})

    actions: list[EventAction] = []
    if actionsLimit > 0:
        stmt: Select[tuple[EventAction]] = (
            select(EventAction)
            .where(EventAction.event_id == event_id)
            .order_by(EventAction.action_time.asc())
            .limit(actionsLimit)
        )
        actions = (await session.execute(stmt)).scalars().all()

    # Best-effort fallback: if actions are not synced into SVOD DB yet,
    # try to fetch them directly from the agency DB by (Date_Key, Event_id).
    if actionsLimit > 0 and not actions and settings.agency_database_url:
        key = _parse_agency_event_key(event_id)
        if key is not None:
            url = settings.agency_database_url
            scheme = (url.split(":", 1)[0] or "").lower()
            try:
                if scheme.startswith("sqlite"):
                    rows = await asyncio.to_thread(
                        fetch_eventservice_actions_for_event_pairs_sqlite,
                        url,
                        event_pairs=[key],
                    )
                elif scheme.startswith("mssql"):
                    rows = await asyncio.to_thread(
                        fetch_eventservice_actions_for_event_pairs_mssql,
                        url,
                        archives_db_name=settings.agency_archives_db_name,
                        event_pairs=[key],
                    )
                else:
                    rows = []
            except Exception:
                rows = []

            out_rows: list[dict[str, Any]] = []
            for r in rows[:actionsLimit]:
                mapped = _action_row_to_out(r)
                if mapped is not None:
                    out_rows.append(mapped)

            if out_rows:
                return {"event": _event_to_out(e), "actions": out_rows}

    return {"event": _event_to_out(e), "actions": [_action_to_out(a) for a in actions]}


@router.get("")
async def list_events(
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=500),
    dateFrom: str | None = None,
    dateTo: str | None = None,
    type: str | None = None,  # noqa: A002
    objectId: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    includeNoise: bool = Query(False, description="Include access/noise events (arming/disarming, etc.)"),
    includeSystem: bool = Query(False, description="Include system-handled events (no operator)"),
    includeCancelled: bool = Query(False, description="Include cancelled events"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filters: list[Any] = []

    # UI requirement: hide operator-irrelevant noise (e.g., постановка/снятие).
    # These are classified as type=access during agency archive sync.
    if not includeNoise:
        filters.append(Event.type != "access")

    # UI requirement: hide cancelled by default.
    if not includeCancelled:
        filters.append(Event.status != "cancelled")

    # UI requirement: hide system-handled alarms by default.
    # Convention for "real handled alarms": there is an operator action
    # "accepted for processing" (eventservice) OR Event.operator_id is set.
    if not includeSystem:
        actions_present = (
            (await session.execute(select(EventAction.id).limit(1))).scalar_one_or_none() is not None
        )
        if actions_present:
            handled_alarm = or_(_is_operator_handled_predicate(), _accepted_action_exists())
            filters.append(or_(Event.type != "alarm", handled_alarm))
        # else: fail-open (actions not synced) -> don't hide alarms

    if type:
        filters.append(Event.type == type)
    if objectId:
        filters.append(Event.object_id == objectId)
    if severity:
        filters.append(Event.severity == severity)
    if status:
        filters.append(Event.status == status)

    # Default UI behavior: if user didn't set any filters, show only recent events.
    # This prevents slow queries when the DB contains millions of rows.
    if (
        not dateFrom
        and not dateTo
        and not type
        and not objectId
        and not severity
        and not status
        and not (search and search.strip())
        and int(settings.ui_events_default_lookback_hours) > 0
    ):
        dt_from = datetime.utcnow() - timedelta(hours=int(settings.ui_events_default_lookback_hours))
        filters.append(Event.timestamp >= dt_from)

    if dateFrom:
        dt_from = _parse_dt(dateFrom)
        if dt_from:
            filters.append(Event.timestamp >= dt_from)
    if dateTo:
        dt_to = _parse_dt(dateTo)
        if dt_to:
            filters.append(Event.timestamp <= dt_to)

    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(
            or_(
                Event.description.ilike(needle),
                Event.object_name.ilike(needle),
                Event.client_name.ilike(needle),
                Event.location.ilike(needle),
            )
        )

    where = and_(*filters) if filters else None

    count_stmt = select(func.count()).select_from(Event)
    if where is not None:
        count_stmt = count_stmt.where(where)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt: Select[tuple[Event]] = select(Event).order_by(Event.timestamp.desc())
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)

    rows = (await session.execute(stmt)).scalars().all()
    page_items = [_event_to_out(e) for e in rows]
    total_pages = (total + pageSize - 1) // pageSize if pageSize else 1

    return {
        "data": page_items,
        "total": total,
        "page": page,
        "pageSize": pageSize,
        "totalPages": total_pages,
    }


@router.get("/export")
async def export_events_export(
    dateFrom: str | None = None,
    dateTo: str | None = None,
    type: str | None = None,  # noqa: A002
    objectId: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    includeNoise: bool = Query(False, description="Include access/noise events (arming/disarming, etc.)"),
    includeSystem: bool = Query(False, description="Include system-handled events (no operator)"),
    includeCancelled: bool = Query(False, description="Include cancelled events"),
    limit: int = Query(50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    filters: list[Any] = []

    if not includeNoise:
        filters.append(Event.type != "access")

    if not includeCancelled:
        filters.append(Event.status != "cancelled")

    if not includeSystem:
        actions_present = (
            (await session.execute(select(EventAction.id).limit(1))).scalar_one_or_none() is not None
        )
        if actions_present:
            handled_alarm = or_(_is_operator_handled_predicate(), _accepted_action_exists())
            filters.append(or_(Event.type != "alarm", handled_alarm))

    if type:
        filters.append(Event.type == type)
    if objectId:
        filters.append(Event.object_id == objectId)
    if severity:
        filters.append(Event.severity == severity)
    if status:
        filters.append(Event.status == status)

    if dateFrom:
        dt_from = _parse_dt(dateFrom)
        if dt_from:
            filters.append(Event.timestamp >= dt_from)
    if dateTo:
        dt_to = _parse_dt(dateTo)
        if dt_to:
            filters.append(Event.timestamp <= dt_to)

    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(
            or_(
                Event.description.ilike(needle),
                Event.object_name.ilike(needle),
                Event.client_name.ilike(needle),
                Event.location.ilike(needle),
            )
        )

    where = and_(*filters) if filters else None

    stmt: Select[tuple[Event]] = select(Event).order_by(Event.timestamp.desc()).limit(limit)
    if where is not None:
        stmt = stmt.where(where)
    rows = (await session.execute(stmt)).scalars().all()

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "События"

    def _agency_event_id(event_id: str | None) -> str:
        if not event_id:
            return ""
        parts = str(event_id).split(":")
        if len(parts) >= 3:
            return parts[-1] or ""
        return ""

    headers = [
        "ID (SVOD)",
        "ID события (аг.)",
        "Дата/время",
        "Тип",
        "Номер объекта",
        "Название объекта",
        "Контрагент",
        "Код",
        "Расшифровка кода",
        "Статус (агентство)",
        "Важность",
        "Статус",
        "Адрес",
        "Параметр (MeterCount)",
        "Время параметра (TimeMeterCount)",
        "Пометка (Result_Text)",
        "Описание",
    ]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for e in rows:
        ws.append(
            [
                e.id,
                _agency_event_id(e.id),
                e.timestamp.isoformat(),
                e.type,
                e.object_id or "",
                e.object_name,
                e.client_name,
                getattr(e, "code", "") or "",
                getattr(e, "code_text", "") or "",
                getattr(e, "state_name", "") or "",
                e.severity,
                e.status,
                e.location or "",
                getattr(e, "meter_count", "") or "",
                (
                    getattr(e, "time_meter_count", None).isoformat()
                    if getattr(e, "time_meter_count", None) is not None
                    else ""
                ),
                getattr(e, "result_text", "") or "",
                (e.description or "").replace("\r\n", "\n"),
            ]
        )

    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 20
    ws.column_dimensions["D"].width = 12
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 40
    ws.column_dimensions["G"].width = 30
    ws.column_dimensions["H"].width = 10
    ws.column_dimensions["I"].width = 40
    ws.column_dimensions["J"].width = 22
    ws.column_dimensions["K"].width = 10
    ws.column_dimensions["L"].width = 12
    ws.column_dimensions["M"].width = 40
    ws.column_dimensions["N"].width = 40
    ws.column_dimensions["O"].width = 22
    ws.column_dimensions["P"].width = 22
    ws.column_dimensions["Q"].width = 40
    ws.column_dimensions["R"].width = 80

    xlsx = io.BytesIO()
    wb.save(xlsx)

    filename = f"events-export-{datetime.utcnow().date().isoformat()}.xlsx"
    return Response(
        content=xlsx.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/xlsx")
async def export_events_xlsx(
    dateFrom: str | None = None,
    dateTo: str | None = None,
    type: str | None = None,  # noqa: A002
    objectId: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    search: str | None = None,
    includeNoise: bool = Query(False, description="Include access/noise events (arming/disarming, etc.)"),
    includeSystem: bool = Query(False, description="Include system-handled events (no operator)"),
    includeCancelled: bool = Query(False, description="Include cancelled events"),
    limit: int = Query(50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    return await export_events_export(
        dateFrom=dateFrom,
        dateTo=dateTo,
        type=type,
        objectId=objectId,
        severity=severity,
        status=status,
        search=search,
        includeNoise=includeNoise,
        includeSystem=includeSystem,
        includeCancelled=includeCancelled,
        limit=limit,
        session=session,
    )


@router.get("/stream")
async def stream_events(
    since: str | None = Query(None, description="ISO timestamp; stream events newer than this"),
    pollSeconds: float = Query(1.0, ge=0.2, le=10.0),
    includeNoise: bool = Query(False, description="Include access/noise events (arming/disarming, etc.)"),
    includeSystem: bool = Query(False, description="Include system-handled events (no operator)"),
    includeCancelled: bool = Query(False, description="Include cancelled events"),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
):
    """Server-Sent Events stream for new events.

    This is intentionally simple: it polls SQLite/Postgres for new rows.
    Works well for local/SQLite and small-to-medium throughput.
    """

    last_ts = _parse_dt(since) if since else datetime.utcnow()
    keepalive_every = 15.0

    actions_present = True
    if not includeSystem:
        try:
            actions_present = (
                (await session.execute(select(EventAction.id).limit(1))).scalar_one_or_none() is not None
            )
        except Exception:
            actions_present = True

    async def gen():
        nonlocal last_ts
        last_keepalive = asyncio.get_event_loop().time()

        # Initial hello event helps clients validate connection quickly.
        yield b"event: hello\n"
        yield f"data: {json.dumps({'serverTime': datetime.utcnow().isoformat()})}\n\n".encode("utf-8")

        while True:
            # Query a small batch; client can keep connection open.
            stmt: Select[tuple[Event]] = select(Event).where(Event.timestamp > last_ts)
            if not includeNoise:
                stmt = stmt.where(Event.type != "access")
            if not includeCancelled:
                stmt = stmt.where(Event.status != "cancelled")
            if not includeSystem:
                if actions_present:
                    handled_alarm = or_(_is_operator_handled_predicate(), _accepted_action_exists())
                    stmt = stmt.where(or_(Event.type != "alarm", handled_alarm))
            stmt = stmt.order_by(Event.timestamp.asc()).limit(500)
            rows = (await session.execute(stmt)).scalars().all()
            for e in rows:
                payload = _event_to_out(e)
                last_ts = max(last_ts, e.timestamp)
                yield b"event: event\n"
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

            now = asyncio.get_event_loop().time()
            if now - last_keepalive >= keepalive_every:
                last_keepalive = now
                yield b": keep-alive\n\n"

            await asyncio.sleep(pollSeconds)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{event_id}")
async def get_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    e = await session.get(Event, event_id)
    if e:
        return _event_to_out(e)
    raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Event not found"})
