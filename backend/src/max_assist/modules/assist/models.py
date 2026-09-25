import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from max_assist.db import Base
from max_assist.utils import now


class AssistSession(Base):
    __tablename__ = "assist_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("service_sessions.id", ondelete="SET NULL")
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    service_code: Mapped[str] = mapped_column(Text)
    service_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="waiting")
    end_reason: Mapped[str | None] = mapped_column(Text)
    last_seq: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    participants: Mapped[list["AssistParticipant"]] = relationship(
        back_populates="assist_session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AssistParticipant.requested_at",
    )
    invites: Mapped[list["AssistInvite"]] = relationship(
        back_populates="assist_session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="AssistInvite.created_at",
    )


class AssistInvite(Base):
    __tablename__ = "assist_invites"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assist_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_sessions.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, default="link")
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    assist_session: Mapped[AssistSession] = relationship(back_populates="invites")


class HelpCallback(Base):
    __tablename__ = "help_callbacks"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    helper_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    service_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("service_sessions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(Text, default="busy")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AssistParticipant(Base):
    __tablename__ = "assist_participants"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assist_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_sessions.id", ondelete="CASCADE")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    kind: Mapped[str] = mapped_column(Text, default="human")
    role: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    joined_via: Mapped[str] = mapped_column(Text)
    invite_id: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_invites.id", ondelete="SET NULL")
    )
    display_name: Mapped[str] = mapped_column(Text)
    badge_label: Mapped[str | None] = mapped_column(Text)
    badge_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assist_session: Mapped[AssistSession] = relationship(back_populates="participants")


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    assist_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_sessions.id", ondelete="CASCADE")
    )
    seq: Mapped[int | None] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor_participant_id: Mapped[uuid.UUID | None] = mapped_column(PgUUID(as_uuid=True))
    event_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
