from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, exists, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.event import Event
from app.models.event_action import EventAction

router = APIRouter(prefix="/search")


_CYR_TO_LAT_CONFUSABLES = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "С": "C",
        "Е": "E",
        "Н": "H",
        "К": "K",
        "М": "M",
        "О": "O",
        "Р": "P",
        "Т": "T",
        "Х": "X",
        "У": "Y",
        "а": "a",
        "в": "b",
        "с": "c",
        "е": "e",
        "н": "h",
        "к": "k",
        "м": "m",
        "о": "o",
        "р": "p",
        "т": "t",
        "х": "x",
        "у": "y",
    }
)

_LAT_TO_CYR_CONFUSABLES = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
        "Y": "У",
        "a": "а",
        "b": "в",
        "c": "с",
        "e": "е",
        "h": "н",
        "k": "к",
        "m": "м",
        "o": "о",
        "p": "р",
        "t": "т",
        "x": "х",
        "y": "у",
    }
)


def _query_variants(value: str) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    v1 = raw
    v2 = raw.translate(_CYR_TO_LAT_CONFUSABLES)
    v3 = raw.translate(_LAT_TO_CYR_CONFUSABLES)
    out: list[str] = []
    for v in (v1, v2, v3):
        v = v.strip()
        if v and v not in out:
            out.append(v)
    return out


@router.get("/events")
async def search_events(
    q: str = Query("", min_length=0),
    limit: int = Query(200, ge=1, le=5000),
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
        variants = _query_variants(t)
        needles = [f"%{v}%" for v in variants]

        action_exists = exists(
            select(literal(1)).where(
                and_(
                    EventAction.event_id == Event.id,
                    or_(
                        *[
                            or_(
                                EventAction.action_name.ilike(n),
                                EventAction.operator_name.ilike(n),
                                EventAction.computer.ilike(n),
                                EventAction.gbr_name.ilike(n),
                            )
                            for n in needles
                        ],
                    ),
                )
            )
        )

        like_clauses = []
        for needle in needles:
            like_clauses.extend(
                [
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
                ]
            )

        token_clauses.append(or_(*like_clauses, action_exists))

    where_clause = and_(*token_clauses) if token_clauses else None
    stmt = select(Event)
    if where_clause is not None:
        stmt = stmt.where(where_clause)
    stmt = stmt.order_by(Event.timestamp.desc()).limit(limit)

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
