from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserPresenceSession(Base):
    __tablename__ = "user_presence_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)

    # Stable client id (stored on frontend). Keeps a single logical session across access-token renewals.
    client_id: Mapped[str] = mapped_column(String(64), index=True)

    # Optional workstation identifier (if provided by client). Often null; we also store client_ip.
    computer: Mapped[str | None] = mapped_column(String(128), nullable=True)
    client_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, index=True)

    ended_at: Mapped[datetime | None] = mapped_column(DateTime, index=True, nullable=True)
    ended_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
