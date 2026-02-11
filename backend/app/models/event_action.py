from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EventAction(Base):
    __tablename__ = "event_actions"
    __table_args__ = (
        UniqueConstraint("source_table", "source_pk", name="uq_event_actions_source"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    # Links to local event id (for MSSQL imports: mssql:{date_key}:{event_id})
    event_id: Mapped[str] = mapped_column(String(64), index=True)

    action_name: Mapped[str] = mapped_column(String(80), index=True)
    action_time: Mapped[datetime] = mapped_column(DateTime, index=True)

    operator_name: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    computer: Mapped[str | None] = mapped_column(String(70), nullable=True)
    gbr_name: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)

    date_key: Mapped[int] = mapped_column(Integer, index=True)
    raw_event_id: Mapped[int] = mapped_column(Integer, index=True)

    source_table: Mapped[str] = mapped_column(String(64), index=True)
    source_pk: Mapped[int] = mapped_column(Integer)
