import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from livekit import api
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.modules.assist import events, journal
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.assist.realtime import hub
from max_assist.modules.voice.models import Recording

logger = logging.getLogger("max_assist.voice")

ENDED = {"egress_ended"}
STARTED = {"egress_started", "egress_updated"}


def moment_of(nanoseconds: int) -> datetime | None:
    if not nanoseconds:
        return None
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, tz=UTC)


def file_of(recording: Recording) -> Path | None:
    if recording.file_path is None:
        return None
    return Path(settings.recordings_dir) / recording.file_path


async def find(db: AsyncSession, assist_id: UUID) -> Recording | None:
    return await db.scalar(select(Recording).where(Recording.assist_session_id == assist_id))


def room_of(event: api.WebhookEvent) -> UUID | None:
    try:
        return UUID(event.egress_info.room_name)
    except ValueError:
        return None


async def on_webhook(db: AsyncSession, event: api.WebhookEvent) -> None:
    if event.event not in STARTED | ENDED:
        return
    assist_id = room_of(event)
    assist = await db.get(AssistSession, assist_id, with_for_update=True) if assist_id else None
    if assist is None:
        return

    info = event.egress_info
    recording = await find(db, assist.id)
    started = recording is None
    if started:
        recording = Recording(assist_session_id=assist.id, egress_id=info.egress_id, status="recording")
        db.add(recording)
        journal.note(db, assist.id, "recording.started", {"status": "recording"})
    elif recording.status != "recording":
        # LiveKit может прислать одно и то же событие повторно
        return

    recording.started_at = recording.started_at or moment_of(info.started_at)
    finished = event.event in ENDED
    if finished:
        finish(recording, info)
        journal.note(db, assist.id, "recording.stopped", {"status": recording.status})

    await db.commit()
    if started or finished:
        await announce(assist.id, recording.status)


def finish(recording: Recording, info: api.EgressInfo) -> None:
    files = list(info.file_results)
    recording.ended_at = moment_of(info.ended_at)
    if info.status != api.EgressStatus.EGRESS_COMPLETE or not files:
        recording.status = "failed"
        logger.warning("recording %s failed: %s", recording.assist_session_id, info.error)
        return

    recording.status = "ready"
    # файл начинается позже, чем запущена запись: так звук совпадёт с действиями на форме
    recording.started_at = moment_of(files[0].started_at) or recording.started_at
    recording.file_path = Path(files[0].filename).name
    recording.duration_ms = files[0].duration // 1_000_000
    recording.size_bytes = files[0].size


async def delete(db: AsyncSession, recording: Recording) -> None:
    path = file_of(recording)
    if path is not None:
        path.unlink(missing_ok=True)
    recording.status = "deleted"
    recording.file_path = None
    await db.commit()


def folder_size_mb() -> int:
    folder = Path(settings.recordings_dir)
    if not folder.is_dir():
        return 0
    return sum(item.stat().st_size for item in folder.iterdir() if item.is_file()) // (1024 * 1024)


async def announce(assist_id: UUID, status: str) -> None:
    message = events.envelope(assist_id, "recording.status_changed", {"status": status})
    await events.publish(assist_id, [events.Delivery(hub.active_participants(assist_id), message)])
