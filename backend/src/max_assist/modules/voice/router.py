from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, Request, Response
from fastapi.responses import FileResponse
from livekit import api
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.deps import CurrentUser, DbSession, Listener
from max_assist.errors import Conflict, Forbidden, NotFound, Unauthorized
from max_assist.modules.assist import domain
from max_assist.modules.assist import service as assist_service
from max_assist.modules.identity.models import User
from max_assist.modules.voice import past_help, recordings
from max_assist.modules.voice.livekit import room_token
from max_assist.modules.voice.models import Recording

router = APIRouter(tags=["voice"])


class VoiceTokenOut(BaseModel):
    url: str
    room: str
    token: str
    expires_at: datetime


@router.post("/assist-sessions/{assist_id}/voice-token", response_model=VoiceTokenOut)
async def voice_token(assist_id: UUID, user: CurrentUser, db: DbSession) -> VoiceTokenOut:
    assist = await assist_service.get_active(db, user, assist_id)
    if assist.status != "active":
        raise Conflict("session_not_active", "Разговор начнётся, когда подключится помощник")

    participant = domain.participant_of(assist, user.id)
    token, expires_at = room_token(str(assist.id), str(participant.id), participant.display_name)
    return VoiceTokenOut(url=settings.livekit_url, room=str(assist.id), token=token, expires_at=expires_at)


class HelperNameOut(BaseModel):
    display_name: str
    role: str


class PastHelpFragmentOut(BaseModel):
    assist_session_id: UUID
    date: datetime
    helpers: list[HelperNameOut]
    has_audio: bool
    audio_url: str | None
    audio_start_ms: int | None
    audio_end_ms: int | None
    replay_from_ms: int
    replay_to_ms: int
    highlights: int
    confusions: int


class PastHelpOut(BaseModel):
    steps: dict[str, list[PastHelpFragmentOut]]


@router.get("/service-sessions/{service_session_id}/past-help", response_model=PastHelpOut)
async def get_past_help(service_session_id: UUID, user: CurrentUser, db: DbSession) -> PastHelpOut:
    return PastHelpOut(steps=await past_help.past_help(db, user, service_session_id))


@router.post("/livekit/webhook", include_in_schema=False)
async def livekit_webhook(
    request: Request,
    db: DbSession,
    authorization: str = Header(""),
) -> Response:
    receiver = api.WebhookReceiver(api.TokenVerifier(settings.livekit_api_key, settings.livekit_api_secret))
    try:
        event = receiver.receive((await request.body()).decode(), authorization)
    except Exception as error:
        raise Unauthorized("Неверная подпись LiveKit") from error

    await recordings.on_webhook(db, event)
    return Response(status_code=200)


async def owned_recording(db: AsyncSession, user: User, assist_id: UUID) -> Recording:
    assist = await assist_service.get_consultation(db, user, assist_id)
    if assist.owner_id != user.id:
        raise Forbidden("Запись может слушать только тот, кому помогали")

    recording = await recordings.find(db, assist.id)
    if recording is None or recording.status in ("failed", "deleted"):
        raise NotFound("Записи нет")
    if recording.status == "recording":
        raise Conflict("recording_not_ready", "Запись ещё идёт")
    return recording


@router.get("/consultations/{assist_id}/recording", response_class=FileResponse)
async def listen(assist_id: UUID, user: Listener, db: DbSession) -> FileResponse:
    recording = await owned_recording(db, user, assist_id)
    path = recordings.file_of(recording)
    if path is None or not path.is_file():
        raise NotFound("Файл записи не найден")
    return FileResponse(
        path,
        media_type="audio/ogg",
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-store",
            "Content-Disposition": "inline",
        },
    )


@router.delete("/consultations/{assist_id}/recording", status_code=204)
async def delete_recording(assist_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    recording = await owned_recording(db, user, assist_id)
    await recordings.delete(db, recording)
    return Response(status_code=204)
