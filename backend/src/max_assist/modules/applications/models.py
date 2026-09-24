import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from max_assist.db import Base
from max_assist.utils import now


class ServiceSession(Base):
    __tablename__ = "service_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), ForeignKey("users.id"))
    service_code: Mapped[str] = mapped_column(Text)
    service_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="draft")
    current_step_id: Mapped[str] = mapped_column(Text)
    completed_step_ids: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    public_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    sensitive_data_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    last_errors: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    confirmation_code_hash: Mapped[str | None] = mapped_column(Text)
    confirmation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_attempts: Mapped[int] = mapped_column(Integer, default=0)
    application_number: Mapped[str | None] = mapped_column(Text, unique=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ServiceSessionInbox(Base):
    __tablename__ = "service_session_inbox"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    service_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("service_sessions.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
