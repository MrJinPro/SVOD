from __future__ import annotations

import csv
import io
from datetime import datetime
from datetime import date as date_type

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import Event


async def export_daily_report_csv(session: AsyncSession, date: str) -> bytes:
    """Экспорт суточного отчёта в CSV.

    На этапе MVP это простой выгрузочный формат (быстро и без внешних библиотек).
    Позже можно заменить на Excel/PDF, не меняя контракт эндпоинта.
    """
    # date: YYYY-MM-DD
    day = date_type.fromisoformat(date)
    dt_from = datetime.combine(day, datetime.min.time())
    dt_to = datetime.combine(day, datetime.max.time())

    out = io.StringIO()
    writer = csv.writer(out, delimiter=';')
    writer.writerow(
        [
            "id",
            "timestamp",
            "type",
            "objectName",
            "clientName",
            "severity",
            "status",
            "description",
            "location",
        ]
    )

    stmt = (
        select(Event)
        .where(Event.timestamp >= dt_from, Event.timestamp <= dt_to)
        .order_by(Event.timestamp.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()

    for e in rows:
        writer.writerow(
            [
                e.id,
                e.timestamp.isoformat(),
                e.type,
                e.object_name,
                e.client_name,
                e.severity,
                e.status,
                e.description,
                e.location or "",
            ]
        )

    return out.getvalue().encode("utf-8-sig")


def today_str() -> str:
    return date_type.today().isoformat()
