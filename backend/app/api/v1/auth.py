from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.db.session import get_session
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User

router = APIRouter(prefix="/auth")


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str
    password: str
    email: str | None = None


class RefreshIn(BaseModel):
    refreshToken: str


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

    access_token = create_access_token(
        subject=str(user.id),
        role=str(user.role),
        expires_in_seconds=int(settings.access_token_ttl_seconds),
    )

    refresh_token = create_refresh_token(subject=str(user.id))
    refresh_payload = decode_token(refresh_token, expected_type="refresh")
    refresh_hash = hash_token(refresh_token, purpose="refresh")
    expires_at = datetime.utcfromtimestamp(int(refresh_payload.get("exp") or 0))
    session.add(
        RefreshToken(
            id=str(uuid4()),
            user_id=str(user.id),
            token_hash=refresh_hash,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            revoked_at=None,
            replaced_by_token_hash=None,
        )
    )
    await session.commit()
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
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

    email = (payload.email or "").strip() or None
    if email is not None:
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

    # RBAC link for new accounts
    operator_role = (
        await session.execute(select(Role).where(Role.code == "operator").limit(1))
    ).scalars().first()
    if operator_role is not None:
        user.roles.append(operator_role)

    session.add(user)
    await session.commit()

    access_token = create_access_token(
        subject=str(user.id),
        role=str(user.role),
        expires_in_seconds=int(settings.access_token_ttl_seconds),
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    refresh_payload = decode_token(refresh_token, expected_type="refresh")
    refresh_hash = hash_token(refresh_token, purpose="refresh")
    expires_at = datetime.utcfromtimestamp(int(refresh_payload.get("exp") or 0))
    session.add(
        RefreshToken(
            id=str(uuid4()),
            user_id=str(user.id),
            token_hash=refresh_hash,
            expires_at=expires_at,
            created_at=datetime.utcnow(),
            revoked_at=None,
            replaced_by_token_hash=None,
        )
    )
    await session.commit()
    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
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
        "roles": current.get("roles") or [],
        "permissions": current.get("permissions") or [],
    }


@router.post("/refresh")
async def refresh(payload: RefreshIn, session: AsyncSession = Depends(get_session)) -> dict:
    token = (payload.refreshToken or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Refresh token required"})

    try:
        decoded = decode_token(token, expected_type="refresh")
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    user_id = str(decoded.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    token_hash = hash_token(token, purpose="refresh")
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash).limit(1))
    ).scalars().first()
    if row is None or row.revoked_at is not None:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    now = datetime.utcnow()
    if row.expires_at <= now:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Token expired"})

    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "User not found"})

    # Rotate refresh token
    new_refresh = create_refresh_token(subject=str(user.id))
    new_decoded = decode_token(new_refresh, expected_type="refresh")
    new_hash = hash_token(new_refresh, purpose="refresh")
    new_expires = datetime.utcfromtimestamp(int(new_decoded.get("exp") or 0))

    row.revoked_at = now
    row.replaced_by_token_hash = new_hash

    session.add(
        RefreshToken(
            id=str(uuid4()),
            user_id=str(user.id),
            token_hash=new_hash,
            expires_at=new_expires,
            created_at=now,
            revoked_at=None,
            replaced_by_token_hash=None,
        )
    )

    access_token = create_access_token(
        subject=str(user.id),
        role=str(user.role),
        expires_in_seconds=int(settings.access_token_ttl_seconds),
    )
    await session.commit()

    return {"accessToken": access_token, "refreshToken": new_refresh, "tokenType": "bearer"}


@router.post("/logout")
async def logout(payload: RefreshIn, session: AsyncSession = Depends(get_session)) -> dict:
    token = (payload.refreshToken or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail={"code": "VALIDATION", "message": "Refresh token required"})

    token_hash = hash_token(token, purpose="refresh")
    row = (
        await session.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash).limit(1))
    ).scalars().first()
    if row is None:
        return {"status": "ok"}

    if row.revoked_at is None:
        row.revoked_at = datetime.utcnow()
        await session.commit()
    return {"status": "ok"}
