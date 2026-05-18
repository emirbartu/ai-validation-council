"""Async SQLAlchemy database models for AI Validation Council."""

from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from uuid_extensions.uuid7 import uuid7

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://council:council@localhost:5432/council",
)

async_engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker[AsyncSession](
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(AsyncAttrs, DeclarativeBase):
    """Declarative base for all async models."""

    type_annotation_map: dict[type[Any], Any] = {
        datetime: DateTime(timezone=True),
    }


class AnalysisStatus(StrEnum):
    """Status enum for analysis sessions."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class User(Base):
    """User model with UUID7 primary key."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    sessions: Mapped[list[AnalysisSession]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class AnalysisSession(Base):
    """Analysis session tracking model."""

    __tablename__ = "analysis_sessions"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AnalysisStatus] = mapped_column(
        default=AnalysisStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(back_populates="sessions")
    results: Mapped[list[AnalysisResult]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AnalysisResult(Base):
    """Individual agent output stored per session."""

    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid7()),
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_role: Mapped[str] = mapped_column(nullable=False)
    output_content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    session: Mapped[AnalysisSession] = relationship(back_populates="results")
