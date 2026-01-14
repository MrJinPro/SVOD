from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, not_, select
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


@router.get("/stats")
async def dashboard_stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Stats for dashboard cards.

    - totalEvents: events count for *today* (calendar day)
    - eventsTrend: % change vs yesterday (calendar day)
    - criticalEvents: critical events that still require attention (active/pending)
    - activeObjects: objects under guard (not disabled, not terminated prefixes)
    - reportsGenerated: number of days with events for last 7 days (incl. today)
    """

    today = date_type.today()
    yesterday = today - timedelta(days=1)
    dt_from, dt_to = _day_bounds(today)
    y_from, y_to = _day_bounds(yesterday)

    total_today = (
        await session.execute(
            select(func.count()).select_from(Event).where(Event.timestamp >= dt_from, Event.timestamp <= dt_to)
        )
    ).scalar_one()

    total_yesterday = (
        await session.execute(
            select(func.count()).select_from(Event).where(Event.timestamp >= y_from, Event.timestamp <= y_to)
        )
    ).scalar_one()

    # Critical that require attention (not resolved)
    critical_open = (
        await session.execute(
            select(func.count()).select_from(Event).where(
                Event.severity == "critical",
                Event.status.in_(["active", "pending"]),
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

    week_from = datetime.combine(today - timedelta(days=6), datetime.min.time())
    reports_generated = (
        await session.execute(
            select(func.count(func.distinct(func.date(Event.timestamp)))).where(Event.timestamp >= week_from)
        )
    ).scalar_one()

    trend = _trend_percent(int(total_today), int(total_yesterday))

    return {
        "totalEvents": int(total_today),
        "criticalEvents": int(critical_open),
        "activeObjects": int(active_objects),
        "reportsGenerated": int(reports_generated),
        "eventsTrend": round(float(trend), 1),
    }


@router.get("/charts/timeline")
async def dashboard_timeline(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    """Timeline of today's events grouped into 2-hour buckets (00:00..22:00)."""

    today = date_type.today()
    dt_from, dt_to = _day_bounds(today)

    # Pre-fill buckets
    buckets: dict[int, dict[str, Any]] = {
        hour: {"time": f"{hour:02d}:00", "events": 0, "critical": 0} for hour in range(0, 24, 2)
    }

    rows = (
        await session.execute(
            select(Event.timestamp, Event.severity).where(and_(Event.timestamp >= dt_from, Event.timestamp <= dt_to))
        )
    ).all()

    for ts, severity in rows:
        if not isinstance(ts, datetime):
            continue
        bucket_hour = (int(ts.hour) // 2) * 2
        if bucket_hour not in buckets:
            continue
        buckets[bucket_hour]["events"] += 1
        if severity == "critical":
            buckets[bucket_hour]["critical"] += 1

    return [buckets[hour] for hour in sorted(buckets.keys())]


@router.get("/charts/by-type")
async def dashboard_by_type(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:
    """Distribution by Event.type for last 24 hours (rolling window)."""

    dt_from = datetime.now() - timedelta(hours=24)

    rows = (
        await session.execute(
            select(Event.type, func.count().label("cnt"))
            .where(Event.timestamp >= dt_from)
            .group_by(Event.type)
            .order_by(func.count().desc())
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
