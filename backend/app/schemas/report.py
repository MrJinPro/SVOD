from __future__ import annotations

from pydantic import BaseModel


class ReportOut(BaseModel):
    id: str
    type: str
    periodStart: str
    periodEnd: str
    generatedAt: str
    status: str
    eventsCount: int
    criticalCount: int
