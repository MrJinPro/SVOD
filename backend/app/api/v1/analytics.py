from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, extract, func, select
from sqlalchemy.sql import desc
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.v1.deps import require_permissions
from app.core.config import settings
from app.db.session import get_session
from app.models.event import Event
from app.models.event_action import EventAction

router = APIRouter(prefix="/analytics")


def _seconds_between(end_ts, start_ts):
    """Return duration in seconds between two timestamps.

    - SQLite: julianday() diff * 86400
    - Postgres: EXTRACT(EPOCH FROM (end - start))
    """

    if settings.database_url.lower().startswith("postgresql"):
        return extract("epoch", end_ts - start_ts)
    return (func.julianday(end_ts) - func.julianday(start_ts)) * 86400.0


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _csv_response(content: str, filename: str) -> Response:
    # Use UTF-8 BOM for Excel-friendly import in Windows environments.
    data = content.encode("utf-8-sig")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/operators/live")
async def operators_live(
    window_minutes: int = Query(60, ge=1, le=1440, alias="windowMinutes"),
    online_minutes: int = Query(10, ge=1, le=240, alias="onlineMinutes"),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> list[dict[str, Any]]:
    """Операторы в реальном времени (эффективность/онлайн).

    Источник: event_actions.

    Важно: "онлайн" вычисляется по последнему действию (event_actions.action_time)
    и порогу onlineMinutes.
    """

    now = datetime.utcnow()
    dt_window = now - timedelta(minutes=int(window_minutes))
    dt_15m = now - timedelta(minutes=15)
    dt_5m = now - timedelta(minutes=5)
    dt_base = now - timedelta(minutes=max(int(window_minutes), 15))

    operator_col = EventAction.operator_name

    # Last action per operator (time) -> join back to fetch name/computer.
    last_ts_sq = (
        select(
            operator_col.label("operator"),
            func.max(EventAction.action_time).label("lastActionAt"),
        )
        .where(operator_col.is_not(None))
        .group_by(operator_col)
        .subquery("last_ts")
    )

    last_rows_sq = (
        select(
            EventAction.operator_name.label("operator"),
            last_ts_sq.c.lastActionAt.label("lastActionAt"),
            EventAction.action_name.label("lastActionName"),
            EventAction.computer.label("computer"),
        )
        .select_from(EventAction)
        .join(
            last_ts_sq,
            and_(
                EventAction.operator_name == last_ts_sq.c.operator,
                EventAction.action_time == last_ts_sq.c.lastActionAt,
            ),
        )
        .subquery("last_rows")
    )

    last_sq = (
        select(
            last_rows_sq.c.operator,
            func.max(last_rows_sq.c.lastActionAt).label("lastActionAt"),
            func.max(last_rows_sq.c.lastActionName).label("lastActionName"),
            func.max(last_rows_sq.c.computer).label("computer"),
        )
        .group_by(last_rows_sq.c.operator)
        .subquery("last")
    )

    # Activity counters for the requested window + fixed short windows.
    actions_5m = func.sum(case((EventAction.action_time >= dt_5m, 1), else_=0)).label("actions5m")
    actions_15m = func.sum(case((EventAction.action_time >= dt_15m, 1), else_=0)).label("actions15m")
    actions_window = func.sum(case((EventAction.action_time >= dt_window, 1), else_=0)).label(
        "actionsWindow"
    )

    event_id_in_window = case((EventAction.action_time >= dt_window, EventAction.event_id), else_=None)
    events_window = func.count(func.distinct(event_id_in_window)).label("eventsWindow")

    counts_sq = (
        select(
            operator_col.label("operator"),
            actions_5m,
            actions_15m,
            actions_window,
            events_window,
        )
        .where(operator_col.is_not(None))
        .where(EventAction.action_time >= dt_base)
        .group_by(operator_col)
        .subquery("counts")
    )

    # Handling time: only events fully handled inside window.
    accept_ts = func.min(
        case(
            (EventAction.action_name.like("Прием%"), EventAction.action_time),
            else_=None,
        )
    ).label("accept_ts")
    end_ts = func.max(
        case(
            (EventAction.action_name == "Окончание обработки", EventAction.action_time),
            else_=None,
        )
    ).label("end_ts")

    per_event = (
        select(
            EventAction.event_id.label("event_id"),
            operator_col.label("operator"),
            accept_ts,
            end_ts,
        )
        .where(operator_col.is_not(None))
        .where(EventAction.action_time >= dt_window)
        .group_by(EventAction.event_id, operator_col)
    ).subquery("per_event")

    duration_seconds = _seconds_between(per_event.c.end_ts, per_event.c.accept_ts).label(
        "duration_seconds"
    )

    handling_sq = (
        select(
            per_event.c.operator.label("operator"),
            func.avg(duration_seconds).label("avgHandlingSeconds"),
            func.count().label("handledEvents"),
        )
        .where(per_event.c.accept_ts.is_not(None))
        .where(per_event.c.end_ts.is_not(None))
        .where(duration_seconds >= 0)
        .group_by(per_event.c.operator)
        .subquery("handling")
    )

    q = (
        select(
            last_sq.c.operator,
            last_sq.c.lastActionAt,
            last_sq.c.lastActionName,
            last_sq.c.computer,
            func.coalesce(counts_sq.c.actions5m, 0).label("actions5m"),
            func.coalesce(counts_sq.c.actions15m, 0).label("actions15m"),
            func.coalesce(counts_sq.c.actionsWindow, 0).label("actionsWindow"),
            func.coalesce(counts_sq.c.eventsWindow, 0).label("eventsWindow"),
            func.coalesce(handling_sq.c.avgHandlingSeconds, None).label("avgHandlingSeconds"),
            func.coalesce(handling_sq.c.handledEvents, 0).label("handledEvents"),
        )
        .select_from(last_sq)
        .outerjoin(counts_sq, counts_sq.c.operator == last_sq.c.operator)
        .outerjoin(handling_sq, handling_sq.c.operator == last_sq.c.operator)
        .order_by(desc(func.coalesce(counts_sq.c.actionsWindow, 0)))
    )

    rows = (await session.execute(q)).all()
    online_cutoff = now - timedelta(minutes=int(online_minutes))

    out: list[dict[str, Any]] = []
    for (
        operator,
        last_action_at,
        last_action_name,
        computer,
        actions5m,
        actions15m,
        actionsWindow,
        eventsWindow,
        avgHandlingSeconds,
        handledEvents,
    ) in rows:
        if not operator:
            continue

        last_dt: datetime | None = last_action_at if isinstance(last_action_at, datetime) else None
        seconds_since = None
        if last_dt is not None:
            seconds_since = int((now - last_dt).total_seconds())

        online = bool(last_dt is not None and last_dt >= online_cutoff)

        out.append(
            {
                "operator": operator,
                "computer": computer,
                "online": online,
                "lastActionAt": last_dt.isoformat() if last_dt else None,
                "lastActionName": last_action_name,
                "secondsSinceLastAction": seconds_since,
                "actions5m": int(actions5m or 0),
                "actions15m": int(actions15m or 0),
                "actionsWindow": int(actionsWindow or 0),
                "eventsWindow": int(eventsWindow or 0),
                "avgHandlingSeconds": float(avgHandlingSeconds) if avgHandlingSeconds is not None else None,
                "handledEvents": int(handledEvents or 0),
                "windowMinutes": int(window_minutes),
                "onlineMinutes": int(online_minutes),
            }
        )

    out.sort(key=lambda r: (1 if r.get("online") else 0, int(r.get("actionsWindow") or 0)), reverse=True)
    return out


@router.get("/operators/handling")
async def operators_handling_time(
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    operator: str | None = Query(None),
    gbr_name: str | None = Query(None, alias="gbrName"),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> list[dict[str, Any]]:
    """Оценка скорости обработки по операторам.

    Считаем для каждой пары (event_id, operator):
    - accept_time = min(action_time) для action_name, начинающегося с "Прием"
    - end_time = max(action_time) для action_name == "Окончание обработки"
    duration_seconds = end_time - accept_time

    Затем агрегируем по operator.
    """

    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)

    accept_ts = func.min(
        case(
            (EventAction.action_name.like("Прием%"), EventAction.action_time),
            else_=None,
        )
    ).label("accept_ts")

    end_ts = func.max(
        case(
            (EventAction.action_name == "Окончание обработки", EventAction.action_time),
            else_=None,
        )
    ).label("end_ts")

    per_event = (
        select(
            EventAction.event_id.label("event_id"),
            EventAction.operator_name.label("operator"),
            accept_ts,
            end_ts,
        )
        .group_by(EventAction.event_id, EventAction.operator_name)
    )

    if dt_from is not None:
        per_event = per_event.where(EventAction.action_time >= dt_from)
    if dt_to is not None:
        per_event = per_event.where(EventAction.action_time <= dt_to)
    if operator:
        per_event = per_event.where(EventAction.operator_name == operator)
    if gbr_name:
        per_event = per_event.where(EventAction.gbr_name == gbr_name)

    per_event_sq = per_event.subquery("per_event")

    duration_seconds = _seconds_between(per_event_sq.c.end_ts, per_event_sq.c.accept_ts).label(
        "duration_seconds"
    )

    agg = (
        select(
            per_event_sq.c.operator.label("operator"),
            func.count().label("events"),
            func.avg(duration_seconds).label("avgSeconds"),
            func.min(duration_seconds).label("minSeconds"),
            func.max(duration_seconds).label("maxSeconds"),
        )
        .where(per_event_sq.c.operator.is_not(None))
        .where(per_event_sq.c.accept_ts.is_not(None))
        .where(per_event_sq.c.end_ts.is_not(None))
        .where(duration_seconds >= 0)
        .group_by(per_event_sq.c.operator)
        .order_by(func.count().desc())
    )

    rows = (await session.execute(agg)).all()
    out: list[dict[str, Any]] = []
    for operator, events, avg_s, min_s, max_s in rows:
        out.append(
            {
                "operator": operator,
                "events": int(events or 0),
                "avgSeconds": float(avg_s or 0.0),
                "minSeconds": float(min_s or 0.0),
                "maxSeconds": float(max_s or 0.0),
            }
        )
    return out


@router.get("/filters")
async def analytics_filters(
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> dict[str, Any]:
    operators = (
        await session.execute(
            select(EventAction.operator_name)
            .where(EventAction.operator_name.is_not(None))
            .distinct()
            .order_by(EventAction.operator_name.asc())
        )
    ).scalars().all()

    action_names = (
        await session.execute(
            select(EventAction.action_name)
            .where(EventAction.action_name.is_not(None))
            .distinct()
            .order_by(EventAction.action_name.asc())
        )
    ).scalars().all()

    gbr_names = (
        await session.execute(
            select(EventAction.gbr_name)
            .where(EventAction.gbr_name.is_not(None))
            .distinct()
            .order_by(EventAction.gbr_name.asc())
        )
    ).scalars().all()

    min_ts, max_ts = (
        await session.execute(select(func.min(EventAction.action_time), func.max(EventAction.action_time)))
    ).one()

    return {
        "operators": [o for o in operators if o],
        "actionNames": [a for a in action_names if a],
        "gbrNames": [g for g in gbr_names if g],
        "dateMin": min_ts.isoformat() if isinstance(min_ts, datetime) else None,
        "dateMax": max_ts.isoformat() if isinstance(max_ts, datetime) else None,
    }


@router.get("/operators/activity")
async def operators_activity(
    bucket: str = Query("day", pattern="^(day|month)$"),
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    operator: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> list[dict[str, Any]]:
    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)

    # SQLite-friendly bucketing; for Postgres this still works in many cases but is not perfect.
    if bucket == "month":
        bucket_expr = func.strftime("%Y-%m", EventAction.action_time)
    else:
        bucket_expr = func.date(EventAction.action_time)

    q = (
        select(
            bucket_expr.label("bucket"),
            EventAction.operator_name.label("operator"),
            func.count().label("actions"),
        )
        .where(EventAction.operator_name.is_not(None))
        .group_by(bucket_expr, EventAction.operator_name)
        .order_by(bucket_expr.asc(), func.count().desc())
    )

    if dt_from is not None:
        q = q.where(EventAction.action_time >= dt_from)
    if dt_to is not None:
        q = q.where(EventAction.action_time <= dt_to)
    if operator:
        q = q.where(EventAction.operator_name == operator)

    rows = (await session.execute(q)).all()
    return [{"bucket": b, "operator": o, "actions": int(c or 0)} for (b, o, c) in rows]


@router.get("/gbr/trips")
async def gbr_trips(
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    gbr_name: str | None = Query(None, alias="gbrName"),
    object_id: str | None = Query(None, alias="objectId"),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> dict[str, Any]:
    """Отчёт по выездам ГБР.

    Строится из event_actions (eventservice) по действиям:
    - "Вызвана группа реагирования"
    - "Прибытие группы реагирования"
    - "Отмена вызова группы реагирования" (и похожие)

    Возвращает поездки (event_id + gbr_name) с временами и, если есть, объектом из таблицы events.
    """

    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)

    called_ts = func.min(
        case(
            (EventAction.action_name.like("Вызвана%"), EventAction.action_time),
            else_=None,
        )
    ).label("called_ts")
    arrived_ts = func.min(
        case(
            (EventAction.action_name.like("Прибытие%"), EventAction.action_time),
            else_=None,
        )
    ).label("arrived_ts")
    cancelled_ts = func.min(
        case(
            (EventAction.action_name.like("Отмена%"), EventAction.action_time),
            else_=None,
        )
    ).label("cancelled_ts")
    last_action_ts = func.max(EventAction.action_time).label("last_action_ts")

    base = (
        select(
            EventAction.event_id.label("event_id"),
            EventAction.gbr_name.label("gbr_name"),
            called_ts,
            arrived_ts,
            cancelled_ts,
            last_action_ts,
        )
        .where(EventAction.gbr_name.is_not(None))
        .group_by(EventAction.event_id, EventAction.gbr_name)
    )

    if dt_from is not None:
        base = base.where(EventAction.action_time >= dt_from)
    if dt_to is not None:
        base = base.where(EventAction.action_time <= dt_to)
    if gbr_name:
        base = base.where(EventAction.gbr_name == gbr_name)

    sq = base.subquery("gbr_trips")

    travel_seconds = _seconds_between(sq.c.arrived_ts, sq.c.called_ts).label("travel_seconds")

    q = (
        select(
            sq.c.event_id,
            sq.c.gbr_name,
            sq.c.called_ts,
            sq.c.arrived_ts,
            sq.c.cancelled_ts,
            sq.c.last_action_ts,
            Event.object_id,
            Event.object_name,
            Event.client_name,
            travel_seconds,
        )
        .select_from(sq)
        .outerjoin(Event, Event.id == sq.c.event_id)
        .where(sq.c.called_ts.is_not(None))
        .order_by(sq.c.called_ts.desc())
        .offset(offset)
        .limit(limit)
    )

    if object_id:
        q = q.where(Event.object_id == object_id)

    rows = (await session.execute(q)).all()
    items: list[dict[str, Any]] = []
    for (
        event_id,
        gbr,
        called,
        arrived,
        cancelled,
        last_action,
        obj_id,
        obj_name,
        client_name,
        travel_s,
    ) in rows:
        items.append(
            {
                "eventId": event_id,
                "gbrName": gbr,
                "calledAt": called.isoformat() if isinstance(called, datetime) else None,
                "arrivedAt": arrived.isoformat() if isinstance(arrived, datetime) else None,
                "cancelledAt": cancelled.isoformat() if isinstance(cancelled, datetime) else None,
                "lastActionAt": last_action.isoformat() if isinstance(last_action, datetime) else None,
                "objectId": obj_id,
                "objectName": obj_name,
                "clientName": client_name,
                "travelSeconds": float(travel_s) if travel_s is not None else None,
            }
        )

    # Count (for pagination) - count distinct pairs from the same grouped view.
    count_inner = (
        select(sq.c.event_id)
        .select_from(sq)
        .outerjoin(Event, Event.id == sq.c.event_id)
        .where(sq.c.called_ts.is_not(None))
    )
    if object_id:
        count_inner = count_inner.where(Event.object_id == object_id)
    count_q = select(func.count()).select_from(count_inner.subquery())
    total = (await session.execute(count_q)).scalar_one()

    return {"data": items, "total": int(total or 0), "limit": limit, "offset": offset}


@router.get("/gbr/trips/export")
async def gbr_trips_export_csv(
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    gbr_name: str | None = Query(None, alias="gbrName"),
    object_id: str | None = Query(None, alias="objectId"),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> Response:
    # Reuse the list endpoint logic with a high limit; export is for management reports.
    result = await gbr_trips(
        date_from=date_from,
        date_to=date_to,
        gbr_name=gbr_name,
        object_id=object_id,
        limit=2000,
        offset=0,
        session=session,
        _perm=_perm,
    )

    import csv
    import io

    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([
        "calledAt",
        "arrivedAt",
        "cancelledAt",
        "travelSeconds",
        "gbrName",
        "objectId",
        "objectName",
        "clientName",
        "eventId",
    ])
    for r in result.get("data") or []:
        w.writerow([
            r.get("calledAt") or "",
            r.get("arrivedAt") or "",
            r.get("cancelledAt") or "",
            "" if r.get("travelSeconds") is None else str(r.get("travelSeconds")),
            r.get("gbrName") or "",
            r.get("objectId") or "",
            r.get("objectName") or "",
            r.get("clientName") or "",
            r.get("eventId") or "",
        ])

    name = f"gbr-trips-{datetime.utcnow().date().isoformat()}.csv"
    return _csv_response(buf.getvalue(), name)


@router.get("/objects/events/summary")
async def object_events_summary(
    object_id: str = Query(..., alias="objectId"),
    date_from: str | None = Query(None, alias="dateFrom"),
    date_to: str | None = Query(None, alias="dateTo"),
    days: int | None = Query(None, ge=1, le=3650, description="Alternative to dateFrom/dateTo"),
    code: str | None = Query(None),
    code_group: int | None = Query(None, alias="codeGroup"),
    session: AsyncSession = Depends(get_session),
    _perm: Any = Depends(require_permissions("analytics:read")),
) -> dict[str, Any]:
    """Сводка по объекту за период: сколько событий/какие коды/статусы/серьёзность."""

    dt_from = _parse_dt(date_from)
    dt_to = _parse_dt(date_to)
    if days is not None and dt_from is None and dt_to is None:
        dt_to = datetime.utcnow()
        dt_from = dt_to - timedelta(days=int(days))

    filters: list[Any] = [Event.object_id == object_id]
    if dt_from is not None:
        filters.append(Event.timestamp >= dt_from)
    if dt_to is not None:
        filters.append(Event.timestamp <= dt_to)
    if code:
        filters.append(Event.code == code)
    if code_group is not None:
        filters.append(Event.code_group == int(code_group))

    where = and_(*filters) if filters else None

    total_q = select(func.count()).select_from(Event)
    if where is not None:
        total_q = total_q.where(where)
    total = (await session.execute(total_q)).scalar_one()

    by_sev_q = select(Event.severity, func.count()).select_from(Event)
    if where is not None:
        by_sev_q = by_sev_q.where(where)
    by_sev_q = by_sev_q.group_by(Event.severity)

    by_status_q = select(Event.status, func.count()).select_from(Event)
    if where is not None:
        by_status_q = by_status_q.where(where)
    by_status_q = by_status_q.group_by(Event.status)

    by_code_q = select(Event.code_group, Event.code, Event.code_text, func.count()).select_from(Event)
    if where is not None:
        by_code_q = by_code_q.where(where)
    by_code_q = by_code_q.group_by(Event.code_group, Event.code, Event.code_text).order_by(func.count().desc()).limit(200)

    by_sev = {str(k or ""): int(v or 0) for (k, v) in (await session.execute(by_sev_q)).all()}
    by_status = {str(k or ""): int(v or 0) for (k, v) in (await session.execute(by_status_q)).all()}
    by_code = [
        {"codeGroup": cg, "code": c, "codeText": ct, "count": int(cnt or 0)}
        for (cg, c, ct, cnt) in (await session.execute(by_code_q)).all()
    ]

    return {
        "objectId": object_id,
        "total": int(total or 0),
        "bySeverity": by_sev,
        "byStatus": by_status,
        "byCode": by_code,
    }
