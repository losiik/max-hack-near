from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response

from max_assist.deps import CurrentUser, DbSession
from max_assist.modules.assist import service
from max_assist.modules.assist.schemas import (
    AcceptOut,
    ActiveAssistOut,
    AssistSessionOut,
    CreateAssistRequest,
    InviteOut,
    InvitePreviewOut,
    InviteRequest,
    SnapshotOut,
    SummaryOut,
    active_view,
    invite_view,
    preview_view,
    session_view,
    snapshot_view,
    summary_view,
)

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


@router.get("/assist-sessions/{assist_id}/summary", response_model=SummaryOut)
async def summary(assist_id: UUID, user: CurrentUser, db: DbSession) -> SummaryOut:
    assist = await service.get_visible(db, user, assist_id)
    return await summary_view(db, assist)
