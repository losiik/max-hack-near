from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from max_assist.modules.identity.models import User


class MaxLoginRequest(BaseModel):
    init_data: str


class DevLoginRequest(BaseModel):
    user_key: str


class UserOut(BaseModel):
    id: UUID
    display_name: str
    photo_url: str | None
    staff: None = None

    @classmethod
    def of(cls, user: User) -> "UserOut":
        return cls(id=user.id, display_name=user.display_name, photo_url=user.photo_url)


class TokenOut(BaseModel):
    access_token: str
    expires_at: datetime
    user: UserOut


class MeCounters(BaseModel):
    drafts: int


class MeOut(BaseModel):
    id: UUID
    first_name: str
    last_name: str | None
    display_name: str
    photo_url: str | None
    staff: None = None
    recording_consent: bool
    counters: MeCounters


class DevUserOut(BaseModel):
    user_key: str
    display_name: str
    role_hint: str
