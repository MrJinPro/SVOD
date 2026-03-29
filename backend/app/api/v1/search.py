from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.event_action import EventAction
from app.models.object import Object, ObjectGroup, Responsible, ResponsiblePhone
from app.utils.search import query_needles, tokenize_query

router = APIRouter(prefix="/search")

def _event_to_out(event: Event) -> dict[str, Any]:
    return {
        "resultType": "event",
        "id": event.id,
        "timestamp": event.timestamp.isoformat(),
        "type": event.type,
        "objectId": event.object_id,
        "objectName": event.object_name,
        "clientName": event.client_name,
        "severity": event.severity,
        "status": event.status,
        "description": event.description,
        "location": event.location,
        "resultText": event.result_text,
        "operatorId": event.operator_id,
        "code": getattr(event, "code", None),
        "codeText": getattr(event, "code_text", None),
        "stateName": getattr(event, "state_name", None),
    }


def _object_to_out(obj: Object) -> dict[str, Any]:
    return {
        "resultType": "object",
        "id": obj.id,
        "name": obj.name,
        "address": obj.address,
        "clientName": obj.client_name,
        "disabled": bool(obj.disabled),
    }


def _event_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
        needles = query_needles(token)

        action_exists = exists(
            select(literal(1)).where(
                and_(
                    EventAction.event_id == Event.id,
                    or_(
                        *[
                            or_(
                                EventAction.action_name.ilike(needle),
                                EventAction.operator_name.ilike(needle),
                                EventAction.computer.ilike(needle),
                                EventAction.gbr_name.ilike(needle),
                            )
                            for needle in needles
                        ]
                    ),
                )
            )
        )

        like_clauses = []
        for needle in needles:
            like_clauses.extend(
                [
                    Event.id.ilike(needle),
                    Event.object_id.ilike(needle),
                    Event.object_name.ilike(needle),
                    Event.client_name.ilike(needle),
                    Event.location.ilike(needle),
                    Event.description.ilike(needle),
                    Event.result_text.ilike(needle),
                    Event.code.ilike(needle),
                    Event.code_text.ilike(needle),
                    Event.state_name.ilike(needle),
                ]
            )

        token_clauses.append(or_(*like_clauses, action_exists))

    return and_(*token_clauses) if token_clauses else None


def _object_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
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

        like_clauses = []
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


@router.get("")
async def search_all(
    q: str = Query("", min_length=0),
    limitPerType: int = Query(25, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    raw = q.strip()
    if not raw:
        return {"query": "", "events": [], "objects": [], "total": 0}

    event_stmt = select(Event)
    event_where = _event_search_clause(raw)
    if event_where is not None:
        event_stmt = event_stmt.where(event_where)
    event_stmt = event_stmt.order_by(Event.timestamp.desc()).limit(limitPerType)

    object_stmt = select(Object)
    object_where = _object_search_clause(raw)
    if object_where is not None:
        object_stmt = object_stmt.where(object_where)
    object_stmt = object_stmt.order_by(Object.id.asc()).limit(limitPerType)

    events = (await session.execute(event_stmt)).scalars().all()
    objects = (await session.execute(object_stmt)).scalars().all()

    out_events = [_event_to_out(event) for event in events]
    out_objects = [_object_to_out(obj) for obj in objects]
    return {
        "query": raw,
        "events": out_events,
        "objects": out_objects,
        "total": len(out_events) + len(out_objects),
    }


@router.get("/events")
async def search_events(
    q: str = Query("", min_length=0),
    limit: int = Query(200, ge=1, le=5000),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    raw = q.strip()
    if not raw:
        return []

    where_clause = _event_search_clause(raw)
    stmt = select(Event)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.order_by(Event.timestamp.desc()).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    return [_event_to_out(event) for event in rows]
