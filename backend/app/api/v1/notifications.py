from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.session import get_session
from app.models.event import Event
from app.models.notification import NotificationClear, NotificationRead

router = APIRouter(prefix="/notifications")


@router.get("")
async def list_notifications(
    current: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    user_id = str(current.get("id") or "")

    cleared_before = (
        await session.execute(
            select(NotificationClear.cleared_before).where(NotificationClear.user_id == user_id).limit(1)
        )
    ).scalar_one_or_none()

    # Notifications are derived from real events.
    # We keep behavior close to the prototype: show latest critical/warning events.
    stmt = (
        select(Event)
        .where(Event.severity.in_(["critical", "warning"]))
        .order_by(Event.timestamp.desc())
        .limit(200)
    )
    if cleared_before is not None:
        stmt = stmt.where(Event.timestamp > cleared_before)

    events = (await session.execute(stmt)).scalars().all()
    if not events:
        return []

    event_ids = [e.id for e in events]
    read_rows = (
        await session.execute(
            select(NotificationRead.event_id)
            .where(NotificationRead.user_id == user_id)
            .where(NotificationRead.event_id.in_(event_ids))
        )
    ).all()
    read_set = {r[0] for r in read_rows}

    out: list[dict[str, Any]] = []
    for e in events:
        title = "Критическое событие" if e.severity == "critical" else "Предупреждение"
        msg = (e.description.splitlines()[0] if e.description else e.object_name) if e else ""
        out.append(
            {
                "id": e.id,
                "title": title,
                "message": msg,
                "severity": e.severity,
                "timestamp": e.timestamp.isoformat(),
                "read": e.id in read_set,
                "eventId": e.id,
            }
        )
    return out


@router.post("/mark-all-read")
async def mark_all_read(
    current: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user_id = str(current.get("id") or "")

    cleared_before = (
        await session.execute(
            select(NotificationClear.cleared_before).where(NotificationClear.user_id == user_id).limit(1)
        )
    ).scalar_one_or_none()

    stmt = select(Event.id).where(Event.severity.in_(["critical", "warning"]))
    if cleared_before is not None:
        stmt = stmt.where(Event.timestamp > cleared_before)
    stmt = stmt.order_by(Event.timestamp.desc()).limit(200)

    event_ids = [r[0] for r in (await session.execute(stmt)).all()]
    if not event_ids:
        return {"status": "ok", "marked": 0}

    existing = (
        await session.execute(
            select(NotificationRead.event_id)
            .where(NotificationRead.user_id == user_id)
            .where(NotificationRead.event_id.in_(event_ids))
        )
    ).all()
    existing_set = {r[0] for r in existing}

    now = datetime.utcnow()
    to_add = [
        NotificationRead(user_id=user_id, event_id=eid, read_at=now)
        for eid in event_ids
        if eid not in existing_set
    ]
    if to_add:
        session.add_all(to_add)
        await session.commit()
    return {"status": "ok", "marked": len(to_add)}


@router.delete("/clear")
async def clear_notifications(
    current: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user_id = str(current.get("id") or "")
    now = datetime.utcnow()

    row = (
        await session.execute(select(NotificationClear).where(NotificationClear.user_id == user_id).limit(1))
    ).scalars().first()
    if row is None:
        session.add(NotificationClear(user_id=user_id, cleared_before=now))
    else:
        row.cleared_before = now

    # Optional cleanup: drop read markers for old events.
    await session.execute(
        delete(NotificationRead)
        .where(NotificationRead.user_id == user_id)
        .where(NotificationRead.read_at < now)
    )

    await session.commit()
    return {"status": "ok"}
