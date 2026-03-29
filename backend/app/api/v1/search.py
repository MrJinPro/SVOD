from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, literal, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.event_action import EventAction
from app.models.object import Object, ObjectGroup, Responsible, ResponsiblePhone
from app.utils.search import (
    query_needles,
    query_prefix_needles,
    query_variants,
    should_search_related_text,
    should_use_light_search,
    tokenize_query,
)

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


def _event_direct_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
        variants = query_variants(token)
        prefix_needles = query_prefix_needles(token)
        contains_needles = query_needles(token)
        light_search = should_use_light_search(token)

        like_clauses = []
        for variant in variants:
            like_clauses.extend(
                [
                    Event.id == variant,
                    Event.object_id == variant,
                    Event.code == variant,
                ]
            )

        for needle in prefix_needles:
            like_clauses.extend(
                [
                    Event.id.ilike(needle),
                    Event.object_id.ilike(needle),
                    Event.object_name.ilike(needle),
                    Event.client_name.ilike(needle),
                    Event.code.ilike(needle),
                ]
            )

        if not light_search:
            for needle in contains_needles:
                like_clauses.extend(
                    [
                        Event.location.ilike(needle),
                        Event.description.ilike(needle),
                        Event.result_text.ilike(needle),
                        Event.code_text.ilike(needle),
                        Event.state_name.ilike(needle),
                    ]
                )

        token_clauses.append(or_(*like_clauses))

    return and_(*token_clauses) if token_clauses else None


def _event_related_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
        if not should_search_related_text(token):
            return None

        contains_needles = query_needles(token)
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
                            for needle in contains_needles
                        ]
                    ),
                )
            )
        )
        token_clauses.append(action_exists)

    return and_(*token_clauses) if token_clauses else None


def _object_direct_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
        variants = query_variants(token)
        prefix_needles = query_prefix_needles(token)
        contains_needles = query_needles(token)
        light_search = should_use_light_search(token)

        like_clauses = []
        for variant in variants:
            like_clauses.append(Object.id == variant)

        for needle in prefix_needles:
            like_clauses.extend(
                [
                    Object.id.ilike(needle),
                    Object.name.ilike(needle),
                    Object.address.ilike(needle),
                    Object.client_name.ilike(needle),
                ]
            )

        if not light_search:
            for needle in contains_needles:
                like_clauses.extend(
                    [
                        Object.remarks.ilike(needle),
                        Object.additional_info.ilike(needle),
                    ]
                )

        token_clauses.append(or_(*like_clauses))

    return and_(*token_clauses) if token_clauses else None


def _object_related_search_clause(raw: str):
    token_clauses = []
    for token in tokenize_query(raw):
        if not should_search_related_text(token):
            return None

        contains_needles = query_needles(token)
        responsible_exists = exists(
            select(literal(1))
            .select_from(Responsible)
            .where(
                and_(
                    Responsible.object_id == Object.id,
                    or_(
                        *[
                            or_(Responsible.name.ilike(needle), Responsible.address.ilike(needle))
                            for needle in contains_needles
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
                    or_(*[ResponsiblePhone.phone.ilike(needle) for needle in contains_needles]),
                )
            )
        )
        group_exists = exists(
            select(literal(1))
            .select_from(ObjectGroup)
            .where(
                and_(
                    ObjectGroup.object_id == Object.id,
                    or_(*[ObjectGroup.name.ilike(needle) for needle in contains_needles]),
                )
            )
        )
        token_clauses.append(or_(responsible_exists, phone_exists, group_exists))

    return and_(*token_clauses) if token_clauses else None


async def _search_events_fast_then_related(
    *,
    session: AsyncSession,
    raw: str,
    limit: int,
) -> list[Event]:
    events: list[Event] = []

    direct_clause = _event_direct_search_clause(raw)
    if direct_clause is not None:
        direct_stmt = select(Event).where(direct_clause).order_by(Event.timestamp.desc()).limit(limit)
        events = list((await session.execute(direct_stmt)).scalars().all())

    if len(events) >= limit:
        return events

    related_clause = _event_related_search_clause(raw)
    if related_clause is None:
        return events

    remaining = limit - len(events)
    existing_ids = [event.id for event in events]
    related_stmt = select(Event).where(related_clause)
    if existing_ids:
        related_stmt = related_stmt.where(not_(Event.id.in_(existing_ids)))
    related_stmt = related_stmt.order_by(Event.timestamp.desc()).limit(remaining)
    related_events = (await session.execute(related_stmt)).scalars().all()
    return [*events, *related_events]


async def _search_objects_fast_then_related(
    *,
    session: AsyncSession,
    raw: str,
    limit: int,
) -> list[Object]:
    objects: list[Object] = []

    direct_clause = _object_direct_search_clause(raw)
    if direct_clause is not None:
        direct_stmt = select(Object).where(direct_clause).order_by(Object.id.asc()).limit(limit)
        objects = list((await session.execute(direct_stmt)).scalars().all())

    if len(objects) >= limit:
        return objects

    related_clause = _object_related_search_clause(raw)
    if related_clause is None:
        return objects

    remaining = limit - len(objects)
    existing_ids = [obj.id for obj in objects]
    related_stmt = select(Object).where(related_clause)
    if existing_ids:
        related_stmt = related_stmt.where(not_(Object.id.in_(existing_ids)))
    related_stmt = related_stmt.order_by(Object.id.asc()).limit(remaining)
    related_objects = (await session.execute(related_stmt)).scalars().all()
    return [*objects, *related_objects]


@router.get("")
async def search_all(
    q: str = Query("", min_length=0),
    limitPerType: int = Query(25, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    raw = q.strip()
    if not raw:
        return {"query": "", "events": [], "objects": [], "total": 0}

    events = await _search_events_fast_then_related(session=session, raw=raw, limit=limitPerType)
    objects = await _search_objects_fast_then_related(session=session, raw=raw, limit=limitPerType)

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

    rows = await _search_events_fast_then_related(session=session, raw=raw, limit=limit)
    return [_event_to_out(event) for event in rows]
