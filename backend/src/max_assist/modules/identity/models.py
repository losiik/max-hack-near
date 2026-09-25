import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from max_assist.db import Base
from max_assist.utils import now


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    max_user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    first_name: Mapped[str] = mapped_column(Text)
    last_name: Mapped[str | None] = mapped_column(Text)
    username: Mapped[str | None] = mapped_column(Text)
    photo_url: Mapped[str | None] = mapped_column(Text)
    dev_key: Mapped[str | None] = mapped_column(Text, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    recording_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    staff: Mapped["StaffProfile | None"] = relationship(lazy="selectin", cascade="all, delete-orphan")

    @property
    def display_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name[0]}."
        return self.first_name

    @property
    def full_name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part)


class StaffProfile(Base):
    __tablename__ = "staff_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(Text, default="mfc_operator")
    organization: Mapped[str] = mapped_column(Text)
    position: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
