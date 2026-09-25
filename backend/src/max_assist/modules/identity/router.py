from fastapi import APIRouter

from max_assist.config import settings
from max_assist.deps import CurrentUser, DbSession
from max_assist.errors import Forbidden
from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist import service as assist_service
from max_assist.modules.identity import service
from max_assist.modules.identity.schemas import (
    DevLoginRequest,
    DevUserOut,
    MaxLoginRequest,
    MeCounters,
    MeOut,
    StaffOut,
    TokenOut,
    UserOut,
)
from max_assist.modules.trust import service as trust_service
from max_assist.security import create_access_token

router = APIRouter(tags=["identity"])


@router.post("/auth/max", response_model=TokenOut)
async def login_with_max(payload: MaxLoginRequest, session: DbSession) -> TokenOut:
    user = await service.login_with_max(session, payload.init_data)
    token, expires_at = create_access_token(user.id)
    return TokenOut(access_token=token, expires_at=expires_at, user=UserOut.of(user))


@router.post("/auth/dev-login", response_model=TokenOut)
async def dev_login(payload: DevLoginRequest, session: DbSession) -> TokenOut:
    user = await service.dev_login(session, payload.user_key)
    token, expires_at = create_access_token(user.id)
    return TokenOut(access_token=token, expires_at=expires_at, user=UserOut.of(user))


@router.get("/dev/users", response_model=list[DevUserOut])
async def dev_users() -> list[DevUserOut]:
    if not settings.is_dev:
        raise Forbidden("Dev-вход отключён")
    return [
        DevUserOut(
            user_key=key,
            display_name=f"{profile['first_name']} {profile['last_name']}",
            role_hint=profile["role_hint"],
        )
        for key, profile in service.DEV_USERS.items()
    ]


@router.post("/dev/reset")
async def dev_reset(user: CurrentUser, session: DbSession) -> dict[str, int]:
    if not settings.is_dev:
        raise Forbidden("Dev-режим отключён")
    removed = await applications_service.reset_user_data(session, user)
    return {"removed_service_sessions": removed}


@router.get("/me", response_model=MeOut)
async def me(user: CurrentUser, session: DbSession) -> MeOut:
    counters = MeCounters(
        drafts=await applications_service.count_drafts(session, user),
        active_assist_sessions=len(await assist_service.list_active(session, user)),
        trusted_helpers=await trust_service.count_helpers(session, user),
        helping_for=await trust_service.count_helping_for(session, user),
    )
    return MeOut(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        display_name=user.display_name,
        photo_url=user.photo_url,
        staff=StaffOut.of(user.staff),
        recording_consent=user.recording_consent_at is not None,
        counters=counters,
    )


@router.post("/me/recording-consent", status_code=204)
async def agree_to_recording(user: CurrentUser, session: DbSession) -> None:
    await service.agree_to_recording(session, user)
