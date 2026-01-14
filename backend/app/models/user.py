from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    role: Mapped[str] = mapped_column(String(32), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # для прототипа: храним хэш позже; сейчас поле оставлено для соответствия будущей реализации
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    last_login: Mapped[str | None] = mapped_column(String(32), nullable=True)
