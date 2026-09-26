import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from max_assist.db import Base
from max_assist.utils import now


class AgentTurn(Base):
    __tablename__ = "ai_agent_turns"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assist_session_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_sessions.id", ondelete="CASCADE")
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("assist_participants.id", ondelete="CASCADE")
    )
    trigger: Mapped[str] = mapped_column(Text)
    reply_text: Mapped[str] = mapped_column(Text)
    tools: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    guard_result: Mapped[str] = mapped_column(Text)
    latency_ms: Mapped[int] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
