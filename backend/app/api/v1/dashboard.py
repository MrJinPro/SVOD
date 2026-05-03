from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, not_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.object import Object

router = APIRouter(prefix="/dashboard")


def _day_bounds(day: date_type) -> tuple[datetime, datetime]:
    dt_from = datetime.combine(day, datetime.min.time())
    dt_to = datetime.combine(day, datetime.max.time())
    return dt_from, dt_to


def _trend_percent(today: int, yesterday: int) -> float:
    if yesterday:
        return ((today - yesterday) / yesterday) * 100.0
    if today:
        return 100.0
    return 0.0


def _coerce_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None
    return None


def _db_dt_value(session: AsyncSession, value: datetime) -> datetime | str:
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
        if getattr(dialect, "name", None) == "sqlite":
            return value.strftime("%Y-%m-%d %H:%M:%S.%f")
    except Exception:
        pass
    return value


def _is_sqlite(session: AsyncSession) -> bool:
    try:
        bind = session.get_bind()
        dialect = getattr(bind, "dialect", None)
        return getattr(dialect, "name", None) == "sqlite"
    except Exception:
        return False


async def _get_reference_day_and_ts(session: AsyncSession) -> tuple[date_type, datetime | None]:
    # Avoid func.max() here: some DBs/dialects can return non-datetime values.
    latest_ts = (
        await session.execute(select(Event.timestamp).order_by(Event.timestamp.desc()).limit(1))
    ).scalar_one_or_none()
    dt = _coerce_dt(latest_ts)
    if dt is not None:
        return dt.date(), dt
    return date_type.today(), None


@router.get("/stats")
async def dashboard_stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Stats for dashboard cards.

    - totalEvents: events count for *today* (calendar day)
    - eventsTrend: % change vs yesterday (calendar day)
    - criticalEvents: critical events that still require attention (active/pending)
    - activeObjects: objects under guard (not disabled, not terminated prefixes)
    - reportsGenerated: number of days with events for last 7 days (incl. today)
    """

    # Use the most recent day present in events as reference.
    ref_day, max_ts = await _get_reference_day_and_ts(session)
    prev_day = ref_day - timedelta(days=1)
    dt_from, dt_to = _day_bounds(ref_day)
    y_from, y_to = _day_bounds(prev_day)
    dt_from_db = _db_dt_value(session, dt_from)
    dt_to_db = _db_dt_value(session, dt_to)
    y_from_db = _db_dt_value(session, y_from)
    y_to_db = _db_dt_value(session, y_to)
    ref_day_str = ref_day.isoformat()
    prev_day_str = prev_day.isoformat()

    alarm_id_expr = func.coalesce(Event.parent_event_id, Event.id)

    if _is_sqlite(session):
        total_today = (
            await session.execute(
                text(
                    "SELECT count(DISTINCT coalesce(parent_event_id, id)) "
                    "FROM events WHERE date(timestamp) = :day"
                ),
                {"day": ref_day_str},
            )
        ).scalar_one()

        total_yesterday = (
            await session.execute(
                text(
                    "SELECT count(DISTINCT coalesce(parent_event_id, id)) "
                    "FROM events WHERE date(timestamp) = :day"
                ),
                {"day": prev_day_str},
            )
        ).scalar_one()

        critical_day = (
            await session.execute(
                text(
                    "SELECT count(DISTINCT coalesce(parent_event_id, id)) "
                    "FROM events WHERE severity = 'critical' AND date(timestamp) = :day"
                ),
                {"day": ref_day_str},
            )
        ).scalar_one()

        active_objects = (
            await session.execute(
                text(
                    "SELECT count(DISTINCT object_id) FROM events "
                    "WHERE object_id IS NOT NULL AND trim(object_id) <> '' "
                    "AND object_id NOT LIKE 'ID%' AND object_id NOT LIKE '*%'"
                )
            )
        ).scalar_one()

        reports_generated = (
            await session.execute(
                text(
                    "SELECT count(DISTINCT date(timestamp)) FROM events "
                    "WHERE date(timestamp) >= :date_from AND date(timestamp) <= :date_to"
                ),
                {
                    "date_from": week_from.date().isoformat(),
                    "date_to": week_to.date().isoformat(),
                },
            )
        ).scalar_one()

        trend = _trend_percent(int(total_today), int(total_yesterday))

        return {
            "totalEvents": int(total_today),
            "criticalEvents": int(critical_day),
            "activeObjects": int(active_objects),
            "reportsGenerated": int(reports_generated),
            "eventsTrend": round(float(trend), 1),
        }

    total_today = (
        await session.execute(
            select(func.count(func.distinct(alarm_id_expr)))
            .select_from(Event)
            .where(func.date(Event.timestamp) == ref_day_str)
        )
    ).scalar_one()

    total_yesterday = (
        await session.execute(
            select(func.count(func.distinct(alarm_id_expr)))
            .select_from(Event)
            .where(func.date(Event.timestamp) == prev_day_str)
        )
    ).scalar_one()

    # Critical events for the reference day.
    critical_day = (
        await session.execute(
            select(func.count(func.distinct(alarm_id_expr))).select_from(Event).where(
                Event.severity == "critical",
                func.date(Event.timestamp) == ref_day_str,
            )
        )
    ).scalar_one()

    active_objects = (
        await session.execute(
            select(func.count()).select_from(Object).where(
                Object.disabled.is_(False),
                not_(Object.id.ilike("ID%")),
                not_(Object.id.like("*%")),
            )
        )
    ).scalar_one()
    if not int(active_objects or 0):
        active_objects = (
            await session.execute(
                select(func.count(func.distinct(Event.object_id))).select_from(Event).where(
                    Event.object_id.is_not(None),
                    Event.object_id != "",
                    not_(Event.object_id.ilike("ID%")),
                    not_(Event.object_id.like("*%")),
                )
            )
        ).scalar_one()

    week_from = datetime.combine(ref_day - timedelta(days=6), datetime.min.time())
    week_to = dt_to
    week_from_db = _db_dt_value(session, week_from)
    week_to_db = _db_dt_value(session, week_to)
    reports_generated = (
        await session.execute(
            select(func.count(func.distinct(func.date(Event.timestamp)))).where(
                func.date(Event.timestamp) >= week_from.date().isoformat(),
                func.date(Event.timestamp) <= week_to.date().isoformat(),
            )
        )
    ).scalar_one()

    trend = _trend_percent(int(total_today), int(total_yesterday))

    return {
        "totalEvents": int(total_today),
        "criticalEvents": int(critical_day),
        "activeObjects": int(active_objects),
        "reportsGenerated": int(reports_generated),
        "eventsTrend": round(float(trend), 1),
    }


@router.get("/charts/timeline")
async def dashboard_timeline(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    """Timeline of today's events grouped into 2-hour buckets (00:00..22:00)."""

    ref_day, _max_ts = await _get_reference_day_and_ts(session)
    dt_from, dt_to = _day_bounds(ref_day)
    dt_from_db = _db_dt_value(session, dt_from)
    dt_to_db = _db_dt_value(session, dt_to)
    ref_day_str = ref_day.isoformat()

    # Pre-fill buckets
    buckets: dict[int, dict[str, Any]] = {
        hour: {"time": f"{hour:02d}:00", "events": 0, "critical": 0} for hour in range(0, 24, 2)
    }

    alarm_id_expr = func.coalesce(Event.parent_event_id, Event.id)

    if _is_sqlite(session):
        rows = (
            await session.execute(
                text(
                    "SELECT timestamp, severity, coalesce(parent_event_id, id) AS alarm_id "
                    "FROM events WHERE date(timestamp) = :day"
                ),
                {"day": ref_day_str},
            )
        ).all()
    else:
        rows = (
            await session.execute(
                select(Event.timestamp, Event.severity, alarm_id_expr.label("alarm_id")).where(
                    func.date(Event.timestamp) == ref_day_str
                )
            )
        ).all()

    seen_by_bucket: dict[int, set[str]] = {hour: set() for hour in range(0, 24, 2)}
    crit_by_bucket: dict[int, set[str]] = {hour: set() for hour in range(0, 24, 2)}

    for ts, severity, alarm_id in rows:
        if not isinstance(ts, datetime):
            continue
        aid = str(alarm_id or "").strip()
        if not aid:
            continue
        bucket_hour = (int(ts.hour) // 2) * 2
        if bucket_hour not in buckets:
            continue
        if aid not in seen_by_bucket[bucket_hour]:
            seen_by_bucket[bucket_hour].add(aid)
            buckets[bucket_hour]["events"] += 1
        if severity == "critical" and aid not in crit_by_bucket[bucket_hour]:
            crit_by_bucket[bucket_hour].add(aid)
            buckets[bucket_hour]["critical"] += 1

    return [buckets[hour] for hour in sorted(buckets.keys())]


@router.get("/charts/by-type")
async def dashboard_by_type(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    """Distribution by Event.type for last 24 hours (rolling window)."""

    _ref_day, max_ts = await _get_reference_day_and_ts(session)
    window_end = max_ts or datetime.now()
    dt_from = window_end - timedelta(hours=24)
    dt_from_db = _db_dt_value(session, dt_from)
    window_end_db = _db_dt_value(session, window_end)

    alarm_id_expr = func.coalesce(Event.parent_event_id, Event.id)

    rows = (
        await session.execute(
            select(Event.type, func.count(func.distinct(alarm_id_expr)).label("cnt"))
            .where(Event.timestamp >= dt_from_db, Event.timestamp <= window_end_db)
            .group_by(Event.type)
            .order_by(func.count(func.distinct(alarm_id_expr)).desc())
        )
    ).all()

    name_map = {
        "alarm": "Тревоги",
        "intrusion": "Проникновения",
        "access": "Доступ",
        "patrol": "Обходы",
        "incident": "Инциденты",
        "maintenance": "Обслуживание",
    }

    palette = [
        "hsl(var(--severity-critical))",
        "hsl(var(--severity-warning))",
        "hsl(var(--severity-success))",
        "hsl(var(--primary))",
        "hsl(var(--muted-foreground))",
        "hsl(var(--foreground))",
    ]

    items = [(str(t or "(unknown)"), int(cnt or 0)) for (t, cnt) in rows]
    top_n = 6
    top = items[:top_n]
    rest_sum = sum(v for _, v in items[top_n:])

    out: list[dict[str, Any]] = []
    for idx, (t, cnt) in enumerate(top):
        out.append(
            {
                "name": name_map.get(t, t),
                "value": int(cnt),
                "color": palette[idx % len(palette)],
            }
        )

    if rest_sum:
        out.append(
            {
                "name": "Другое",
                "value": int(rest_sum),
                "color": "hsl(var(--muted-foreground))",
            }
        )

    return out
