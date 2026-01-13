from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token

security = HTTPBearer(auto_error=False)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Missing token"})

    try:
        payload = decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "Invalid token"})

    return {"id": payload.get("sub"), "role": payload.get("role")}
