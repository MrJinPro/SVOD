from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/auth")


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    email: str | None = None


@router.post("/login")
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)) -> dict:
    user = (
        await session.execute(select(User).where(User.username == payload.username).limit(1))
    ).scalars().first()
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Bad credentials"})

    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "User is inactive"})

    # Backward-compat: if password_hash is empty (старые записи),
    # разрешим вход по "password" и сразу мигрируем на хэш.
    if not user.password_hash:
        if payload.password != "password":
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Bad credentials"})
        user.password_hash = hash_password(payload.password)
    else:
        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Bad credentials"})

    user.last_login = datetime.utcnow().isoformat()
    await session.commit()

    token = create_access_token(subject=str(user.id), role=str(user.role))
    return {
        "accessToken": token,
        "tokenType": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "isActive": bool(user.is_active),
            "lastLogin": user.last_login,
        },
    }


@router.post("/register")
async def register(payload: RegisterIn, session: AsyncSession = Depends(get_session)) -> dict:
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Username is required"})

    existing = (
        await session.execute(select(User).where(User.username == username).limit(1))
    ).scalars().first()
    if existing is not None:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Username already exists"})

    email = (payload.email or "").strip() or f"{username}@svod.local"
    existing_email = (
        await session.execute(select(User).where(User.email == email).limit(1))
    ).scalars().first()
    if existing_email is not None:
        raise HTTPException(status_code=409, detail={"code": "CONFLICT", "message": "Email already exists"})

    import uuid

    user = User(
        id=str(uuid.uuid4()),
        username=username,
        email=email,
        role="operator",
        is_active=True,
        password_hash=hash_password(payload.password),
        last_login=None,
    )
    session.add(user)
    await session.commit()

    token = create_access_token(subject=str(user.id), role=str(user.role))
    return {
        "accessToken": token,
        "tokenType": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "isActive": bool(user.is_active),
            "lastLogin": user.last_login,
        },
    }


@router.get("/me")
async def me(
    current: dict = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    user_id = str(current.get("id") or "")
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "User not found"})
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "isActive": bool(user.is_active),
        "lastLogin": user.last_login,
    }
