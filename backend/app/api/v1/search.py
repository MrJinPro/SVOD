from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event

router = APIRouter(prefix="/search")


@router.get("/events")
async def search_events(
    q: str = Query("", min_length=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    if not q.strip():
        return []

    needle = f"%{q.strip()}%"
    stmt = (
        select(Event)
        .where(
            or_(
                Event.description.ilike(needle),
                Event.object_name.ilike(needle),
                Event.client_name.ilike(needle),
                Event.location.ilike(needle),
            )
        )
        .order_by(Event.timestamp.desc())
        .limit(50)
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat(),
            "type": e.type,
            "objectId": e.object_id,
            "objectName": e.object_name,
            "clientName": e.client_name,
            "severity": e.severity,
            "status": e.status,
            "description": e.description,
            "location": e.location,
            "operatorId": e.operator_id,
        }
        for e in rows
    ]
