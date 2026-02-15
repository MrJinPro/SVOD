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

    # Optional: if report has a stored file
    downloadUrl: str | None = None
    fileName: str | None = None
    mimeType: str | None = None
