from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.session import get_session
from app.models.user_presence_session import UserPresenceSession

router = APIRouter(prefix="/presence")


class PresencePingIn(BaseModel):
    clientId: str
    computer: str | None = None


def _extract_client_ip(request: Request) -> str | None:
    # Prefer reverse-proxy header if present.
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",", 1)[0].strip() or None

    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client is not None else None
    return str(host) if host else None


@router.post("/ping")
async def presence_ping(
    payload: PresencePingIn,
    request: Request,
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> dict:
    """Heartbeat for operator presence.

    Creates or updates an "active" presence session for (user_id, clientId).
    """

    client_id = (payload.clientId or "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "clientId is required"})

    now = datetime.utcnow()
    user_id = str(current.get("id") or "").strip()
    username = str(current.get("username") or "").strip()
    if not user_id or not username:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "User not found"})

    computer = (payload.computer or "").strip() or None
    client_ip = _extract_client_ip(request)
    user_agent = (request.headers.get("user-agent") or "").strip() or None

    active = (
        (
            await session.execute(
                select(UserPresenceSession)
                .where(UserPresenceSession.user_id == user_id)
                .where(UserPresenceSession.client_id == client_id)
                .where(UserPresenceSession.ended_at.is_(None))
                .order_by(UserPresenceSession.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if active is None:
        active = UserPresenceSession(
            id=str(uuid4()),
            user_id=user_id,
            username=username,
            client_id=client_id,
            computer=computer,
            client_ip=client_ip,
            user_agent=user_agent,
            started_at=now,
            last_seen_at=now,
            ended_at=None,
            ended_reason=None,
        )
        session.add(active)
    else:
        active.last_seen_at = now
        active.username = username
        if computer is not None:
            active.computer = computer
        if client_ip is not None:
            active.client_ip = client_ip
        if user_agent is not None:
            active.user_agent = user_agent

    await session.commit()

    return {
        "id": str(active.id),
        "userId": str(active.user_id),
        "username": str(active.username),
        "clientId": str(active.client_id),
        "computer": active.computer,
        "clientIp": active.client_ip,
        "startedAt": active.started_at.isoformat(timespec="seconds"),
        "lastSeenAt": active.last_seen_at.isoformat(timespec="seconds"),
    }


class PresenceEndIn(BaseModel):
    clientId: str
    reason: str | None = None


@router.post("/end")
async def presence_end(
    payload: PresenceEndIn,
    session: AsyncSession = Depends(get_session),
    current: dict = Depends(get_current_user),
) -> dict:
    client_id = (payload.clientId or "").strip()
    if not client_id:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "clientId is required"})

    user_id = str(current.get("id") or "").strip()
    now = datetime.utcnow()

    active = (
        (
            await session.execute(
                select(UserPresenceSession)
                .where(UserPresenceSession.user_id == user_id)
                .where(UserPresenceSession.client_id == client_id)
                .where(UserPresenceSession.ended_at.is_(None))
                .order_by(UserPresenceSession.started_at.desc())
                .limit(1)
            )
        )
        .scalars()
        .first()
    )

    if active is None:
        return {"ok": True}

    active.ended_at = now
    active.ended_reason = (payload.reason or "client_end").strip() or "client_end"
    await session.commit()
    return {"ok": True}
