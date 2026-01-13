from __future__ import annotations

from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.user import User

router = APIRouter()


def _day_bounds(day: date_type) -> tuple[datetime, datetime]:
    dt_from = datetime.combine(day, datetime.min.time())
    dt_to = datetime.combine(day, datetime.max.time())
    return dt_from, dt_to


@router.get("/dashboard/stats")
async def dashboard_stats(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:

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
    critical_today = (
        await session.execute(
            select(func.count()).select_from(Event).where(
                Event.timestamp >= dt_from,
                Event.timestamp <= dt_to,
                Event.severity == "critical",
            )
        )
    ).scalar_one()
    active_objects = (
        await session.execute(
            select(func.count(func.distinct(Event.object_name))).where(Event.timestamp >= dt_from, Event.timestamp <= dt_to)
        )
    ).scalar_one()

    # "Отчётов за неделю" — считаем как количество дней с событиями за 7 дней
    week_from = datetime.combine(today - timedelta(days=6), datetime.min.time())
    days_with_events = (
        await session.execute(
            select(func.count(func.distinct(func.date(Event.timestamp)))).where(Event.timestamp >= week_from)
        )
    ).scalar_one()

    trend = 0.0
    if total_yesterday:
        trend = ((total_today - total_yesterday) / total_yesterday) * 100
    elif total_today:
        trend = 100.0

    return {
        "totalEvents": int(total_today),
        "criticalEvents": int(critical_today),
        "activeObjects": int(active_objects),
        "reportsGenerated": int(days_with_events),
        "eventsTrend": round(float(trend), 1),
    }


@router.get("/dashboard/charts/timeline")
async def dashboard_timeline(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:

    today = date_type.today()
    dt_from, dt_to = _day_bounds(today)

    # 2-hour buckets like the mock
    out: list[dict[str, Any]] = []
    for hour in range(0, 24, 2):
        b_from = dt_from + timedelta(hours=hour)
        b_to = min(dt_to, b_from + timedelta(hours=2) - timedelta(microseconds=1))
        total = (
            await session.execute(
                select(func.count()).select_from(Event).where(Event.timestamp >= b_from, Event.timestamp <= b_to)
            )
        ).scalar_one()
        critical = (
            await session.execute(
                select(func.count()).select_from(Event).where(
                    Event.timestamp >= b_from,
                    Event.timestamp <= b_to,
                    Event.severity == "critical",
                )
            )
        ).scalar_one()
        out.append({"time": f"{hour:02d}:00", "events": int(total), "critical": int(critical)})
    return out


@router.get("/dashboard/charts/by-type")
async def dashboard_by_type(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:

    today = date_type.today()
    dt_from, dt_to = _day_bounds(today)
    rows = (
        await session.execute(
            select(Event.type, func.count().label("cnt"))
            .where(Event.timestamp >= dt_from, Event.timestamp <= dt_to)
            .group_by(Event.type)
            .order_by(func.count().desc())
        )
    ).all()

    # Keep the same token colors as in prototype data
    color_map = {
        "alarm": "hsl(var(--severity-warning))",
        "intrusion": "hsl(var(--severity-critical))",
        "access": "hsl(var(--severity-info))",
        "patrol": "hsl(var(--severity-success))",
        "incident": "hsl(var(--chart-5))",
        "maintenance": "hsl(var(--severity-info))",
    }
    name_map = {
        "alarm": "Тревоги",
        "intrusion": "Проникновения",
        "access": "Доступ",
        "patrol": "Обходы",
        "incident": "Инциденты",
        "maintenance": "Обслуживание",
    }

    return [
        {
            "name": name_map.get(t or "", t or "(unknown)"),
            "value": int(cnt),
            "color": color_map.get(t or "", "hsl(var(--chart-5))"),
        }
        for (t, cnt) in rows
    ]


@router.get("/notifications")
async def list_notifications(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:

    stmt = (
        select(Event)
        .where(Event.severity.in_(["critical", "warning"]))
        .order_by(Event.timestamp.desc())
        .limit(20)
    )
    events = (await session.execute(stmt)).scalars().all()

    out: list[dict[str, Any]] = []
    for e in events:
        title = "Критическое событие" if e.severity == "critical" else "Предупреждение"
        msg = e.description.splitlines()[0] if e.description else e.object_name
        out.append(
            {
                "id": e.id,
                "title": title,
                "message": msg,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat(),
                "read": False,
                "eventId": e.id,
            }
        )
    return out


@router.get("/users")
async def list_users(session: AsyncSession = Depends(get_session)) -> list[dict[str, Any]]:

    rows = (await session.execute(select(User).order_by(User.username.asc()))).scalars().all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "isActive": bool(u.is_active),
            "lastLogin": u.last_login,
        }
        for u in rows
    ]
