from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from datetime import datetime
from datetime import date as date_type
from datetime import time as time_type
from datetime import timedelta
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from starlette.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, case, func, or_, select

from app.api.v1.deps import get_current_user
from app.db.session import get_session
from app.services.report_service import export_daily_report_csv, today_str
from app.models.event_action import EventAction
from app.models.event import Event
from app.models.object import Object
from app.models.report import Report

router = APIRouter(prefix="/reports")


def _agency_event_id(event_id: str | None) -> str | None:
    """Extract agency numeric event id from stored local id.

    For MSSQL imports we store ids like: 'mssql:{date_key}:{event_id}'.
    """

    if not event_id:
        return None
    parts = str(event_id).split(":")
    if len(parts) >= 3:
        return parts[-1] or None
    return None


def _ensure_reports_manage_perm(current: dict) -> None:
    role = str(current.get("role") or "")
    if role in {"admin", "analyst"}:
        return
    raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Missing permissions"})


def _parse_dt(value: str) -> datetime | None:
    try:
        v = (value or "").strip()
        # Frontend often sends UTC ISO with trailing 'Z'.
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        # DB stores timestamps as naive datetimes (no timezone). If frontend sends
        # tz-aware ISO strings (e.g. trailing 'Z'), normalize to server local time
        # and drop tzinfo so comparisons match stored values.
        if dt.tzinfo is not None:
            return dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def _parse_date(value: str) -> date_type | None:
    try:
        return date_type.fromisoformat(value)
    except Exception:
        return None


def _parse_hhmm(value: str, *, default: time_type) -> time_type:
    v = (value or "").strip()
    if not v:
        return default
    try:
        parts = v.split(":")
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        return time_type(hour=hh, minute=mm)
    except Exception:
        return default


def _shift_bucket(
    ts: datetime,
    *,
    day_start: time_type,
    night_start: time_type,
) -> tuple[date_type, str]:
    """Returns (shift_date, shift_name).

    day shift: [day_start, night_start)
    night shift: [night_start, next_day day_start)

    If ts time is before day_start it is counted to previous day's night shift.
    """

    t = ts.time()
    d = ts.date()
    if t >= night_start:
        return (d, "ночь")
    if t >= day_start:
        return (d, "день")
    return (d - timedelta(days=1), "ночь")


def _pcn_ledger_payout(
    dispatchers: int,
    percent: float,
    *,
    payouts: tuple[int, int, int, int],
    thresholds: dict[int, tuple[int, int, int]],
) -> int:
    """Payout based on percent and dispatcher count.

    Logic matches the Excel formula shape:
    - < t1 -> pay0
    - < t2 -> pay1
    - <= t3 -> pay2
    - else -> pay3
    """

    t = thresholds.get(int(dispatchers))
    if not t:
        return int(payouts[0])
    t1, t2, t3 = t
    pay0, pay1, pay2, pay3 = payouts
    if percent < t1:
        return int(pay0)
    if percent < t2:
        return int(pay1)
    if percent <= t3:
        return int(pay2)
    return int(pay3)


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
    params: dict = {}
    try:
        if r.params_json:
            params = json.loads(r.params_json)
    except Exception:
        params = {}

    title: str | None = None
    rt = str(r.type)
    if rt == "gbrRaportXlsx":
        gbr = str(params.get("gbrName") or "").strip()
        title = f"Рапорт ГБР по {gbr}" if gbr else "Рапорт ГБР"
    elif rt == "objectsByCode":
        code = str(params.get("eventCode") or "").strip()
        title = f"Объекты по коду {code}" if code else "Объекты по коду"
    elif rt == "daily":
        title = "Суточный отчёт"
    elif rt == "pcnLedger":
        ps = str(r.period_start or "").strip()
        pe = str(r.period_end or "").strip()
        title = f"Ведомость по тревогам (ПЦН) {ps}–{pe}" if ps and pe else "Ведомость по тревогам (ПЦН)"
    elif rt == "eventsRaportXlsx":
        ps = str(r.period_start or "").strip()
        pe = str(r.period_end or "").strip()
        title = f"Рапорт по событиям {ps}–{pe}" if ps and pe else "Рапорт по событиям"

    d = {
        "id": str(r.id),
        "type": str(r.type),
        "title": title,
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


def _resolve_and_validate_store_path(storage_path: str) -> Path:
    path = Path(str(storage_path))
    if not path.exists():
        raise HTTPException(status_code=410, detail={"code": "GONE", "message": "Stored file not found"})

    store = _reports_store_dir().resolve()
    try:
        resolved = path.resolve()
    except Exception:
        raise HTTPException(status_code=400, detail={"code": "BAD_PATH", "message": "Invalid file path"})
    if store not in resolved.parents and resolved != store:
        raise HTTPException(status_code=400, detail={"code": "BAD_PATH", "message": "Invalid file path"})
    return resolved


def _file_ext(filename: str | None) -> str:
    if not filename:
        return ""
    f = filename.lower().strip()
    if f.endswith(".csv"):
        return "csv"
    if f.endswith(".xlsx"):
        return "xlsx"
    return ""


def _preview_table_from_csv_bytes(content: bytes, max_rows: int = 200) -> dict:
    import csv
    import io

    text = content.decode("utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return {"kind": "table", "columns": [], "rows": []}

    reader = csv.reader(lines, delimiter=";")
    rows = list(reader)
    columns = [str(x or "") for x in (rows[0] if rows else [])]
    out_rows: list[list[str]] = []
    for r in rows[1 : 1 + max_rows]:
        out_rows.append([str(x or "") for x in r])
    return {"kind": "table", "columns": columns, "rows": out_rows}


def _preview_table_from_xlsx_bytes(content: bytes, max_rows: int = 200, max_cols: int = 50) -> dict:
    from io import BytesIO

    try:
        from openpyxl import load_workbook
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "MISSING_DEP", "message": "openpyxl not installed"})

    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0] if wb.worksheets else None
    if ws is None:
        return {"kind": "table", "columns": [], "rows": []}

    collected: list[list[str]] = []
    for row in ws.iter_rows(values_only=True, max_row=max_rows, max_col=max_cols):
        collected.append(["" if v is None else str(v) for v in row])

    if not collected:
        return {"kind": "table", "columns": [], "rows": [], "titleLines": []}

    def _norm(v: str) -> str:
        return (v or "").strip().lower()

    def _non_empty_count(row: list[str]) -> int:
        return sum(1 for x in row if (x or "").strip())

    # Heuristic: find a header row (for Raport templates it's not row 1).
    header_idx: int = 0
    for i, r in enumerate(collected[: min(len(collected), 50)]):
        low = [_norm(x) for x in r]
        if any("№ объекта" in x or "номер объекта" in x for x in low):
            header_idx = i
            break
        if _non_empty_count(r) >= 3 and any(x in {"адрес", "гбр", "вызов", "прибыл", "оператор"} for x in low):
            header_idx = i
            break

    title_lines: list[str] = []
    if header_idx > 0:
        for r in collected[:header_idx]:
            parts = [x.strip() for x in r if (x or "").strip()]
            if parts:
                title_lines.append(" ".join(parts))

    columns = collected[header_idx]
    rows = collected[header_idx + 1 :]

    # Trim trailing completely empty rows for nicer preview.
    while rows and _non_empty_count(rows[-1]) == 0:
        rows.pop()

    return {"kind": "table", "columns": columns, "rows": rows, "titleLines": title_lines}


def _csv_bytes_to_xlsx_bytes(content: bytes) -> bytes:
    import csv
    import io
    from io import BytesIO

    try:
        from openpyxl import Workbook
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "MISSING_DEP", "message": "openpyxl not installed"})

    text = content.decode("utf-8-sig", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    reader = csv.reader(lines, delimiter=";")

    wb = Workbook()
    ws = wb.active
    ws.title = "Report"
    for r_idx, row in enumerate(reader, start=1):
        for c_idx, v in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=v)

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def _xlsx_bytes_to_csv_bytes(content: bytes) -> bytes:
    import csv
    from io import BytesIO, StringIO

    try:
        from openpyxl import load_workbook
    except Exception:
        raise HTTPException(status_code=500, detail={"code": "MISSING_DEP", "message": "openpyxl not installed"})

    wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0] if wb.worksheets else None
    buf = StringIO()
    writer = csv.writer(buf, delimiter=";")
    if ws is not None:
        for row in ws.iter_rows(values_only=True):
            writer.writerow(["" if v is None else str(v) for v in row])
    return buf.getvalue().encode("utf-8-sig")


@router.get("")
async def list_reports(
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> list[dict]:
    # 1) Stored reports (history)
    stored = (
        await session.execute(
            select(Report)
            .where(Report.type != "daily")
            .order_by(Report.generated_at.desc())
            .limit(200)
        )
    ).scalars().all()

    out: list[dict] = [_as_report_out_dict(r) for r in stored]

    return out


@router.post("/generate/daily", include_in_schema=False)
async def generate_daily_report(
    date: str = Query(default_factory=today_str, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> dict:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "DISABLED",
            "message": "Суточный отчёт отключён. Формируйте отчёты только по согласованным событиям/объектам.",
        },
    )

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
        xlsx = _csv_bytes_to_xlsx_bytes(content)
        filename = f"daily-report-{day.isoformat()}.xlsx"
        path = _write_report_file(report_id, filename, xlsx)

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
        r.mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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
    # Generate XLSX now and store (CSV is not generated as an artifact).
    # Build XLSX directly so headers are human-friendly and we can include more columns.
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

    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    # best-effort: take one code_text for code
    code_text = (
        await session.execute(select(func.max(Event.code_text)).where(Event.code == eventCode.strip()))
    ).scalar_one_or_none()

    obj_name = func.coalesce(Object.name, Event.object_name)
    obj_addr = func.coalesce(Object.address, Event.location)

    where = and_(*filters)

    base_stmt = (
        select(
            Event.id.label("event_id"),
            Event.object_id.label("object_id"),
            obj_name.label("object_name"),
            obj_addr.label("address"),
            Event.timestamp.label("timestamp"),
            Event.result_text.label("result_text"),
            Event.meter_count.label("meter_count"),
        )
        .select_from(Event)
        .outerjoin(Object, Object.id == Event.object_id)
        .where(where)
    )
    base = base_stmt.subquery("base")

    agg_stmt = (
        select(
            base.c.object_id,
            base.c.object_name,
            base.c.address,
            func.count().label("events_count"),
            func.min(base.c.timestamp).label("first_time"),
            func.max(base.c.timestamp).label("last_time"),
        )
        .group_by(base.c.object_id, base.c.object_name, base.c.address)
        .order_by(func.count().desc())
        .limit(200000)
    )
    agg = agg_stmt.subquery("agg")

    rn_stmt = select(
        base.c.object_id.label("object_id"),
        base.c.event_id.label("event_id"),
        base.c.result_text.label("result_text"),
        base.c.meter_count.label("meter_count"),
        base.c.timestamp.label("timestamp"),
        func.row_number().over(partition_by=base.c.object_id, order_by=base.c.timestamp.desc()).label("rn"),
    )
    rn = rn_stmt.subquery("rn")
    last_note = (
        select(
            rn.c.object_id.label("object_id"),
            rn.c.event_id.label("last_event_id"),
            rn.c.result_text.label("last_result_text"),
            rn.c.meter_count.label("last_meter_count"),
        )
        .where(rn.c.rn == 1)
        .subquery("last_note")
    )

    stmt = (
        select(
            agg.c.object_id,
            agg.c.object_name,
            agg.c.address,
            agg.c.events_count,
            agg.c.first_time,
            agg.c.last_time,
            last_note.c.last_event_id,
            last_note.c.last_meter_count,
            last_note.c.last_result_text,
        )
        .select_from(agg)
        .outerjoin(last_note, last_note.c.object_id == agg.c.object_id)
        .order_by(agg.c.events_count.desc())
    )

    rows = (await session.execute(stmt)).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Объекты"

    headers = [
        "Номер объекта",
        "Название объекта",
        "Адрес",
        "Количество событий",
        "Код события",
        "Событие",
        "Первое срабатывание",
        "Последнее срабатывание",
        "ID события (аг.)",
        "Параметр (MeterCount)",
        "Комментарий оператора (Result_Text)",
    ]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    def fmt_ts(dt: datetime | None) -> str:
        if not dt:
            return ""
        return dt.isoformat(sep=" ", timespec="seconds")

    for object_id, object_name, address, events_count, first_time, last_time, last_event_id, last_meter_count, last_result_text in rows:
        ws.append(
            [
                object_id or "",
                object_name or "",
                address or "",
                int(events_count or 0),
                eventCode.strip(),
                code_text or "",
                fmt_ts(first_time),
                fmt_ts(last_time),
                _agency_event_id(last_event_id) or "",
                last_meter_count or "",
                last_result_text or "",
            ]
        )

    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 55
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 40
    ws.column_dimensions["G"].width = 22
    ws.column_dimensions["H"].width = 22
    ws.column_dimensions["I"].width = 16
    ws.column_dimensions["J"].width = 32
    ws.column_dimensions["K"].width = 35

    out = BytesIO()
    wb.save(out)
    xlsx = out.getvalue()

    # Determine period strings for list
    ps = (dt_from.date().isoformat() if dt_from else (str(year) if year else ""))
    pe = (dt_to.date().isoformat() if dt_to else (str(year) if year else ""))
    if not ps:
        ps = date_type.today().isoformat()
    if not pe:
        pe = ps

    report_id = str(uuid4())
    filename = f"objects-by-code-{eventCode.strip()}-{ps}-{pe}.xlsx"
    path = _write_report_file(report_id, filename, xlsx)

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
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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

    page_size = 2000
    max_rows = 50000
    trips = await gbr_trips(
        date_from=dateFrom,
        date_to=dateTo,
        gbr_name=(gbrName or None),
        object_id=(objectId or None),
        limit=page_size,
        offset=0,
        session=session,
        _perm=current,
    )

    total = int(trips.get("total") or 0)
    if max_rows and total > max_rows:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "TOO_MANY_ROWS",
                "message": f"Слишком много строк для рапорта: {total}. Сузьте период/фильтры.",
            },
        )

    rows_all: list[dict[str, Any]] = list(trips.get("data") or [])
    if total > len(rows_all) and len(rows_all) >= page_size:
        offset = page_size
        while len(rows_all) < total:
            out = await gbr_trips(
                date_from=dateFrom,
                date_to=dateTo,
                gbr_name=(gbrName or None),
                object_id=(objectId or None),
                limit=page_size,
                offset=offset,
                session=session,
                _perm=current,
            )
            batch = out.get("data") or []
            if not batch:
                break
            rows_all.extend(batch)
            offset += page_size
            if len(batch) < page_size:
                break

    trips["data"] = rows_all
    trips["total"] = total

    # Build XLSX similarly to analytics export
    from io import BytesIO
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

    def clean_excel_text(value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str):
            return re.sub(ILLEGAL_CHARACTERS_RE, "", value)
        return value

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
        "ID события (аг.)",
        "Параметр (MeterCount)",
        "Пометка оператора (Result_Text)",
        "Статус",
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Рапорт"

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    header_title = "Рапорт"
    if (gbrName or "").strip():
        header_title = f"Рапорт ГБР по {(gbrName or '').strip()}"
    ws.cell(row=1, column=1, value=clean_excel_text(header_title)).font = Font(bold=True, size=14)
    ws.cell(row=1, column=1).alignment = Alignment(horizontal="center", vertical="center")

    period_text = f"За период: {from_dt.strftime('%d.%m.%Y %H:%M')} — {to_dt.strftime('%d.%m.%Y %H:%M')}"
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    ws.cell(row=2, column=1, value=clean_excel_text(period_text)).alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(columns))
    ws.cell(row=3, column=1, value="оперативная обстановка следующая:").alignment = Alignment(
        horizontal="center"
    )

    header_row = 5
    thin = Side(style="thin", color="000000")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    widths = [12, 28, 10, 16, 16, 12, 14, 18, 18, 12, 18, 16, 14, 10, 18, 16, 28, 45, 14]
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
            r.get("agencyEventId") or "",
            r.get("meterCount") or "",
            r.get("resultText") or "",
            r.get("tripStatus") or "",
        ]
        for col_idx, v in enumerate(values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=clean_excel_text(v))
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
    gbr_part = (gbrName or "").strip()
    if gbr_part:
        filename = f"raport-gbr-{gbr_part}-{ps}-{pe}.xlsx"
    else:
        filename = f"raport-gbr-{ps}-{pe}.xlsx"
    path = _write_report_file(report_id, filename, data)

    r = Report(
        id=report_id,
        type="gbrRaportXlsx",
        period_start=ps,
        period_end=pe,
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="generated",
        events_count=len(rows),
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


@router.post("/generate/events-raport-xlsx")
async def generate_events_raport_xlsx(
    dateFrom: str = Query(description="ISO datetime"),
    dateTo: str = Query(description="ISO datetime"),
    type: str | None = Query(default=None, description="Event.type filter"),  # noqa: A002
    objectId: str | None = Query(default=None, description="Event.object_id filter"),
    severity: str | None = Query(default=None, description="Event.severity filter"),
    status: str | None = Query(default=None, description="Event.status filter"),
    search: str | None = Query(default=None, description="Free-text search (description/object/client/location)"),
    includeNoise: bool = Query(False, description="Include access/noise events"),
    includeSystem: bool = Query(False, description="Include system-handled events (no operator)"),
    includeCancelled: bool = Query(False, description="Include cancelled events"),
    onlyWithOperatorComment: bool = Query(
        True,
        description="Show only events that have an operator comment (Result_Text)",
    ),
    limit: int = Query(50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> dict:
    from_dt = _parse_dt(dateFrom)
    to_dt = _parse_dt(dateTo)
    if not from_dt or not to_dt or to_dt < from_dt:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date range"})

    # Reuse events raport builder (no HTTP call)
    from app.api.v1.events import build_events_raport_xlsx_bytes

    xlsx, events_count = await build_events_raport_xlsx_bytes(
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
        onlyWithOperatorComment=onlyWithOperatorComment,
        limit=limit,
        session=session,
    )

    report_id = str(uuid4())
    ps = from_dt.date().isoformat()
    pe = to_dt.date().isoformat()
    filename = f"raport-events-{ps}-{pe}.xlsx"
    path = _write_report_file(report_id, filename, xlsx)

    r = Report(
        id=report_id,
        type="eventsRaportXlsx",
        period_start=ps,
        period_end=pe,
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="generated",
        events_count=int(events_count or 0),
        critical_count=0,
        file_name=filename,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        storage_path=str(path),
        params_json=json.dumps(
            {
                "dateFrom": dateFrom,
                "dateTo": dateTo,
                "type": type,
                "objectId": objectId,
                "severity": severity,
                "status": status,
                "search": search,
                "includeNoise": includeNoise,
                "includeSystem": includeSystem,
                "includeCancelled": includeCancelled,
                "onlyWithOperatorComment": onlyWithOperatorComment,
                "limit": limit,
            },
            ensure_ascii=False,
        ),
        error_message=None,
    )
    session.add(r)
    await session.commit()
    return _as_report_out_dict(r)


@router.post("/generate/pcn-ledger-xlsx")
async def generate_pcn_ledger_xlsx(
    dateFrom: str = Query(description="YYYY-MM-DD"),
    dateTo: str = Query(description="YYYY-MM-DD"),
    dayStart: str | None = Query(default="09:00", description="HH:MM (start of day shift)"),
    nightStart: str | None = Query(default="20:00", description="HH:MM (start of night shift)"),
    actionName: str | None = Query(default="Прием на обработку", description="EventAction.action_name match"),
    operatorQuery: str | None = Query(default=None, description="Filter by operator name (substring)"),
    hideOperatorNames: bool = Query(
        default=False,
        description="If true, operator names are hidden in XLSX (personal data protection)",
    ),
    pay0: int = Query(default=0, ge=0, le=100000, description="Payout for lowest bracket"),
    pay1: int = Query(default=330, ge=0, le=100000, description="Payout for bracket 2"),
    pay2: int = Query(default=430, ge=0, le=100000, description="Payout for bracket 3"),
    pay3: int = Query(default=480, ge=0, le=100000, description="Payout for top bracket"),
    thr3_1: int = Query(default=29, ge=0, le=100, description="3 dispatchers: threshold 1"),
    thr3_2: int = Query(default=36, ge=0, le=100, description="3 dispatchers: threshold 2"),
    thr3_3: int = Query(default=40, ge=0, le=100, description="3 dispatchers: threshold 3"),
    thr4_1: int = Query(default=21, ge=0, le=100, description="4 dispatchers: threshold 1"),
    thr4_2: int = Query(default=27, ge=0, le=100, description="4 dispatchers: threshold 2"),
    thr4_3: int = Query(default=30, ge=0, le=100, description="4 dispatchers: threshold 3"),
    thr5_1: int = Query(default=17, ge=0, le=100, description="5 dispatchers: threshold 1"),
    thr5_2: int = Query(default=23, ge=0, le=100, description="5 dispatchers: threshold 2"),
    thr5_3: int = Query(default=26, ge=0, le=100, description="5 dispatchers: threshold 3"),
    bonusDefault: int = Query(default=500, ge=0, le=100000, description="Default bonus per operator row"),
    bonusOverride: list[str] | None = Query(
        default=None,
        description="Repeatable override: 'ФИО:1000'",
    ),
    includePresenceOnly: bool = Query(
        default=True,
        description="Include operators who were present in the shift even if they have 0 alarms",
    ),
    dispatchersSource: str = Query(
        default="auto",
        description="Dispatcher count source: auto|presence|actions",
    ),
    minPresenceMinutes: int = Query(
        default=30,
        ge=0,
        le=24 * 60,
        description="Minimum presence minutes inside a shift to count as dispatcher",
    ),
    presenceGraceMinutes: int = Query(
        default=15,
        ge=0,
        le=24 * 60,
        description="Grace minutes added after lastSeenAt to close non-ended presence sessions",
    ),
    session: AsyncSession = Depends(get_session),
    _current: dict = Depends(get_current_user),
) -> dict:
    # Stored XLSX report: "Ведомость учета работы операторов ПЦН".

    ds = (dispatchersSource or "auto").strip().lower()
    if ds not in {"auto", "presence", "actions"}:
        raise HTTPException(
            status_code=400,
            detail={"code": "BAD_REQUEST", "message": "dispatchersSource must be one of: auto|presence|actions"},
        )

    def _has_time_component(v: str | None) -> bool:
        return bool(re.search(r"\d{1,2}:\d{2}", (v or "")))

    dt_from: datetime | None = _parse_dt(dateFrom) if _has_time_component(dateFrom) else None
    dt_to: datetime | None = _parse_dt(dateTo) if _has_time_component(dateTo) else None

    d_from: date_type | None = None
    d_to: date_type | None = None
    if dt_from is None:
        d_from = _parse_date(dateFrom) or (_parse_dt(dateFrom).date() if _parse_dt(dateFrom) else None)
    if dt_to is None:
        d_to = _parse_date(dateTo) or (_parse_dt(dateTo).date() if _parse_dt(dateTo) else None)

    day_start = _parse_hhmm(dayStart or "", default=time_type(9, 0))
    night_start = _parse_hhmm(nightStart or "", default=time_type(20, 0))

    exact_window = dt_from is not None or dt_to is not None
    if exact_window:
        if dt_from is None or dt_to is None or dt_to < dt_from:
            raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date range"})
        window_start = dt_from
        window_end = dt_to
        period_start_date = dt_from.date()
        period_end_date = dt_to.date()

        # For exact windows we do NOT clamp by shift_date, otherwise early-hours actions
        # (before dayStart) would be incorrectly dropped (they belong to previous day's night shift).
        clamp_shift_dates: tuple[date_type, date_type] | None = None

        # For presence bucketing we need a date span that covers possible shift_dates.
        # shift_bucket can produce (ts.date() - 1) for times before dayStart.
        presence_span_start = window_start.date() - timedelta(days=1)
        presence_span_end = window_end.date()
    else:
        if not d_from or not d_to or d_to < d_from:
            raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date range"})
        # Build query window that covers the last night shift up to next day's dayStart.
        window_start = datetime.combine(d_from, day_start)
        window_end = datetime.combine(d_to + timedelta(days=1), day_start)
        period_start_date = d_from
        period_end_date = d_to
        clamp_shift_dates = (d_from, d_to)
        presence_span_start = d_from
        presence_span_end = d_to

    if period_end_date < period_start_date:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid date range"})

    payouts: tuple[int, int, int, int] = (int(pay0), int(pay1), int(pay2), int(pay3))
    thresholds: dict[int, tuple[int, int, int]] = {
        3: (int(thr3_1), int(thr3_2), int(thr3_3)),
        4: (int(thr4_1), int(thr4_2), int(thr4_3)),
        5: (int(thr5_1), int(thr5_2), int(thr5_3)),
    }

    def _validate_thresholds(label: str, t: tuple[int, int, int]) -> None:
        a, b, c = t
        if not (0 <= a <= b <= c <= 100):
            raise HTTPException(
                status_code=400,
                detail={"code": "BAD_REQUEST", "message": f"Invalid thresholds for {label}"},
            )

    _validate_thresholds("3 dispatchers", thresholds[3])
    _validate_thresholds("4 dispatchers", thresholds[4])
    _validate_thresholds("5 dispatchers", thresholds[5])

    # Bonus overrides parsing
    overrides: dict[str, int] = {}
    for item in bonusOverride or []:
        try:
            if not item:
                continue
            if ":" not in item:
                continue
            name, val = item.split(":", 1)
            name = name.strip()
            val_i = int(val.strip())
            if name:
                overrides[name] = val_i
        except Exception:
            continue

    # Select one representative action_time per (event_id, operator) for the chosen action.
    # Then group in Python into shifts because SQL bucketing differs between SQLite/Postgres.
    act = (actionName or "").strip()
    stmt = (
        select(
            EventAction.event_id,
            EventAction.operator_name,
            func.min(EventAction.action_time).label("ts"),
        )
        .select_from(EventAction)
        .join(Event, Event.id == EventAction.event_id)
        .where(Event.type == "alarm")
        .where(EventAction.operator_name.is_not(None))
        .where(EventAction.action_time >= window_start)
        .group_by(EventAction.event_id, EventAction.operator_name)
    )

    if exact_window:
        stmt = stmt.where(EventAction.action_time <= window_end)
    else:
        stmt = stmt.where(EventAction.action_time < window_end)

    if act:
        # Prefer exact match but allow substring match for robustness.
        stmt = stmt.where(or_(EventAction.action_name == act, EventAction.action_name.ilike(f"%{act}%")))

    oq = (operatorQuery or "").strip()
    if oq:
        stmt = stmt.where(EventAction.operator_name.ilike(f"%{oq}%"))

    rows = (await session.execute(stmt)).all()

    # Presence (who was logged in / "in the system")
    # Used to compute the dispatcher count per shift (staffing), independent from actions.
    presence_ops_by_shift: dict[tuple[date_type, str], set[str]] = {}
    try:
        from app.models.user_presence_session import UserPresenceSession

        grace = timedelta(minutes=int(presenceGraceMinutes))
        min_seconds = int(minPresenceMinutes) * 60

        # Query a slightly wider window to account for grace.
        q_start = window_start - grace
        q_end = window_end + grace

        pres_stmt = (
            select(
                UserPresenceSession.username,
                UserPresenceSession.started_at,
                UserPresenceSession.last_seen_at,
                UserPresenceSession.ended_at,
            )
            .where(UserPresenceSession.started_at < q_end)
            .where(
                or_(
                    and_(UserPresenceSession.ended_at.is_not(None), UserPresenceSession.ended_at >= q_start),
                    and_(UserPresenceSession.ended_at.is_(None), UserPresenceSession.last_seen_at >= q_start),
                )
            )
        )

        pres_rows = (await session.execute(pres_stmt)).all()

        # Prepare shift windows for the date range.
        shift_windows: list[tuple[date_type, str, datetime, datetime]] = []
        d = presence_span_start
        while d <= presence_span_end:
            day_s = datetime.combine(d, day_start)
            day_e = datetime.combine(d, night_start)
            night_s = datetime.combine(d, night_start)
            night_e = datetime.combine(d + timedelta(days=1), day_start)
            shift_windows.append((d, "день", day_s, day_e))
            shift_windows.append((d, "ночь", night_s, night_e))
            d = d + timedelta(days=1)

        # Accumulate overlap seconds per (shift_date, shift_name, operator)
        presence_seconds: dict[tuple[date_type, str, str], int] = {}
        for username, started_at, last_seen_at, ended_at in pres_rows:
            op = str(username or "").strip()
            if not op or not isinstance(started_at, datetime) or not isinstance(last_seen_at, datetime):
                continue

            ses_start = started_at
            ses_end = ended_at if isinstance(ended_at, datetime) else (last_seen_at + grace)
            if ses_end <= ses_start:
                continue

            for sd, sh, s_start, s_end in shift_windows:
                # fast reject
                if ses_end <= s_start or ses_start >= s_end:
                    continue
                overlap = min(ses_end, s_end) - max(ses_start, s_start)
                sec = int(overlap.total_seconds())
                if sec <= 0:
                    continue
                key = (sd, sh, op)
                presence_seconds[key] = presence_seconds.get(key, 0) + sec

        for (sd, sh, op), sec in presence_seconds.items():
            if min_seconds <= 0 or sec >= min_seconds:
                presence_ops_by_shift.setdefault((sd, sh), set()).add(op)
    except Exception:
        # Presence is optional; fallback to action-based dispatcher count.
        presence_ops_by_shift = {}

    # Aggregate counts per (shift_date, shift_name, operator)
    counts: dict[tuple[date_type, str, str], int] = {}
    for event_id, op, ts in rows:
        if not isinstance(ts, datetime) or not op:
            continue
        shift_date, shift_name = _shift_bucket(ts, day_start=day_start, night_start=night_start)
        if clamp_shift_dates is not None:
            dmin, dmax = clamp_shift_dates
            if shift_date < dmin or shift_date > dmax:
                continue
        key = (shift_date, shift_name, str(op))
        counts[key] = counts.get(key, 0) + 1

    # Totals per shift
    shift_totals: dict[tuple[date_type, str], int] = {}
    shift_ops: dict[tuple[date_type, str], set[str]] = {}
    for (sd, sh, op), c in counts.items():
        shift_totals[(sd, sh)] = shift_totals.get((sd, sh), 0) + int(c or 0)
        shift_ops.setdefault((sd, sh), set()).add(op)

    # Build ordered output rows
    ordered_shifts = sorted(shift_totals.keys(), key=lambda x: (x[0].toordinal(), 0 if x[1] == "день" else 1))
    out_rows: list[dict[str, object]] = []
    control_rows: list[dict[str, object]] = []
    for sd, sh in ordered_shifts:
        total = int(shift_totals.get((sd, sh)) or 0)
        ops_from_actions = shift_ops.get((sd, sh)) or set()
        ops_from_presence = presence_ops_by_shift.get((sd, sh)) or set()

        dispatchers_presence = len(ops_from_presence)
        dispatchers_actions = len(ops_from_actions)

        # Dispatcher count source selection.
        if ds == "presence":
            dispatchers = dispatchers_presence
        elif ds == "actions":
            dispatchers = dispatchers_actions
        else:
            # auto: prefer presence, but if it's empty fallback to actions.
            dispatchers = dispatchers_presence if dispatchers_presence else dispatchers_actions

        control_rows.append(
            {
                "date": sd,
                "shift": sh,
                "totalAlarms": total,
                "dispatchersPresence": dispatchers_presence,
                "dispatchersActions": dispatchers_actions,
                "dispatchersUsed": dispatchers,
            }
        )

        # Operators for this shift
        alarms_by_op: dict[str, int] = {}
        for (sd2, sh2, op), c in counts.items():
            if sd2 == sd and sh2 == sh:
                alarms_by_op[str(op)] = int(c or 0)

        if includePresenceOnly:
            op_names = set(alarms_by_op.keys()) | set(ops_from_presence)
        else:
            op_names = set(alarms_by_op.keys())

        ops = [(op, int(alarms_by_op.get(op, 0))) for op in op_names]
        ops.sort(key=lambda x: (-x[1], x[0].lower()))

        for op, c in ops:
            percent = (float(c) * 100.0 / float(total)) if total > 0 else 0.0
            payout = _pcn_ledger_payout(dispatchers, percent, payouts=payouts, thresholds=thresholds)
            bonus = int(overrides.get(op, bonusDefault))
            out_rows.append(
                {
                    "date": sd,
                    "dispatchers": dispatchers,
                    "shift": sh,
                    "operator": op,
                    "alarms": c,
                    "percent": percent,
                    "payout": payout,
                    "bonus": bonus,
                    "total": payout + bonus,
                }
            )

    # Build XLSX
    from io import BytesIO

    try:
        from openpyxl import Workbook
        from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
        from openpyxl.styles import Alignment, Border, Font, Side
    except ModuleNotFoundError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "MISSING_DEP",
                "message": "Не установлен openpyxl (нужен для XLSX). Установите зависимости: pip install -r backend/requirements.txt",
            },
        ) from e

    def clean_excel_text(value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str):
            return re.sub(ILLEGAL_CHARACTERS_RE, "", value)
        return value

    wb = Workbook()
    ws = wb.active
    ws.title = "Ведомость"

    thin = Side(style="thin", color="D0D0D0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Threshold legend (like sample)
    ws["C3"].value = f"{payouts[0]} р."
    ws["D3"].value = f"{payouts[1]} р."
    ws["E3"].value = f"{payouts[2]} р."
    ws["F3"].value = f"{payouts[3]} р."

    t31, t32, t33 = thresholds[3]
    t41, t42, t43 = thresholds[4]
    t51, t52, t53 = thresholds[5]

    ws["B4"].value = "3 диспетчера"
    ws["C4"].value = f"< {t31} %"
    ws["D4"].value = f"{t31}– {t32} %"
    ws["E4"].value = f"{t32} – {t33} %"
    ws["F4"].value = f">{t33} %"

    ws["B5"].value = "4 диспетчера"
    ws["C5"].value = f"< {t41} %"
    ws["D5"].value = f"{t41} – {t42} %"
    ws["E5"].value = f"{t42} – {t43} %"
    ws["F5"].value = f">{t43} %"

    ws["B6"].value = "5 диспетчеров"
    ws["C6"].value = f"< {t51} %"
    ws["D6"].value = f"{t51} – {t52} %"
    ws["E6"].value = f"{t52} – {t53} %"
    ws["F6"].value = f">{t53} %"

    for r in range(3, 7):
        for c in range(2, 7):
            cell = ws.cell(r, c)
            cell.alignment = center
            cell.border = border
            cell.font = Font(size=10, bold=(r == 3))

    # Formula note (so the sheet always shows the exact rule used)
    ws.merge_cells(start_row=7, start_column=2, end_row=8, end_column=10)
    formula_note = "".join(
        [
            "Формула: % = (тревоги оператора * 100) / (все тревоги смены). ",
            "Выплата определяется по порогам выше (по числу диспетчеров в смену).\n",
            f"Границы смен: день с {dayStart or '08:00'}, ночь с {nightStart or '20:00'}. ",
            f"Отработка тревоги: действие '{actionName or ''}'. ",
            f"Диспетчеры в смену: {ds} (presence>= {int(minPresenceMinutes)} мин, grace {int(presenceGraceMinutes)} мин). ",
            "ФИО скрыты. " if hideOperatorNames else "",
            "Сравнение presence/actions — на листе 'Контроль'.",
        ]
    )
    ws.cell(7, 2, clean_excel_text(formula_note)).alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    ws.cell(7, 2).font = Font(size=10)

    # Title
    ws.merge_cells(start_row=9, start_column=2, end_row=9, end_column=10)
    if (
        period_start_date.year == period_end_date.year
        and period_start_date.month == period_end_date.month
        and period_start_date.day == 1
    ):
        title = f"Ведомость учета работы операторов ПЦН за {period_start_date.strftime('%m.%Y')}г."
    else:
        title = (
            f"Ведомость учета работы операторов ПЦН за период {period_start_date.isoformat()}–{period_end_date.isoformat()}"
        )
    ws.cell(9, 2, clean_excel_text(title)).font = Font(bold=True, size=12)
    ws.cell(9, 2).alignment = Alignment(horizontal="center")

    ws.merge_cells(start_row=10, start_column=2, end_row=10, end_column=10)
    scope_bits = [f"Оператор: {operatorQuery.strip()}" if (operatorQuery or "").strip() else "Оператор: все"]
    if hideOperatorNames:
        scope_bits.append("ФИО скрыты")
    ws.cell(10, 2, clean_excel_text(" | ".join(scope_bits))).alignment = Alignment(horizontal="center")
    ws.cell(10, 2).font = Font(size=10, italic=True)

    headers = [
        "Дата",
        "Количество диспетчеров в смену",
        "Смена",
        "ФИО",
        "Тревоги",
        "%",
        "Сумма",
        "Доплата",
        "Всего в смену, руб.",
    ]

    start_row = 12
    for idx, h in enumerate(headers, start=2):
        cell = ws.cell(start_row, idx, clean_excel_text(h))
        cell.font = Font(bold=True)
        cell.alignment = center
        cell.border = border

    cur = start_row + 1
    # Group by shift
    from collections import defaultdict

    grouped: dict[tuple[date_type, str], list[dict[str, object]]] = defaultdict(list)
    for r in out_rows:
        grouped[(r["date"], r["shift"])].append(r)

    for sd, sh in ordered_shifts:
        items = grouped.get((sd, sh)) or []
        if not items:
            continue

        # Operator rows
        total_alarms = sum(int(x.get("alarms") or 0) for x in items)
        total_payout = sum(int(x.get("payout") or 0) for x in items)
        total_bonus = sum(int(x.get("bonus") or 0) for x in items)
        total_total = sum(int(x.get("total") or 0) for x in items)

        for i, x in enumerate(items):
            ws.cell(cur, 2, sd).number_format = "DD.MM.YYYY" if i == 0 else ""
            ws.cell(cur, 3, int(x.get("dispatchers") or 0) if i == 0 else "")
            ws.cell(cur, 4, sh if i == 0 else "")
            ws.cell(cur, 5, "" if hideOperatorNames else clean_excel_text(x.get("operator")))
            ws.cell(cur, 6, int(x.get("alarms") or 0))
            ws.cell(cur, 7, float(x.get("percent") or 0.0))
            ws.cell(cur, 7).number_format = "0.00"
            ws.cell(cur, 8, int(x.get("payout") or 0))
            ws.cell(cur, 9, int(x.get("bonus") or 0))
            ws.cell(cur, 10, int(x.get("total") or 0))

            for col in range(2, 11):
                cell = ws.cell(cur, col)
                cell.border = border
                cell.alignment = center if col != 5 else Alignment(horizontal="left", vertical="center")
            cur += 1

        # Summary row
        ws.cell(cur, 3, "Всего в смену:").font = Font(bold=True)
        ws.cell(cur, 6, int(total_alarms)).font = Font(bold=True)
        ws.cell(cur, 8, int(total_payout)).font = Font(bold=True)
        ws.cell(cur, 9, int(total_bonus)).font = Font(bold=True)
        ws.cell(cur, 10, int(total_total)).font = Font(bold=True)
        for col in range(2, 11):
            ws.cell(cur, col).border = border
            ws.cell(cur, col).alignment = center if col != 5 else Alignment(horizontal="left", vertical="center")
        cur += 1

    # Column widths (approx)
    ws.column_dimensions["B"].width = 12
    ws.column_dimensions["C"].width = 18
    ws.column_dimensions["D"].width = 10
    ws.column_dimensions["E"].width = 26
    ws.column_dimensions["F"].width = 10
    ws.column_dimensions["G"].width = 8
    ws.column_dimensions["H"].width = 10
    ws.column_dimensions["I"].width = 12
    ws.column_dimensions["J"].width = 16

    # Control sheet: compare dispatcher counts from presence vs from actions
    try:
        ws2 = wb.create_sheet("Контроль")
        ws2_headers = [
            "Дата",
            "Смена",
            "Всего тревог",
            "Диспетчеры (presence)",
            "Диспетчеры (actions)",
            "Использовано",
        ]
        for idx, h in enumerate(ws2_headers, start=1):
            cell = ws2.cell(1, idx, clean_excel_text(h))
            cell.font = Font(bold=True)
            cell.alignment = center
            cell.border = border

        r = 2
        for x in control_rows:
            sd = x.get("date")
            ws2.cell(r, 1, sd).number_format = "DD.MM.YYYY"
            ws2.cell(r, 2, clean_excel_text(x.get("shift")))
            ws2.cell(r, 3, int(x.get("totalAlarms") or 0))
            ws2.cell(r, 4, int(x.get("dispatchersPresence") or 0))
            ws2.cell(r, 5, int(x.get("dispatchersActions") or 0))
            ws2.cell(r, 6, int(x.get("dispatchersUsed") or 0))
            for col in range(1, 7):
                c = ws2.cell(r, col)
                c.border = border
                c.alignment = center
            r += 1

        ws2.column_dimensions["A"].width = 12
        ws2.column_dimensions["B"].width = 10
        ws2.column_dimensions["C"].width = 12
        ws2.column_dimensions["D"].width = 20
        ws2.column_dimensions["E"].width = 18
        ws2.column_dimensions["F"].width = 14
    except Exception:
        # If something goes wrong, do not fail the report generation.
        pass

    bio = BytesIO()
    wb.save(bio)
    data = bio.getvalue()

    report_id = str(uuid4())
    ps = period_start_date.isoformat()
    pe = period_end_date.isoformat()
    filename = f"pcn-ledger-{ps}-{pe}.xlsx"
    path = _write_report_file(report_id, filename, data)

    r = Report(
        id=report_id,
        type="pcnLedger",
        period_start=ps,
        period_end=pe,
        generated_at=datetime.utcnow().isoformat(timespec="seconds"),
        status="generated",
        events_count=sum(int(v or 0) for v in shift_totals.values()) if shift_totals else 0,
        critical_count=0,
        file_name=filename,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        storage_path=str(path),
        params_json=json.dumps(
            {
                "dateFrom": dateFrom,
                "dateTo": dateTo,
                "dayStart": dayStart,
                "nightStart": nightStart,
                "actionName": actionName,
                "operatorQuery": operatorQuery,
                "hideOperatorNames": hideOperatorNames,
                "payouts": {"pay0": pay0, "pay1": pay1, "pay2": pay2, "pay3": pay3},
                "thresholds": {
                    "3": [thr3_1, thr3_2, thr3_3],
                    "4": [thr4_1, thr4_2, thr4_3],
                    "5": [thr5_1, thr5_2, thr5_3],
                },
                "bonusDefault": bonusDefault,
                "bonusOverride": bonusOverride or [],
                "includePresenceOnly": includePresenceOnly,
                "dispatchersSource": dispatchersSource,
                "minPresenceMinutes": minPresenceMinutes,
                "presenceGraceMinutes": presenceGraceMinutes,
            },
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
    format: str | None = Query(default=None, description="csv|xlsx"),
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

    resolved = _resolve_and_validate_store_path(str(r.storage_path))

    requested = (format or "").strip().lower() or None
    if requested not in {None, "xlsx"}:
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Invalid format"})

    stored_ext = _file_ext(r.file_name)
    # Always return XLSX to users.
    if stored_ext == "xlsx":
        return FileResponse(
            path=str(resolved),
            media_type=r.mime_type or "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=r.file_name,
        )

    src = resolved.read_bytes()
    if stored_ext == "csv":
        out = _csv_bytes_to_xlsx_bytes(src)
        filename = (r.file_name.rsplit(".", 1)[0] + ".xlsx") if r.file_name else "report.xlsx"
        return Response(
            content=out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    # fallback: return as is
    media = r.mime_type or "application/octet-stream"
    return FileResponse(
        path=str(resolved),
        media_type=media,
        filename=r.file_name,
    )


@router.delete("/{report_id}")
async def delete_report(
    report_id: str,
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> Response:
    _ensure_reports_manage_perm(current)

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

    if r.storage_path:
        try:
            resolved = _resolve_and_validate_store_path(str(r.storage_path))
            resolved.unlink(missing_ok=True)
        except HTTPException:
            # If file is missing/bad path, still allow deleting DB record.
            pass
        except Exception:
            pass

    await session.delete(r)
    await session.commit()
    return Response(status_code=204)


@router.get("/{report_id}/preview")
async def preview_report(
    report_id: str,
    maxRows: int = Query(200, ge=1, le=5000, description="Max rows for table preview"),
    maxCols: int = Query(50, ge=1, le=200, description="Max cols for table preview"),
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> dict:
    r = (
        await session.execute(select(Report).where(Report.id == report_id).limit(1))
    ).scalars().first()
    if r is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Report not found"})

    # Special preview for analytics-based GBR report (old behavior)
    if str(r.type) == "gbrRaportXlsx":
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

        out = await gbr_trips(
            date_from=date_from,
            date_to=date_to,
            gbr_name=(str(gbr_name) if gbr_name else None),
            object_id=(str(object_id) if object_id else None),
            limit=2000,
            offset=0,
            session=session,
            _perm=current,
        )
        out["kind"] = "gbr"
        return out

    # Generic preview for stored files (CSV/XLSX)
    if not r.storage_path or not r.file_name:
        raise HTTPException(status_code=409, detail={"code": "NO_FILE", "message": "Report has no stored file"})

    resolved = _resolve_and_validate_store_path(str(r.storage_path))
    content = resolved.read_bytes()
    ext = _file_ext(r.file_name) or ("csv" if (r.mime_type or "").startswith("text/csv") else "")

    if ext == "csv":
        return _preview_table_from_csv_bytes(content, max_rows=int(maxRows))
    if ext == "xlsx":
        return _preview_table_from_xlsx_bytes(content, max_rows=int(maxRows), max_cols=int(maxCols))

    raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": "Preview not supported"})


@router.get("/export/daily", include_in_schema=False)
async def export_daily(
    date: str = Query(default_factory=today_str, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    raise HTTPException(
        status_code=410,
        detail={
            "code": "DISABLED",
            "message": "Суточный отчёт отключён. Формируйте отчёты только по согласованным событиям/объектам.",
        },
    )

    content = await export_daily_report_csv(session=session, date=date)
    xlsx = _csv_bytes_to_xlsx_bytes(content)
    filename = f"daily-report-{date}.xlsx"
    return Response(
        content=xlsx,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/daily/xlsx", include_in_schema=False)
async def export_daily_xlsx(
    date: str = Query(default_factory=today_str, description="YYYY-MM-DD"),
    session: AsyncSession = Depends(get_session),
) -> Response:
    return await export_daily(date=date, session=session)


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

    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Фразы"

    headers = [
        "Номер объекта",
        "Название объекта",
        "Адрес",
        phraseA,
        phraseB,
        "Примечание",
    ]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for object_id, object_name, address, c_a, c_b in rows:
        ws.append(
            [
                object_id or "",
                object_name or "",
                address or "",
                int(c_a or 0),
                int(c_b or 0),
                "",
            ]
        )

    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 14
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 50
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 18
    ws.column_dimensions["F"].width = 20

    out = BytesIO()
    wb.save(out)
    content = out.getvalue()
    y = str(year) if year is not None else "custom"
    safe_client = client.replace('"', "").replace("'", "").strip() or "all"
    filename = f"phrase-counts-{y}-{safe_client}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
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
    """XLSX: по выбранному коду события — сколько раз и по каким объектам за период."""
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

    base_stmt = (
        select(
            Event.id.label("event_id"),
            Event.object_id.label("object_id"),
            obj_name.label("object_name"),
            obj_addr.label("address"),
            Event.timestamp.label("timestamp"),
            Event.result_text.label("result_text"),
            Event.meter_count.label("meter_count"),
        )
        .select_from(Event)
        .outerjoin(Object, Object.id == Event.object_id)
        .where(where)
    )
    base = base_stmt.subquery("base")

    agg_stmt = (
        select(
            base.c.object_id,
            base.c.object_name,
            base.c.address,
            func.count().label("events_count"),
            func.min(base.c.timestamp).label("first_time"),
            func.max(base.c.timestamp).label("last_time"),
        )
        .group_by(base.c.object_id, base.c.object_name, base.c.address)
        .order_by(base.c.object_name.asc())
        .limit(limit)
    )
    agg = agg_stmt.subquery("agg")

    rn_stmt = select(
        base.c.object_id.label("object_id"),
        base.c.event_id.label("event_id"),
        base.c.result_text.label("result_text"),
        base.c.meter_count.label("meter_count"),
        base.c.timestamp.label("timestamp"),
        func.row_number().over(partition_by=base.c.object_id, order_by=base.c.timestamp.desc()).label("rn"),
    )
    rn = rn_stmt.subquery("rn")
    last_note = (
        select(
            rn.c.object_id.label("object_id"),
            rn.c.event_id.label("last_event_id"),
            rn.c.result_text.label("last_result_text"),
            rn.c.meter_count.label("last_meter_count"),
        )
        .where(rn.c.rn == 1)
        .subquery("last_note")
    )

    stmt = (
        select(
            agg.c.object_id,
            agg.c.object_name,
            agg.c.address,
            agg.c.events_count,
            agg.c.first_time,
            agg.c.last_time,
            last_note.c.last_event_id,
            last_note.c.last_meter_count,
            last_note.c.last_result_text,
        )
        .select_from(agg)
        .outerjoin(last_note, last_note.c.object_id == agg.c.object_id)
        .order_by(agg.c.object_name.asc())
    )

    rows = (await session.execute(stmt)).all()

    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    wb = Workbook()
    ws = wb.active
    ws.title = "Объекты"

    headers = [
        "Код события",
        "Номер объекта",
        "Название объекта",
        "Адрес",
        "Количество событий",
        "Первое срабатывание",
        "Последнее срабатывание",
        "ID события (аг.)",
        "Параметр (MeterCount)",
        "Комментарий оператора (Result_Text)",
    ]
    ws.append(headers)
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    for object_id, object_name, address, events_count, first_time, last_time, last_event_id, last_meter_count, last_result_text in rows:
        ws.append(
            [
                eventCode,
                object_id or "",
                object_name or "",
                address or "",
                int(events_count or 0),
                first_time.isoformat() if first_time else "",
                last_time.isoformat() if last_time else "",
                _agency_event_id(last_event_id) or "",
                last_meter_count or "",
                last_result_text or "",
            ]
        )

    ws.freeze_panes = "A2"
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 40
    ws.column_dimensions["D"].width = 50
    ws.column_dimensions["E"].width = 20
    ws.column_dimensions["F"].width = 22
    ws.column_dimensions["G"].width = 22
    ws.column_dimensions["H"].width = 16
    ws.column_dimensions["I"].width = 32
    ws.column_dimensions["J"].width = 35

    out = BytesIO()
    wb.save(out)
    content = out.getvalue()
    safe_code = eventCode.replace("/", "_").replace("\\", "_")
    filename = f"objects-by-code-{safe_code}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/objects-by-code/xlsx")
async def export_objects_by_code_xlsx(
    eventCode: str = Query(min_length=1, max_length=16, description="Код события, например E1001"),
    dateFrom: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    dateTo: str | None = Query(default=None, description="ISO datetime или YYYY-MM-DD"),
    year: int | None = Query(default=None, ge=1970, le=2100, description="Год (если указан — задаёт период)"),
    clientName: str | None = Query(default=None, description="Контрагент/клиент (поиск по подстроке)"),
    objectQuery: str | None = Query(default=None, description="Поиск по объекту/адресу/ID"),
    limit: int = Query(default=50000, ge=1, le=200000),
    session: AsyncSession = Depends(get_session),
) -> Response:
    return await export_objects_by_code(
        eventCode=eventCode,
        dateFrom=dateFrom,
        dateTo=dateTo,
        year=year,
        clientName=clientName,
        objectQuery=objectQuery,
        limit=limit,
        session=session,
    )
