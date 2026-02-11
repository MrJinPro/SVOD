from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.db.session import get_session
from app.models.role import Role
from app.models.user import User

security = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Missing token"})

    try:
        payload = decode_token(creds.credentials, expected_type="access")
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    user_id = str(payload.get("sub") or "")
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    user = (
        await session.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.id == user_id)
            .limit(1)
        )
    ).scalars().first()
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "User not found"})

    roles = [getattr(r, "code", None) or getattr(r, "name", "") for r in getattr(user, "roles", [])]
    roles = [str(r).strip() for r in roles if str(r).strip()]

    perm_codes: set[str] = set()
    for r in getattr(user, "roles", []):
        for p in getattr(r, "permissions", []):
            code = str(getattr(p, "code", "") or "").strip()
            if code:
                perm_codes.add(code)

    # Backward compat: keep single 'role' field for older checks/UI.
    legacy_role = str(getattr(user, "role", "") or "").strip()
    primary_role = "admin" if "admin" in roles else (roles[0] if roles else legacy_role)

    return {
        "id": user.id,
        "role": primary_role,
        "roles": roles,
        "permissions": sorted(perm_codes),
    }


def require_permissions(*codes: str):
    required = {c.strip() for c in codes if c and c.strip()}

    async def _dep(current: dict = Depends(get_current_user)) -> dict:
        if not required:
            return current
        have = set(map(str, current.get("permissions") or []))
        if not required.issubset(have):
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "Missing permissions"})
        return current

    return _dep
