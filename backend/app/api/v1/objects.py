from __future__ import annotations

from datetime import date as date_type
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, and_, exists, func, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.object import Object, ObjectGroup, Responsible, ResponsiblePhone
from app.utils.search import query_needles, tokenize_query

router = APIRouter(prefix="/objects")


def _object_search_clause(search: str):
    token_clauses: list[Any] = []
    for token in tokenize_query(search):
        needles = query_needles(token)

        responsible_exists = exists(
            select(literal(1))
            .select_from(Responsible)
            .where(
                and_(
                    Responsible.object_id == Object.id,
                    or_(
                        *[
                            or_(Responsible.name.ilike(needle), Responsible.address.ilike(needle))
                            for needle in needles
                        ]
                    ),
                )
            )
        )
        phone_exists = exists(
            select(literal(1))
            .select_from(ResponsiblePhone)
            .join(Responsible, ResponsiblePhone.responsible_id == Responsible.id)
            .where(
                and_(
                    Responsible.object_id == Object.id,
                    or_(*[ResponsiblePhone.phone.ilike(needle) for needle in needles]),
                )
            )
        )
        group_exists = exists(
            select(literal(1))
            .select_from(ObjectGroup)
            .where(
                and_(
                    ObjectGroup.object_id == Object.id,
                    or_(*[ObjectGroup.name.ilike(needle) for needle in needles]),
                )
            )
        )

        like_clauses: list[Any] = []
        for needle in needles:
            like_clauses.extend(
                [
                    Object.id.ilike(needle),
                    Object.name.ilike(needle),
                    Object.address.ilike(needle),
                    Object.client_name.ilike(needle),
                    Object.remarks.ilike(needle),
                    Object.additional_info.ilike(needle),
                ]
            )

        token_clauses.append(or_(*like_clauses, responsible_exists, phone_exists, group_exists))

    return and_(*token_clauses) if token_clauses else None


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
    includeIdPrefix: bool = Query(
        False,
        description="Включать объекты, чей ID начинается с 'ID' (в агентской БД это часто расторгнутые)",
    ),
    includeStarPrefix: bool = Query(
        False,
        description="Включать объекты, чей ID начинается с '*' (в агентской БД это часто расторгнутые)",
    ),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    filters: list[Any] = []

    # By default, hide terminated/disabled objects.
    if not includeDisabled:
        # Backward compat: older DBs/imports may contain NULL in 'disabled'.
        # Consider NULL as "not disabled".
        filters.append(or_(Object.disabled.is_(False), Object.disabled.is_(None)))

    # In some deployments, terminated objects are stored with Panel_id like 'IDxxxxx'.
    if not includeIdPrefix:
        filters.append(not_(Object.id.ilike("ID%")))

    # In some deployments, terminated objects are stored with leading '*'.
    if not includeStarPrefix:
        filters.append(not_(Object.id.like("*%")))
    if search and search.strip():
        clause = _object_search_clause(search.strip())
        if clause is not None:
            filters.append(clause)

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

    # Добавим лёгкую статистику: последнее событие и кол-во за сегодня.
    # Важно: не делаем N+1 (по 2 запроса на объект) — это на больших данных выглядит как "вечная загрузка".
    today = date_type.today()
    dt_from = datetime.combine(today, datetime.min.time())
    dt_to = datetime.combine(today, datetime.max.time())

    obj_ids = [str(o.id) for o in rows]
    last_event_by_obj: dict[str, datetime] = {}
    today_cnt_by_obj: dict[str, int] = {}

    if obj_ids:
        last_rows = (
            await session.execute(
                select(Event.object_id, func.max(Event.timestamp).label("last_ts"))
                .where(Event.object_id.in_(obj_ids))
                .group_by(Event.object_id)
            )
        ).all()
        last_event_by_obj = {str(oid): ts for oid, ts in last_rows if oid and isinstance(ts, datetime)}

        today_rows = (
            await session.execute(
                select(Event.object_id, func.count().label("cnt"))
                .where(Event.object_id.in_(obj_ids))
                .where(Event.timestamp >= dt_from)
                .where(Event.timestamp <= dt_to)
                .group_by(Event.object_id)
            )
        ).all()
        today_cnt_by_obj = {str(oid): int(cnt or 0) for oid, cnt in today_rows if oid}

    out_items: list[dict[str, Any]] = []
    for obj in rows:
        last_event_ts = last_event_by_obj.get(str(obj.id))
        today_cnt = int(today_cnt_by_obj.get(str(obj.id), 0))
        out_items.append(
            {
                "id": obj.id,
                "name": obj.name,
                "address": obj.address,
                "clientName": obj.client_name,
                "disabled": bool(obj.disabled),
                "lastEventAt": last_event_ts.isoformat() if last_event_ts else None,
                "eventsToday": today_cnt,
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
            "code": getattr(e, "code", None),
            "codeText": getattr(e, "code_text", None),
            "stateName": getattr(e, "state_name", None),
            "resultText": getattr(e, "result_text", None),
            "meterCount": getattr(e, "meter_count", None),
            "timeMeterCount": (
                getattr(e, "time_meter_count", None).isoformat()
                if getattr(e, "time_meter_count", None) is not None
                else None
            ),
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
