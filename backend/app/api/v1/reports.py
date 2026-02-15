from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from datetime import datetime
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, case, func, or_, select

from app.api.v1.deps import get_current_user
from app.db.session import get_session
from app.services.report_service import export_daily_report_csv, today_str
from app.models.event import Event
from app.models.object import Object
from app.models.report import Report

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


def _backend_root_dir() -> Path:
    # backend/app/api/v1/reports.py -> parents[3] == backend/
    return Path(__file__).resolve().parents[3]


def _reports_store_dir() -> Path:
    return _backend_root_dir() / "reports_store"


def _write_report_file(report_id: str, filename: str, content: bytes) -> Path:
    store = _reports_store_dir()
    store.mkdir(parents=True, exist_ok=True)
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = store / f"{report_id}-{safe_name}"
    path.write_bytes(content)
    return path


def _as_report_out_dict(r: Report) -> dict:
    d = {
        "id": str(r.id),
        "type": str(r.type),
        "periodStart": str(r.period_start),
        "periodEnd": str(r.period_end),
        "generatedAt": str(r.generated_at or ""),
        "status": str(r.status),
        "eventsCount": int(r.events_count or 0),
        "criticalCount": int(r.critical_count or 0),
        "downloadUrl": None,
        "fileName": r.file_name,
        "mimeType": r.mime_type,
    }
    if r.storage_path:
        d["downloadUrl"] = f"/reports/{r.id}/download"
    return d


@router.get("")
async def list_reports(
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> list[dict]:
    # 1) Stored reports (history)
    stored = (
        await session.execute(
            select(Report)
            .order_by(Report.generated_at.desc())
            .limit(200)
        )
    ).scalars().all()

    out: list[dict] = [_as_report_out_dict(r) for r in stored]

    # 2) Derived "daily" reports from real events (last 30 days)
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
                "downloadUrl": f"/reports/export/daily?date={day_str}",
                "fileName": f"daily-report-{day_str}.csv",
                "mimeType": "text/csv; charset=utf-8",
            }
        )
    return out


@router.post("/generate/daily")
async def generate_daily_report(
    date: str = Query(default_factory=today_str, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> dict:
    # Generate now, but return a record and keep it in history.
    day = _parse_date(date)
    if not day:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date"})

    report_id = str(uuid4())
    r = Report(
        id=report_id,
        type="daily",
        period_start=day.isoformat(),
        period_end=day.isoformat(),
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="pending",
        events_count=0,
        critical_count=0,
        file_name=None,
        mime_type=None,
        storage_path=None,
        params_json=json.dumps({"date": day.isoformat()}, ensure_ascii=False),
        error_message=None,
    )
    session.add(r)
    await session.commit()

    try:
        content = await export_daily_report_csv(session=session, date=day.isoformat())
        filename = f"daily-report-{day.isoformat()}.csv"
        path = _write_report_file(report_id, filename, content)

        # fill counts
        dt_from = datetime.combine(day, datetime.min.time())
        dt_to = datetime.combine(day, datetime.max.time())
        counts = (
            await session.execute(
                select(
                    func.count().label("events_count"),
                    func.sum(case((Event.severity == "critical", 1), else_=0)).label("critical_count"),
                ).where(Event.timestamp >= dt_from, Event.timestamp <= dt_to)
            )
        ).first()
        events_count = int((counts[0] if counts else 0) or 0)
        critical_count = int((counts[1] if counts else 0) or 0)

        r.status = "generated"
        r.file_name = filename
        r.mime_type = "text/csv; charset=utf-8"
        r.storage_path = str(path)
        r.events_count = events_count
        r.critical_count = critical_count
        r.generated_at = datetime.utcnow().isoformat(timespec="seconds")
        await session.commit()
    except Exception as e:
        r.status = "failed"
        r.error_message = str(e)
        await session.commit()

    return _as_report_out_dict(r)


@router.post("/generate/objects-by-code")
async def generate_objects_by_code_report(
    eventCode: str = Query(min_length=1, max_length=16, description="Код события, например E1001"),
    dateFrom: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    dateTo: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    year: int | None = Query(default=None, ge=1970, le=2100, description="Год (если указан — задаёт период)"),
    clientName: str | None = Query(default=None, description="Контрагент/клиент (поиск по подстроке)"),
    objectQuery: str | None = Query(default=None, description="Поиск по объекту/адресу/ID"),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> dict:
    # Generate CSV now and store.
    # Reuse logic from export_objects_by_code but produce bytes.
    dt_from: datetime | None = None
    dt_to: datetime | None = None

    if year is not None:
        dt_from = datetime(year, 1, 1, 0, 0, 0)
        dt_to = datetime(year, 12, 31, 23, 59, 59, 999999)

    if dateFrom:
        parsed_dt = _parse_dt(dateFrom)
        parsed_d = _parse_date(dateFrom)
        if parsed_dt:
            dt_from = parsed_dt
        elif parsed_d:
            dt_from = datetime.combine(parsed_d, datetime.min.time())
    if dateTo:
        parsed_dt = _parse_dt(dateTo)
        parsed_d = _parse_date(dateTo)
        if parsed_dt:
            dt_to = parsed_dt
        elif parsed_d:
            dt_to = datetime.combine(parsed_d, datetime.max.time())

    filters: list[object] = [Event.code == eventCode.strip()]
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
        filters.append(
            or_(
                Event.object_id.ilike(needle),
                Object.name.ilike(needle),
                Object.address.ilike(needle),
                Event.object_name.ilike(needle),
                Event.location.ilike(needle),
            )
        )

    obj_name = func.coalesce(Object.name, Event.object_name)
    obj_addr = func.coalesce(Object.address, Event.location)

    stmt = (
        select(
            Event.object_id.label("object_id"),
            obj_name.label("object_name"),
            obj_addr.label("address"),
            func.count().label("events"),
        )
        .select_from(Event)
        .outerjoin(Object, Object.id == Event.object_id)
        .where(and_(*filters))
        .group_by(Event.object_id, Object.name, Event.object_name, Object.address, Event.location)
        .order_by(func.count().desc())
        .limit(200000)
    )

    rows = (await session.execute(stmt)).all()

    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(["object_id", "object_name", "address", "events", "event_code", "event_code_text"])

    # best-effort: take one code_text for code
    code_text = (
        await session.execute(select(func.max(Event.code_text)).where(Event.code == eventCode.strip()))
    ).scalar_one_or_none()

    for object_id, object_name, address, c in rows:
        writer.writerow(
            [
                object_id or "",
                object_name or "",
                address or "",
                int(c or 0),
                eventCode.strip(),
                code_text or "",
            ]
        )

    content = buf.getvalue().encode("utf-8-sig")

    # Determine period strings for list
    ps = (dt_from.date().isoformat() if dt_from else (str(year) if year else ""))
    pe = (dt_to.date().isoformat() if dt_to else (str(year) if year else ""))
    if not ps:
        ps = date_type.today().isoformat()
    if not pe:
        pe = ps

    report_id = str(uuid4())
    filename = f"objects-by-code-{eventCode.strip()}-{ps}-{pe}.csv"
    path = _write_report_file(report_id, filename, content)

    r = Report(
        id=report_id,
        type="objectsByCode",
        period_start=ps,
        period_end=pe,
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="generated",
        events_count=sum(int(x[3] or 0) for x in rows) if rows else 0,
        critical_count=0,
        file_name=filename,
        mime_type="text/csv; charset=utf-8",
        storage_path=str(path),
        params_json=json.dumps(
            {
                "eventCode": eventCode.strip(),
                "dateFrom": dateFrom,
                "dateTo": dateTo,
                "year": year,
                "clientName": clientName,
                "objectQuery": objectQuery,
            },
            ensure_ascii=False,
        ),
        error_message=None,
    )
    session.add(r)
    await session.commit()
    return _as_report_out_dict(r)


@router.post("/generate/gbr-raport-xlsx")
async def generate_gbr_raport_xlsx(
    dateFrom: str = Query(description="ISO datetime"),
    dateTo: str = Query(description="ISO datetime"),
    gbrName: str | None = Query(default=None),
    objectId: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> dict:
    # Permission gate
    have = set(map(str, current.get("permissions") or []))
    if "analytics:read" not in have and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Missing permissions"})

    from_dt = _parse_dt(dateFrom)
    to_dt = _parse_dt(dateTo)
    if not from_dt or not to_dt:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date range"})

    # Reuse analytics logic (no HTTP call)
    from app.api.v1.analytics import gbr_trips  # local import to avoid circular deps

    trips = await gbr_trips(
        date_from=dateFrom,
        date_to=dateTo,
        gbr_name=(gbrName or None),
        object_id=(objectId or None),
        limit=2000,
        offset=0,
        session=session,
        _perm=current,
    )

    # Build XLSX similarly to analytics export
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side

    columns = [
        "№ объекта",
        "Адрес",
        "Шлейф",
        "Инженер",
        "Результат",
        "Дата",
        "ГБР",
        "Вызов",
        "Прибыл",
        "Время в пути",
        "Результат осмотра",
        "Оператор",
        "Заявка",
        "Штраф",
        "Сработок за полгода",
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Рапорт"

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    ws.cell(row=1, column=1, value="Рапорт").font = Font(bold=True, size=14)
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")

    period_text = f"За период: {from_dt.strftime('%d.%m.%Y %H:%M')} — {to_dt.strftime('%d.%m.%Y %H:%M')}"
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    ws.cell(row=2, column=1, value=period_text).alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(columns))
    ws.cell(row=3, column=1, value="оперативная обстановка следующая:").alignment = Alignment(
        horizontal="center"
    )

    header_row = 5
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    widths = [12, 28, 10, 16, 16, 12, 14, 18, 18, 12, 18, 16, 14, 10, 18]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[chr(ord('A') + i - 1)].width = w

    for col_idx, title in enumerate(columns, start=1):
        c = ws.cell(row=header_row, column=col_idx, value=title)
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = border

    def fmt_ts(ts: str | None) -> str:
        if not ts:
            return ""
        return ts.replace("T", " ")[:19]

    def fmt_date(ts: str | None) -> str:
        if not ts:
            return ""
        return ts[:10].replace("-", ".")

    def fmt_travel(seconds) -> str:
        try:
            if seconds is None:
                return ""
            total = int(round(float(seconds)))
            if total < 0:
                return ""
            h = total // 3600
            m = (total % 3600) // 60
            s = total % 60
            return f"{h:d}:{m:02d}:{s:02d}" if h > 0 else f"{m:d}:{s:02d}"
        except Exception:
            return ""

    rows = trips.get("data") or []
    start_row = header_row + 1
    for i, r in enumerate(rows, start=0):
        row_idx = start_row + i
        called_at = r.get("calledAt")
        arrived_at = r.get("arrivedAt")
        cancelled_at = r.get("cancelledAt")
        values = [
            r.get("objectId") or "",
            r.get("objectName") or r.get("clientName") or "",
            "",
            "",
            "",
            fmt_date(called_at),
            r.get("gbrName") or "",
            fmt_ts(called_at),
            fmt_ts(arrived_at) if arrived_at else ("Отмена" if cancelled_at else ""),
            fmt_travel(r.get("travelSeconds")),
            "",
            "",
            "",
            "",
            "",
        ]
        for col_idx, v in enumerate(values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=v)
            c.border = border
            c.alignment = Alignment(vertical="top", wrap_text=True)

    ws.freeze_panes = ws["A6"]
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0

    out = BytesIO()
    wb.save(out)
    data = out.getvalue()

    report_id = str(uuid4())
    ps = from_dt.date().isoformat()
    pe = to_dt.date().isoformat()
    filename = f"raport-gbr-{ps}-{pe}.xlsx"
    path = _write_report_file(report_id, filename, data)

    r = Report(
        id=report_id,
        type="gbrRaportXlsx",
        period_start=ps,
        period_end=pe,
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="generated",
        events_count=int(trips.get("total") or len(rows) or 0),
        critical_count=0,
        file_name=filename,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        storage_path=str(path),
        params_json=json.dumps(
            {"dateFrom": dateFrom, "dateTo": dateTo, "gbrName": gbrName, "objectId": objectId},
            ensure_ascii=False,
        ),
        error_message=None,
    )
    session.add(r)
    await session.commit()
    return _as_report_out_dict(r)


@router.get("/{report_id}/download")
async def download_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> Response:
    r = (
        await session.execute(select(Report).where(Report.id == report_id).limit(1))
    ).scalars().first()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Report not found"})

    # Permission gate for analytics-based reports
    if str(r.type) == "gbrRaportXlsx":
        have = set(map(str, current.get("permissions") or []))
        if "analytics:read" not in have and current.get("role") != "admin":
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Missing permissions"})

    if not r.storage_path or not r.file_name:
        raise HTTPException(status_code=409, detail={"code": "NO_FILE", "message": "Report has no stored file"})

    path = Path(str(r.storage_path))
    if not path.exists():
        raise HTTPException(status_code=410, detail={"code": "GONE", "message": "Stored file not found"})

    # Ensure file is inside our store dir
    store = _reports_store_dir().resolve()
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "BAD_PATH", "message": "Invalid file path"})
    if store not in resolved.parents and resolved != store:
        raise HTTPException(status_code=400, detail={"code": "BAD_PATH", "message": "Invalid file path"})

    media = r.mime_type or "application/octet-stream"
    return FileResponse(
        path=str(resolved),
        media_type=media,
        filename=r.file_name,
    )


@router.get("/{report_id}/preview")
async def preview_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> dict:
    r = (
        await session.execute(select(Report).where(Report.id == report_id).limit(1))
    ).scalars().first()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Report not found"})

    if str(r.type) != "gbrRaportXlsx":
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Preview not supported"})

    have = set(map(str, current.get("permissions") or []))
    if "analytics:read" not in have and current.get("role") != "admin":
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Missing permissions"})

    params = {}
    try:
        if r.params_json:
            params = json.loads(r.params_json)
    except Exception:
        params = {}

    from app.api.v1.analytics import gbr_trips  # local import

    date_from = str(params.get("dateFrom") or "")
    date_to = str(params.get("dateTo") or "")
    gbr_name = params.get("gbrName")
    object_id = params.get("objectId")

    return await gbr_trips(
        date_from=date_from,
        date_to=date_to,
        gbr_name=(str(gbr_name) if gbr_name else None),
        object_id=(str(object_id) if object_id else None),
        limit=2000,
        offset=0,
        session=session,
        _perm=current,
    )


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
