from __future__ import annotations

from datetime import datetime
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, case, func, or_, select

from app.db.session import get_session
from app.services.report_service import export_daily_report_csv, today_str
from app.models.event import Event
from app.models.object import Object

router = APIRouter(prefix="/reports")


def _parse_dt(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _parse_date(value: str) -> date_type | None:
    try:
        return date_type.fromisoformat(value)
    except Exception:
        return None


@router.get("")
async def list_reports(session: AsyncSession = Depends(get_session)) -> list[dict]:
    # Build "daily" reports from real events (last 30 days)
    rows = (
        await session.execute(
            select(
                func.date(Event.timestamp).label("day"),
                func.count().label("events_count"),
                func.sum(case((Event.severity == "critical", 1), else_=0)).label("critical_count"),
            )
            .group_by(func.date(Event.timestamp))
            .order_by(func.date(Event.timestamp).desc())
            .limit(30)
        )
    ).all()

    out: list[dict] = []
    for day, events_count, critical_count in rows:
        if isinstance(day, date_type):
            day_str = day.isoformat()
        else:
            day_str = str(day)
        out.append(
            {
                "id": day_str,
                "type": "daily",
                "periodStart": day_str,
                "periodEnd": day_str,
                "generatedAt": "",
                "status": "generated",
                "eventsCount": int(events_count or 0),
                "criticalCount": int(critical_count or 0),
            }
        )
    return out


@router.get("/export/daily")
async def export_daily(
    date: str = Query(default_factory=today_str, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    content = await export_daily_report_csv(session=session, date=date)
    filename = f"daily-report-{date}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/phrase-counts")
async def export_phrase_counts(
    # Filters
    year: int | None = Query(default=None, ge=1970, le=2100, description="Год, например 2025"),
    dateFrom: str | None = Query(default=None, description="ISO datetime, например 2025-01-01T00:00:00"),
    dateTo: str | None = Query(default=None, description="ISO datetime, например 2025-12-31T23:59:59"),
    clientName: str | None = Query(default=None, description="Контрагент/клиент (поиск по подстроке)"),
    # What to count
    phraseA: str = Query(default="Снятие не по расписанию", min_length=1),
    phraseB: str = Query(default="Объект не поставлен под охрану по расписанию", min_length=1),
    # Output
    limit: int = Query(default=50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Экспорт агрегированного отчёта (по объектам) по двум ключевым фразам.

    Нужен для периодических запросов вида:
    - за год N по контрагенту X: сколько было событий типа A и B.
    """
    dt_from: datetime | None = None
    dt_to: datetime | None = None

    if year is not None:
        dt_from = datetime(year, 1, 1, 0, 0, 0)
        dt_to = datetime(year, 12, 31, 23, 59, 59, 999999)

    if dateFrom:
        parsed = _parse_dt(dateFrom)
        if parsed:
            dt_from = parsed
    if dateTo:
        parsed = _parse_dt(dateTo)
        if parsed:
            dt_to = parsed

    filters: list[object] = []
    if dt_from is not None:
        filters.append(Event.timestamp >= dt_from)
    if dt_to is not None:
        filters.append(Event.timestamp <= dt_to)

    client = (clientName or "").strip()
    if client:
        needle = f"%{client}%"
        filters.append(or_(Object.client_name.ilike(needle), Event.client_name.ilike(needle)))

    # Only keep rows that match at least one phrase (for performance + relevance)
    p_a = f"%{phraseA.strip()}%"
    p_b = f"%{phraseB.strip()}%"

    where = and_(*filters) if filters else None

    # Prefer objects snapshot for better names/addresses when event has only object_id.
    obj_name = func.coalesce(Object.name, Event.object_name)
    obj_addr = func.coalesce(Object.address, Event.location)

    a_count = func.sum(case((or_(Event.description.ilike(p_a), Event.code_text.ilike(p_a)), 1), else_=0))
    b_count = func.sum(case((or_(Event.description.ilike(p_b), Event.code_text.ilike(p_b)), 1), else_=0))

    stmt = (
        select(
            Event.object_id.label("object_id"),
            obj_name.label("object_name"),
            obj_addr.label("address"),
            a_count.label("phrase_a_count"),
            b_count.label("phrase_b_count"),
        )
        .select_from(Event)
        .outerjoin(Object, Object.id == Event.object_id)
        .group_by(Event.object_id, Object.name, Event.object_name, Object.address, Event.location)
        .having(or_(a_count > 0, b_count > 0))
        .order_by(obj_name.asc())
        .limit(limit)
    )
    if where is not None:
        stmt = stmt.where(where)

    rows = (await session.execute(stmt)).all()

    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "object_id",
            "object_name",
            "address",
            phraseA,
            phraseB,
            "примечание",
        ]
    )

    for object_id, object_name, address, c_a, c_b in rows:
        writer.writerow(
            [
                object_id or "",
                object_name or "",
                address or "",
                int(c_a or 0),
                int(c_b or 0),
                "",
            ]
        )

    # Use UTF-8 with BOM for Excel compatibility
    content = buf.getvalue().encode("utf-8-sig")
    y = str(year) if year is not None else "custom"
    safe_client = client.replace('"', "").replace("'", "").strip() or "all"
    filename = f"phrase-counts-{y}-{safe_client}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/event-codes")
async def list_event_codes(
    query: str | None = Query(default=None, description="Поиск по коду или расшифровке"),
    limit: int = Query(default=100, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Справочник кодов событий для UI.

    Возвращает коды, которые реально встречаются в локальной таблице events,
    чтобы UI мог выбирать по коду (например E1001), показывая расшифровку.
    """
    q = (query or "").strip()

    stmt = (
        select(
            Event.code.label("code"),
            func.max(Event.code_text).label("codeText"),
            func.count().label("count"),
        )
        .where(Event.code.isnot(None))
        .group_by(Event.code)
        .order_by(func.count().desc())
        .limit(limit)
    )

    if q:
        needle = f"%{q}%"
        stmt = stmt.where(or_(Event.code.ilike(needle), Event.code_text.ilike(needle)))

    rows = (await session.execute(stmt)).all()
    return [
        {
            "code": code,
            "codeText": code_text,
            "count": int(count or 0),
        }
        for code, code_text, count in rows
        if code
    ]


@router.get("/export/objects-by-code")
async def export_objects_by_code(
    eventCode: str = Query(min_length=1, max_length=16, description="Код события, например E1001"),
    dateFrom: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    dateTo: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    year: int | None = Query(default=None, ge=1970, le=2100, description="Год (если указан — задаёт период)"),
    clientName: str | None = Query(default=None, description="Контрагент/клиент (поиск по подстроке)"),
    objectQuery: str | None = Query(default=None, description="Поиск по объекту/адресу/ID"),
    limit: int = Query(default=50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Экспорт CSV: по выбранному коду события — сколько раз и по каким объектам за период."""
    dt_from: datetime | None = None
    dt_to: datetime | None = None

    if year is not None:
        dt_from = datetime(year, 1, 1, 0, 0, 0)
        dt_to = datetime(year, 12, 31, 23, 59, 59, 999999)

    if dateFrom:
        parsed = _parse_dt(dateFrom) or (
            datetime.combine(_parse_date(dateFrom), datetime.min.time()) if _parse_date(dateFrom) else None
        )
        if parsed:
            dt_from = parsed
    if dateTo:
        parsed = _parse_dt(dateTo) or (
            datetime.combine(_parse_date(dateTo), datetime.max.time()) if _parse_date(dateTo) else None
        )
        if parsed:
            dt_to = parsed

    filters: list[object] = [Event.code == eventCode]
    if dt_from is not None:
        filters.append(Event.timestamp >= dt_from)
    if dt_to is not None:
        filters.append(Event.timestamp <= dt_to)

    client = (clientName or "").strip()
    if client:
        needle = f"%{client}%"
        filters.append(or_(Object.client_name.ilike(needle), Event.client_name.ilike(needle)))

    obj_q = (objectQuery or "").strip()
    if obj_q:
        needle = f"%{obj_q}%"
        obj_name = func.coalesce(Object.name, Event.object_name)
        obj_addr = func.coalesce(Object.address, Event.location)
        filters.append(
            or_(
                obj_name.ilike(needle),
                obj_addr.ilike(needle),
                Event.object_id.ilike(needle),
            )
        )

    where = and_(*filters)

    obj_name = func.coalesce(Object.name, Event.object_name)
    obj_addr = func.coalesce(Object.address, Event.location)

    stmt = (
        select(
            Event.object_id.label("object_id"),
            obj_name.label("object_name"),
            obj_addr.label("address"),
            func.count().label("events_count"),
            func.min(Event.timestamp).label("first_time"),
            func.max(Event.timestamp).label("last_time"),
        )
        .select_from(Event)
        .outerjoin(Object, Object.id == Event.object_id)
        .where(where)
        .group_by(Event.object_id, Object.name, Event.object_name, Object.address, Event.location)
        .order_by(obj_name.asc())
        .limit(limit)
    )

    rows = (await session.execute(stmt)).all()

    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(
        [
            "event_code",
            "object_id",
            "object_name",
            "address",
            "events_count",
            "first_time",
            "last_time",
            "note",
        ]
    )

    for object_id, object_name, address, events_count, first_time, last_time in rows:
        writer.writerow(
            [
                eventCode,
                object_id or "",
                object_name or "",
                address or "",
                int(events_count or 0),
                first_time.isoformat() if first_time else "",
                last_time.isoformat() if last_time else "",
                "",
            ]
        )

    content = buf.getvalue().encode("utf-8-sig")
    safe_code = eventCode.replace("/", "_").replace("\\", "_")
    filename = f"objects-by-code-{safe_code}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
