from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.object import Object

router = APIRouter(prefix="/objects")


def _object_to_out(obj: Object) -> dict[str, Any]:
    return {
        "id": obj.id,
        "name": obj.name,
        "address": obj.address,
        "clientName": obj.client_name,
        "disabled": bool(obj.disabled),
        "remarks": obj.remarks,
        "additionalInfo": obj.additional_info,
        "latitude": obj.latitude,
        "longitude": obj.longitude,
        "createdAt": obj.created_at.isoformat() if obj.created_at else None,
        "updatedAt": obj.updated_at.isoformat() if obj.updated_at else None,
        "groups": [
            {
                "group": g.group_no,
                "name": g.name,
                "isOpen": g.is_open,
                "timeEvent": g.time_event.isoformat() if g.time_event else None,
            }
            for g in (obj.groups or [])
        ],
        "responsibles": [
            {
                "id": r.id,
                "name": r.name,
                "address": r.address,
                "group": r.group_no,
                "order": r.order_no,
                "phones": [p.phone for p in (r.phones or [])],
            }
            for r in (obj.responsibles or [])
        ],
    }


@router.get("")
async def list_objects(
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=500),
    search: str | None = None,
    includeDisabled: bool = Query(False, description="Включать расторгнутые/отключенные объекты"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filters: list[Any] = []

    # By default, hide terminated/disabled objects.
    if not includeDisabled:
        filters.append(Object.disabled.is_(False))
    if search and search.strip():
        needle = f"%{search.strip()}%"
        filters.append(
            or_(
                Object.id.ilike(needle),
                Object.name.ilike(needle),
                Object.address.ilike(needle),
                Object.client_name.ilike(needle),
            )
        )

    where = and_(*filters) if filters else None

    count_stmt = select(func.count()).select_from(Object)
    if where is not None:
        count_stmt = count_stmt.where(where)
    total = (await session.execute(count_stmt)).scalar_one()

    stmt: Select[tuple[Object]] = select(Object).order_by(Object.id.asc())
    if where is not None:
        stmt = stmt.where(where)
    stmt = stmt.offset((page - 1) * pageSize).limit(pageSize)

    rows = (await session.execute(stmt)).scalars().all()

    # Добавим лёгкую статистику: последние событие и кол-во за сегодня.
    today = date_type.today()
    dt_from = datetime.combine(today, datetime.min.time())
    dt_to = datetime.combine(today, datetime.max.time())
    out_items: list[dict[str, Any]] = []
    for obj in rows:
        last_event_ts = (
            await session.execute(
                select(func.max(Event.timestamp)).where(Event.object_id == obj.id)
            )
        ).scalar_one_or_none()
        today_cnt = (
            await session.execute(
                select(func.count()).select_from(Event).where(
                    Event.object_id == obj.id,
                    Event.timestamp >= dt_from,
                    Event.timestamp <= dt_to,
                )
            )
        ).scalar_one()
        out_items.append(
            {
                "id": obj.id,
                "name": obj.name,
                "address": obj.address,
                "clientName": obj.client_name,
                "disabled": bool(obj.disabled),
                "lastEventAt": last_event_ts.isoformat() if last_event_ts else None,
                "eventsToday": int(today_cnt),
            }
        )

    total_pages = (total + pageSize - 1) // pageSize if pageSize else 1
    return {
        "data": out_items,
        "total": int(total),
        "page": int(page),
        "pageSize": int(pageSize),
        "totalPages": int(total_pages),
    }


@router.get("/{object_id}")
async def get_object(
    object_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    obj = await session.get(Object, object_id)
    if not obj:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Object not found"})

    # Простая статистика
    last_event = (
        await session.execute(
            select(Event).where(Event.object_id == object_id).order_by(Event.timestamp.desc()).limit(1)
        )
    ).scalars().first()
    total_events = (
        await session.execute(select(func.count()).select_from(Event).where(Event.object_id == object_id))
    ).scalar_one()

    today = date_type.today()
    dt_from = datetime.combine(today, datetime.min.time())
    dt_to = datetime.combine(today, datetime.max.time())
    today_events = (
        await session.execute(
            select(func.count()).select_from(Event).where(
                Event.object_id == object_id,
                Event.timestamp >= dt_from,
                Event.timestamp <= dt_to,
            )
        )
    ).scalar_one()

    out = _object_to_out(obj)
    out["stats"] = {
        "eventsTotal": int(total_events),
        "eventsToday": int(today_events),
        "lastEventAt": last_event.timestamp.isoformat() if last_event else None,
    }
    return out


@router.get("/{object_id}/events")
async def list_object_events(
    object_id: str,
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    # reuse events pagination format
    total = (
        await session.execute(select(func.count()).select_from(Event).where(Event.object_id == object_id))
    ).scalar_one()

    stmt = (
        select(Event)
        .where(Event.object_id == object_id)
        .order_by(Event.timestamp.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
    )
    rows = (await session.execute(stmt)).scalars().all()

    items = [
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
    total_pages = (total + pageSize - 1) // pageSize if pageSize else 1
    return {
        "data": items,
        "total": int(total),
        "page": int(page),
        "pageSize": int(pageSize),
        "totalPages": int(total_pages),
    }
