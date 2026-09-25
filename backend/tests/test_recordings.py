import base64
import hashlib
from uuid import UUID, uuid4

import pytest
from google.protobuf.json_format import MessageToJson
from livekit import api
from sqlalchemy import select

from max_assist.config import settings
from max_assist.db import session_factory
from max_assist.modules.assist.models import SessionEvent
from max_assist.modules.voice import recordings
from max_assist.modules.voice.models import Recording
from max_assist.utils import now
from tests.helpers import login
from tests.test_assist_api import joined_helper, owner_with_assist

SECOND = 1_000_000_000


@pytest.fixture(autouse=True)
def recordings_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "recordings_dir", str(tmp_path))
    return tmp_path


def signed(event):
    body = MessageToJson(event)
    digest = base64.b64encode(hashlib.sha256(body.encode()).digest()).decode()
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret).with_sha256(digest).to_jwt()
    )
    return body, token


async def send(client, event, token=None):
    body, good_token = signed(event)
    return await client.post(
        "/api/v1/livekit/webhook",
        content=body,
        headers={"Authorization": token or good_token, "Content-Type": "application/webhook+json"},
    )


def egress_event(kind, room, status=api.EgressStatus.EGRESS_ACTIVE, files=()):
    started = int(now().timestamp() * SECOND)
    return api.WebhookEvent(
        event=kind,
        egress_info=api.EgressInfo(
            egress_id="EG_test",
            room_name=str(room),
            status=status,
            started_at=started,
            ended_at=started + 5 * SECOND,
            file_results=list(files),
        ),
    )


def finished(room, status=api.EgressStatus.EGRESS_COMPLETE, file_started=0):
    file = api.FileInfo(
        filename=f"/out/{room}.ogg",
        started_at=file_started,
        duration=5 * SECOND,
        size=48_000,
    )
    return egress_event("egress_ended", room, status, [file])


async def meeting(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    return headers, helper_headers, body["id"]


async def recorded_meeting(client, folder):
    headers, helper_headers, assist_id = await meeting(client)
    await send(client, egress_event("egress_started", assist_id))
    await send(client, finished(assist_id))
    (folder / f"{assist_id}.ogg").write_bytes(b"OggS" + bytes(1000))
    await client.post(f"/api/v1/assist-sessions/{assist_id}/end", headers=headers)
    return headers, helper_headers, assist_id


async def stored(assist_id):
    async with session_factory() as db:
        return await db.scalar(select(Recording).where(Recording.assist_session_id == UUID(assist_id)))


async def test_recording_goes_from_started_to_ready(client):
    headers, _, assist_id = await meeting(client)

    started = await send(client, egress_event("egress_started", assist_id))
    during = (await client.get(f"/api/v1/assist-sessions/{assist_id}", headers=headers)).json()
    ended = await send(client, finished(assist_id))
    recording = await stored(assist_id)

    assert (started.status_code, ended.status_code) == (200, 200)
    assert during["recording"] == {"status": "recording", "duration_ms": None}
    assert (recording.status, recording.duration_ms, recording.size_bytes) == ("ready", 5000, 48_000)
    assert recording.file_path == f"{assist_id}.ogg"
    assert recording.egress_id == "EG_test"

    async with session_factory() as db:
        journal = list(
            await db.scalars(
                select(SessionEvent.event_type).where(SessionEvent.assist_session_id == UUID(assist_id))
            )
        )
    assert journal.count("recording.started") == journal.count("recording.stopped") == 1


async def test_repeated_or_foreign_events_change_nothing(client):
    _, _, assist_id = await meeting(client)
    await send(client, finished(assist_id))

    again = await send(client, egress_event("egress_started", assist_id))
    other_event = await send(client, api.WebhookEvent(event="room_started", room=api.Room(name=assist_id)))
    not_our_room = await send(client, egress_event("egress_started", "livekit-test-room"))
    unknown_room = await send(client, egress_event("egress_started", uuid4()))

    assert [item.status_code for item in (again, other_event, not_our_room, unknown_room)] == [200] * 4
    assert (await stored(assist_id)).status == "ready"


async def test_progress_updates_keep_the_recording_going(client):
    _, _, assist_id = await meeting(client)
    await send(client, egress_event("egress_started", assist_id))

    await send(client, egress_event("egress_updated", assist_id))

    assert (await stored(assist_id)).status == "recording"


async def test_sound_is_aligned_by_the_start_of_the_file(client):
    _, _, assist_id = await meeting(client)
    await send(client, egress_event("egress_started", assist_id))
    requested = (await stored(assist_id)).started_at
    file_started = int((requested.timestamp() + 2.5) * SECOND)

    await send(client, finished(assist_id, file_started=file_started))

    shift = (await stored(assist_id)).started_at - requested
    assert round(shift.total_seconds(), 1) == 2.5


def test_empty_times_and_paths_stay_empty():
    assert recordings.moment_of(0) is None
    assert recordings.file_of(Recording(file_path=None)) is None


async def test_forged_webhook_is_rejected(client):
    _, _, assist_id = await meeting(client)
    forged = api.AccessToken(settings.livekit_api_key, "some-other-secret-that-is-long-enough").to_jwt()

    response = await send(client, egress_event("egress_started", assist_id), token=forged)

    assert response.status_code == 401
    assert await stored(assist_id) is None


async def test_failed_recording_is_reported_and_not_served(client):
    headers, _, assist_id = await meeting(client)

    await send(client, finished(assist_id, api.EgressStatus.EGRESS_FAILED))
    response = await client.get(f"/api/v1/consultations/{assist_id}/recording", headers=headers)

    assert (await stored(assist_id)).status == "failed"
    assert response.status_code == 404


async def test_owner_listens_and_can_rewind(client, recordings_folder):
    headers, _, assist_id = await recorded_meeting(client, recordings_folder)
    token = headers["Authorization"].removeprefix("Bearer ")
    url = f"/api/v1/consultations/{assist_id}/recording"

    whole = await client.get(url, headers=headers)
    by_link = await client.get(f"{url}?token={token}")
    part = await client.get(url, headers={**headers, "Range": "bytes=0-3"})

    assert whole.status_code == 200
    assert whole.headers["content-type"] == "audio/ogg"
    assert by_link.status_code == 200
    assert (part.status_code, part.content) == (206, b"OggS")


async def test_only_the_owner_hears_the_recording(client, recordings_folder):
    _, helper_headers, assist_id = await recorded_meeting(client, recordings_folder)
    stranger = await login(client, "anna")
    url = f"/api/v1/consultations/{assist_id}/recording"

    helper = await client.get(url, headers=helper_headers)
    outsider = await client.get(url, headers=stranger)
    nobody = await client.get(url)

    assert (helper.status_code, outsider.status_code, nobody.status_code) == (403, 404, 401)


async def test_replay_links_sound_to_the_timeline(client, recordings_folder):
    headers, helper_headers, assist_id = await recorded_meeting(client, recordings_folder)

    owner = (await client.get(f"/api/v1/consultations/{assist_id}/replay", headers=headers)).json()
    helper = (await client.get(f"/api/v1/consultations/{assist_id}/replay", headers=helper_headers)).json()
    summary = (await client.get(f"/api/v1/consultations/{assist_id}", headers=headers)).json()

    assert owner["recording"]["url"] == f"/api/v1/consultations/{assist_id}/recording"
    assert owner["recording"]["offset_ms"] >= 0
    assert owner["recording"]["duration_ms"] == 5000
    assert helper["recording"]["url"] is None
    assert summary["recording"] == {"status": "ready", "duration_ms": 5000}


async def test_recording_in_progress_is_not_served_yet(client):
    headers, _, assist_id = await meeting(client)
    await send(client, egress_event("egress_started", assist_id))

    response = await client.get(f"/api/v1/consultations/{assist_id}/recording", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "recording_not_ready"


async def test_owner_deletes_the_recording_but_keeps_the_replay(client, recordings_folder):
    headers, _, assist_id = await recorded_meeting(client, recordings_folder)
    url = f"/api/v1/consultations/{assist_id}/recording"

    deleted = await client.delete(url, headers=headers)
    listen = await client.get(url, headers=headers)
    replay = (await client.get(f"/api/v1/consultations/{assist_id}/replay", headers=headers)).json()

    assert deleted.status_code == 204
    assert listen.status_code == 404
    assert not (recordings_folder / f"{assist_id}.ogg").exists()
    assert replay["recording"]["status"] == "deleted"
    assert replay["recording"]["url"] is None
    assert replay["events"]


async def test_lost_file_is_not_found(client, recordings_folder):
    headers, _, assist_id = await recorded_meeting(client, recordings_folder)
    (recordings_folder / f"{assist_id}.ogg").unlink()

    response = await client.get(f"/api/v1/consultations/{assist_id}/recording", headers=headers)

    assert response.status_code == 404


async def test_health_shows_how_much_space_recordings_take(client, recordings_folder, monkeypatch):
    (recordings_folder / "big.ogg").write_bytes(bytes(3 * 1024 * 1024))

    body = (await client.get("/health")).json()
    monkeypatch.setattr(settings, "recordings_dir", str(recordings_folder / "missing"))

    assert body["recordings_size_mb"] == 3
    assert recordings.folder_size_mb() == 0
