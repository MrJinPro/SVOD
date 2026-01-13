from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, func, select

from app.db.session import get_session
from app.services.report_service import export_daily_report_csv, today_str
from app.models.event import Event

router = APIRouter(prefix="/reports")


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
