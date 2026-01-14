from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NotificationRead(Base):
    __tablename__ = "notification_reads"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class NotificationClear(Base):
    __tablename__ = "notification_clears"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cleared_before: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
