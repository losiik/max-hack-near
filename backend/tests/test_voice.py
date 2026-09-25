import logging
from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from livekit import api

from max_assist import tasks
from max_assist.config import settings
from max_assist.modules.voice import sync
from max_assist.modules.voice.livekit import Rooms, room_token, skip_missing
from max_assist.utils import now
from tests.helpers import login
from tests.test_assist_api import joined_helper, owner_with_assist


async def voice_token(client, headers, assist_id):
    return await client.post(f"/api/v1/assist-sessions/{assist_id}/voice-token", headers=headers)


def claims_of(token):
    return jwt.decode(token, settings.livekit_api_secret, algorithms=["HS256"], options={"verify_aud": False})


async def test_voice_opens_only_when_a_helper_is_connected(client):
    headers, _, body = await owner_with_assist(client)

    early = await voice_token(client, headers, body["id"])
    helper_headers, participant_id = await joined_helper(client, headers, body["id"])
    owner = await voice_token(client, headers, body["id"])
    helper = await voice_token(client, helper_headers, body["id"])

    assert early.status_code == 409
    assert early.json()["error"]["code"] == "session_not_active"
    assert owner.status_code == helper.status_code == 200
    assert owner.json()["room"] == body["id"]
    assert owner.json()["url"] == settings.livekit_url

    claims = claims_of(helper.json()["token"])
    assert claims["sub"] == participant_id
    assert claims["name"] == "Сергей К."
    assert claims["video"]["room"] == body["id"]
    assert claims["video"]["roomJoin"] is True
    assert claims["video"]["canPublishSources"] == ["microphone"]
    assert claims["video"]["canPublishData"] is False
    assert claims["exp"] - now().timestamp() <= settings.voice_token_ttl_seconds + 1


async def test_waiting_and_strangers_hear_nothing(client):
    headers, _, body = await owner_with_assist(client)
    await joined_helper(client, headers, body["id"])
    waiting_headers, _ = await joined_helper(client, headers, body["id"], "oleg", approve=False)
    stranger = await login(client, "anna")

    waiting = await voice_token(client, waiting_headers, body["id"])
    outsider = await voice_token(client, stranger, body["id"])

    assert waiting.status_code == 403
    assert outsider.status_code == 404


async def test_room_follows_the_session(client, voice):
    headers, _, body = await owner_with_assist(client)
    _, participant_id = await joined_helper(client, headers, body["id"])
    await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}",
        headers=headers,
    )
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    await tasks.wait_background()

    assert voice.calls_for(body["id"]) == [
        ("open", body["id"]),
        ("remove", body["id"], participant_id),
        ("close", body["id"]),
    ]


async def test_helper_leaving_is_dropped_from_the_room(client, voice):
    headers, _, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"])

    await client.post(f"/api/v1/assist-sessions/{body['id']}/leave", headers=helper_headers)
    await tasks.wait_background()

    assert ("remove", body["id"], participant_id) in voice.calls_for(body["id"])


async def test_voice_failure_does_not_break_help(client, monkeypatch, caplog):
    async def broken(room):
        raise RuntimeError("livekit is down")

    monkeypatch.setattr(sync.rooms, "open", broken)
    headers, _, body = await owner_with_assist(client)

    with caplog.at_level(logging.ERROR, logger="max_assist.voice"):
        helper_headers, _ = await joined_helper(client, headers, body["id"])
        await tasks.wait_background()

    session = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=helper_headers)
    assert session.json()["status"] == "active"
    assert "open failed" in caplog.text


async def test_health_shows_when_voice_server_is_down(client, voice):
    voice.up = False

    body = (await client.get("/health")).json()

    assert (body["status"], body["livekit"]) == ("degraded", "down")


async def test_missing_room_or_participant_is_not_an_error():
    async def missing():
        raise api.TwirpError(api.TwirpErrorCode.NOT_FOUND, "room not found", status=404)

    async def broken():
        raise api.TwirpError(api.TwirpErrorCode.INTERNAL, "boom", status=500)

    await skip_missing(missing())
    with pytest.raises(api.TwirpError):
        await skip_missing(broken())


async def test_unreachable_voice_server_is_reported_as_down(monkeypatch):
    monkeypatch.setattr(settings, "livekit_api_url", "http://127.0.0.1:9")

    assert await Rooms().ping() is False


def test_token_lives_briefly():
    token, expires_at = room_token(str(uuid4()), str(uuid4()), "Людмила П.")

    assert expires_at - now() <= timedelta(seconds=settings.voice_token_ttl_seconds)
    assert claims_of(token)["name"] == "Людмила П."
