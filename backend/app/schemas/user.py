from __future__ import annotations

from pydantic import BaseModel


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    isActive: bool
    lastLogin: str | None = None


class TokenOut(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    user: UserOut
