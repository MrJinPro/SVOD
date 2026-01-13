from __future__ import annotations

from pydantic import BaseModel


class ApiError(BaseModel):
    code: str
    message: str
