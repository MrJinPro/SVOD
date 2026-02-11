from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_permissions
from app.core.security import hash_password
from app.db.session import get_session
from app.models.role import Role
from app.models.user import User

router = APIRouter(prefix="/users")


def _user_out(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "isActive": bool(u.is_active),
        "lastLogin": u.last_login,
    }


class CreateUserIn(BaseModel):
    username: str
    password: str
    email: str | None = None
    role: str = "operator"
    isActive: bool = True


class UpdateUserIn(BaseModel):
    username: str | None = None
    email: str | None = None
    role: str | None = None
    isActive: bool | None = None


class SetPasswordIn(BaseModel):
    password: str


@router.get("")
async def list_users(
    current: dict = Depends(require_permissions("users:read")),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    rows = (await session.execute(select(User).order_by(User.username.asc()))).scalars().all()
    return [_user_out(u) for u in rows]


@router.post("")
async def create_user(
    payload: CreateUserIn,
    current: dict = Depends(require_permissions("users:write")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:

    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Username is required"})
    if not payload.password:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Password is required"})

    existing = (
        await session.execute(select(User).where(User.username == username).limit(1))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Username already exists"})

    email = (payload.email or "").strip() or None
    if email is not None:
        existing_email = (
            await session.execute(select(User).where(User.email == email).limit(1))
        ).scalars().first()
        if existing_email is not None:
            raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Email already exists"})

    role = payload.role or "operator"
    role = role.strip() or "operator"

    import uuid

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        role=role,
        is_active=bool(payload.isActive),
        password_hash=hash_password(payload.password),
        last_login=None,
    )

    r = (await session.execute(select(Role).where(Role.code == role).limit(1))).scalars().first()
    if r is None:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Unknown role code"})
    user.roles.append(r)

    session.add(user)
    await session.commit()
    return _user_out(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: str,
    payload: UpdateUserIn,
    current: dict = Depends(require_permissions("users:write")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})

    if payload.username is not None:
        username = payload.username.strip()
        if not username:
            raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Username is required"})
        if username != user.username:
            existing = (
                await session.execute(select(User).where(User.username == username).limit(1))
            ).scalars().first()
            if existing is not None:
                raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Username already exists"})
            user.username = username

    if payload.email is not None:
        email = payload.email.strip() or None
        if email != user.email:
            if email is not None:
                existing_email = (
                    await session.execute(select(User).where(User.email == email).limit(1))
                ).scalars().first()
                if existing_email is not None:
                    raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Email already exists"})
            user.email = email

    if payload.role is not None:
        role_code = payload.role.strip()
        if not role_code:
            raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Invalid role"})
        user.role = role_code
        r = (await session.execute(select(Role).where(Role.code == role_code).limit(1))).scalars().first()
        if r is not None and r not in user.roles:
            user.roles.append(r)

    if payload.isActive is not None:
        user.is_active = bool(payload.isActive)

    await session.commit()
    return _user_out(user)


@router.post("/{user_id}/password")
async def set_password(
    user_id: str,
    payload: SetPasswordIn,
    current: dict = Depends(require_permissions("users:write")),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "User not found"})
    if not payload.password:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Password is required"})

    user.password_hash = hash_password(payload.password)
    user.last_login = user.last_login  # keep
    await session.commit()
    return {"status": "ok", "updatedAt": datetime.utcnow().isoformat()}
