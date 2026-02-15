from __future__ import annotations

from sqlalchemy import Integer, String, Text
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

    # Stored file (optional): if generated via POST /reports/generate
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Parameters used for generation/view (JSON string)
    params_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Error details (if failed)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
