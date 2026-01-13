from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class EventBase(BaseModel):
    timestamp: datetime
    type: str
    objectId: str | None = None
    objectName: str
    clientName: str
    severity: str
    status: str
    description: str
    location: str | None = None
    operatorId: str | None = None


class EventCreate(EventBase):
    id: str


class EventUpdate(BaseModel):
    timestamp: datetime | None = None
    type: str | None = None
    objectId: str | None = None
    objectName: str | None = None
    clientName: str | None = None
    severity: str | None = None
    status: str | None = None
    description: str | None = None
    location: str | None = None
    operatorId: str | None = None


class EventOut(EventBase):
    id: str
