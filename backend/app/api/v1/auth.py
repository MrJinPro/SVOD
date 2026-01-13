from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.db.session import get_session
from app.models.user import User

router = APIRouter(prefix="/auth")


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(payload: LoginIn, session: AsyncSession = Depends(get_session)) -> dict:
    # Прототипная авторизация: принимаем пароль "password" для пользователей из списка.
    if payload.password != "password":
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Bad credentials"})

    user = (
        await session.execute(select(User).where(User.username == payload.username).limit(1))
    ).scalars().first()
    if user is None:
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
