from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from max_assist.modules.identity.models import StaffProfile, User


class MaxLoginRequest(BaseModel):
    init_data: str


class DevLoginRequest(BaseModel):
    user_key: str


class StaffOut(BaseModel):
    role: str
    organization: str
    position: str | None
    verified: bool

    @classmethod
    def of(cls, profile: StaffProfile | None) -> "StaffOut | None":
        if profile is None:
            return None
        return cls(
            role=profile.role,
            organization=profile.organization,
            position=profile.position,
            verified=profile.verified_at is not None,
        )


class UserOut(BaseModel):
    id: UUID
    display_name: str
    photo_url: str | None
    staff: StaffOut | None

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(
            id=user.id,
            display_name=user.display_name,
            photo_url=user.photo_url,
            staff=StaffOut.of(user.staff),
        )


class TokenOut(BaseModel):
    access_token: str
    expires_at: datetime
    user: UserOut


class MeCounters(BaseModel):
    drafts: int
    active_assist_sessions: int
    trusted_helpers: int
    helping_for: int


class MeOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    display_name: str
    photo_url: str | None
    staff: StaffOut | None
    recording_consent: bool
    counters: MeCounters


class DevUserOut(BaseModel):
    user_key: str
    display_name: str
    role_hint: str
