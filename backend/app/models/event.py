from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(index=True)

    type: Mapped[str] = mapped_column(String(32), index=True)
    object_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    object_name: Mapped[str] = mapped_column(String(255), index=True)
    client_name: Mapped[str] = mapped_column(String(255), index=True)

    severity: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), index=True)

    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)

    operator_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
