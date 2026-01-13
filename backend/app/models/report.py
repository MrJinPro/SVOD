from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), index=True)
    period_start: Mapped[str] = mapped_column(String(10), index=True)
    period_end: Mapped[str] = mapped_column(String(10), index=True)

    generated_at: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(16), index=True)

    events_count: Mapped[int] = mapped_column(Integer)
    critical_count: Mapped[int] = mapped_column(Integer)
