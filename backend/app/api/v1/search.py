from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.event_action import EventAction

router = APIRouter(prefix="/search")


@router.get("/events")
async def search_events(
    q: str = Query("", min_length=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    raw = q.strip()
    if not raw:
        return []

    # Smart search: split query into tokens and require every token to match
    # at least one field (event fields or related event_actions fields).
    # Example: "оповещён" will match operator notes (result_text).
    tokens = [t for t in raw.split() if t]
    tokens = tokens[:6]  # keep queries reasonably fast

    token_clauses = []
    for t in tokens:
        needle = f"%{t}%"

        action_exists = exists(
            select(literal(1)).where(
                and_(
                    EventAction.event_id == Event.id,
                    or_(
                        EventAction.action_name.ilike(needle),
                        EventAction.operator_name.ilike(needle),
                        EventAction.computer.ilike(needle),
                        EventAction.gbr_name.ilike(needle),
                    ),
                )
            )
        )

        token_clauses.append(
            or_(
                # Core event fields
                Event.id.ilike(needle),
                Event.object_id.ilike(needle),
                Event.object_name.ilike(needle),
                Event.client_name.ilike(needle),
                Event.location.ilike(needle),
                Event.description.ilike(needle),
                # Operator note / comment
                Event.result_text.ilike(needle),
                # Agency fields used in UI/reporting
                Event.code.ilike(needle),
                Event.code_text.ilike(needle),
                Event.state_name.ilike(needle),
                action_exists,
            )
        )

    where_clause = and_(*token_clauses) if token_clauses else None
    stmt = select(Event)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.order_by(Event.timestamp.desc()).limit(50)

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
            "resultText": e.result_text,
            "operatorId": e.operator_id,
        }
        for e in rows
    ]
