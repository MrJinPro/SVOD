from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Object(Base):
    __tablename__ = "objects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    client_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    disabled: Mapped[bool] = mapped_column(Boolean, default=False)

    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    additional_info: Mapped[str | None] = mapped_column(Text, nullable=True)

    latitude: Mapped[str | None] = mapped_column(String(32), nullable=True)
    longitude: Mapped[str | None] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    groups: Mapped[list[ObjectGroup]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    responsibles: Mapped[list[Responsible]] = relationship(
        back_populates="object",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ObjectGroup(Base):
    __tablename__ = "object_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id", ondelete="CASCADE"), index=True)
    group_no: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    is_open: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_event: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    object: Mapped[Object] = relationship(back_populates="groups")


class Responsible(Base):
    __tablename__ = "responsibles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[str] = mapped_column(ForeignKey("objects.id", ondelete="CASCADE"), index=True)
    group_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    name: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)

    object: Mapped[Object] = relationship(back_populates="responsibles")
    phones: Mapped[list[ResponsiblePhone]] = relationship(
        back_populates="responsible",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ResponsiblePhone(Base):
    __tablename__ = "responsible_phones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    responsible_id: Mapped[int] = mapped_column(ForeignKey("responsibles.id", ondelete="CASCADE"), index=True)
    phone: Mapped[str] = mapped_column(String(32), index=True)
    type_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    responsible: Mapped[Responsible] = relationship(back_populates="phones")
