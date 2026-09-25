from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from max_assist.deps import CurrentUser, DbSession
from max_assist.modules.assist import service
from max_assist.modules.assist.schemas import (
    AcceptOut,
    ActiveAssistOut,
    AssistSessionOut,
    CallBackOut,
    ConsultationItemOut,
    ConsultationOut,
    CreateAssistRequest,
    DeclineOut,
    HelpCallbackOut,
    InviteOut,
    InvitePreviewOut,
    InviteRequest,
    NameOut,
    ReplayOut,
    SnapshotOut,
    SummaryOut,
    active_view,
    callback_view,
    consultation_item,
    consultation_view,
    invite_view,
    preview_view,
    replay_view,
    session_view,
    snapshot_view,
    summary_view,
)
from max_assist.modules.identity.models import User

router = APIRouter(tags=["assist"])


@router.post("/assist-sessions", response_model=AssistSessionOut, status_code=201)
async def create_session(payload: CreateAssistRequest, user: CurrentUser, db: DbSession) -> AssistSessionOut:
    assist = await service.create(db, user, payload.service_session_id)
    return await session_view(db, assist, user.id)


@router.get("/assist-sessions", response_model=list[ActiveAssistOut])
async def list_sessions(
    user: CurrentUser,
    db: DbSession,
    scope: Literal["active"] = "active",
) -> list[ActiveAssistOut]:
    rows = await service.list_active(db, user)
    return [await active_view(db, row, user.id) for row in rows]


@router.get("/assist-sessions/{assist_id}", response_model=AssistSessionOut)
async def get_session(assist_id: UUID, user: CurrentUser, db: DbSession) -> AssistSessionOut:
    assist = await service.get_visible(db, user, assist_id)
    return await session_view(db, assist, user.id)


@router.get("/assist-sessions/{assist_id}/state", response_model=SnapshotOut)
async def get_state(assist_id: UUID, user: CurrentUser, db: DbSession) -> SnapshotOut:
    assist = await service.get_active(db, user, assist_id)
    return await snapshot_view(db, assist, user.id)


@router.post("/assist-sessions/{assist_id}/invites", response_model=InviteOut, status_code=201)
async def create_invite(
    assist_id: UUID,
    payload: InviteRequest,
    user: CurrentUser,
    db: DbSession,
) -> InviteOut:
    assist, invite, token = await service.create_invite(db, user, assist_id)
    return await invite_view(db, assist, invite, token, user)


@router.delete("/assist-sessions/{assist_id}/invites/{invite_id}", status_code=204)
async def revoke_invite(assist_id: UUID, invite_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.revoke_invite(db, user, assist_id, invite_id)
    return Response(status_code=204)


@router.get("/assist-invites/{token}", response_model=InvitePreviewOut)
async def preview_invite(token: str, user: CurrentUser, db: DbSession) -> InvitePreviewOut:
    assist, invite = await service.find_invite(db, token)
    return await preview_view(db, assist, invite, user.id)


@router.post("/assist-invites/{token}/accept", response_model=AcceptOut)
async def accept_invite(token: str, user: CurrentUser, db: DbSession) -> AcceptOut:
    assist, participant = await service.accept_invite(db, user, token)
    return AcceptOut(assist_session_id=assist.id, participant_id=participant.id, status=participant.status)


@router.post("/assist-invites/{token}/decline", response_model=DeclineOut)
async def decline_invite(token: str, user: CurrentUser, db: DbSession) -> DeclineOut:
    assist, callback = await service.decline_invite(db, user, token)
    owner = await db.get(User, assist.owner_id)
    return DeclineOut(help_callback_id=callback.id, owner=NameOut(display_name=owner.display_name))


@router.get("/help-callbacks", response_model=list[HelpCallbackOut])
async def list_callbacks(
    user: CurrentUser,
    db: DbSession,
    role: Literal["owner", "helper"] = Query("owner", alias="as"),
) -> list[HelpCallbackOut]:
    rows = await service.list_callbacks(db, user, role == "owner")
    return [await callback_view(db, row) for row in rows]


@router.post("/help-callbacks/{callback_id}/ready", response_model=HelpCallbackOut)
async def helper_is_ready(callback_id: UUID, user: CurrentUser, db: DbSession) -> HelpCallbackOut:
    callback = await service.helper_is_ready(db, user, callback_id)
    return await callback_view(db, callback)


@router.post("/help-callbacks/{callback_id}/call", response_model=CallBackOut, status_code=201)
async def call_back(callback_id: UUID, user: CurrentUser, db: DbSession) -> CallBackOut:
    assist, invite, token = await service.call_back(db, user, callback_id)
    return CallBackOut(
        assist_session=await session_view(db, assist, user.id),
        invite=await invite_view(db, assist, invite, token, user),
    )


@router.delete("/help-callbacks/{callback_id}", status_code=204)
async def dismiss_callback(callback_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.dismiss_callback(db, user, callback_id)
    return Response(status_code=204)


@router.post(
    "/assist-sessions/{assist_id}/participants/{participant_id}/approve",
    response_model=AssistSessionOut,
)
async def approve(
    assist_id: UUID,
    participant_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> AssistSessionOut:
    assist = await service.approve(db, user, assist_id, participant_id)
    return await session_view(db, assist, user.id)


@router.post(
    "/assist-sessions/{assist_id}/participants/{participant_id}/reject",
    response_model=AssistSessionOut,
)
async def reject(assist_id: UUID, participant_id: UUID, user: CurrentUser, db: DbSession) -> AssistSessionOut:
    assist = await service.reject(db, user, assist_id, participant_id)
    return await session_view(db, assist, user.id)


@router.delete(
    "/assist-sessions/{assist_id}/participants/{participant_id}",
    response_model=AssistSessionOut,
)
async def remove(assist_id: UUID, participant_id: UUID, user: CurrentUser, db: DbSession) -> AssistSessionOut:
    assist = await service.remove(db, user, assist_id, participant_id)
    return await session_view(db, assist, user.id)


@router.post("/assist-sessions/{assist_id}/leave", status_code=204)
async def leave(assist_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.leave(db, user, assist_id)
    return Response(status_code=204)


@router.post("/assist-sessions/{assist_id}/end", response_model=SummaryOut)
async def end(assist_id: UUID, user: CurrentUser, db: DbSession) -> SummaryOut:
    assist = await service.end(db, user, assist_id)
    return await summary_view(db, assist)


@router.get("/consultations", response_model=list[ConsultationItemOut])
async def list_consultations(
    user: CurrentUser,
    db: DbSession,
    role: Literal["owner", "helper"] = Query("owner", alias="as"),
    limit: int = Query(20, ge=1, le=100),
) -> list[ConsultationItemOut]:
    rows = await service.list_consultations(db, user, role == "owner", limit)
    return [await consultation_item(db, row, user.id, await service.journal_of(db, row.id)) for row in rows]


@router.get("/consultations/{assist_id}", response_model=ConsultationOut)
async def get_consultation(assist_id: UUID, user: CurrentUser, db: DbSession) -> ConsultationOut:
    assist = await service.get_consultation(db, user, assist_id)
    return await consultation_view(db, assist, user.id, await service.journal_of(db, assist.id))


@router.get("/consultations/{assist_id}/replay", response_model=ReplayOut)
async def get_replay(assist_id: UUID, user: CurrentUser, db: DbSession) -> ReplayOut:
    assist = await service.get_consultation(db, user, assist_id)
    return await replay_view(db, assist, await service.journal_of(db, assist.id))


@router.get("/assist-sessions/{assist_id}/summary", response_model=SummaryOut)
async def summary(assist_id: UUID, user: CurrentUser, db: DbSession) -> SummaryOut:
    assist = await service.get_visible(db, user, assist_id)
    return await summary_view(db, assist)
