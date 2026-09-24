import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import update

from max_assist.db import session_factory
from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist import expiry
from max_assist.modules.assist import service as assist_service
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.assist.realtime import Viewer, hub
from max_assist.utils import now
from tests.helpers import login, start_session
from tests.test_assist_api import joined_helper, owner_with_assist


async def idle_for(assist_id: str, minutes: int) -> None:
    async with session_factory() as db:
        await db.execute(
            update(AssistSession)
            .where(AssistSession.id == UUID(assist_id))
            .values(last_activity_at=now() - timedelta(minutes=minutes))
        )
        await db.commit()


async def view(client, headers, assist_id: str) -> dict:
    return (await client.get(f"/api/v1/assist-sessions/{assist_id}", headers=headers)).json()


async def expire() -> int:
    async with session_factory() as db:
        return await assist_service.expire_idle(db)


async def test_abandoned_sessions_expire_after_their_timeout(client):
    ludmila, _, waiting = await owner_with_assist(client)
    anna = await login(client, "anna")
    application = await start_session(client, anna)
    active = (
        await client.post("/api/v1/assist-sessions", json={"service_session_id": application}, headers=anna)
    ).json()
    await joined_helper(client, anna, active["id"], "sergey")

    await idle_for(waiting["id"], 31)
    await idle_for(active["id"], 40)
    await expire()

    assert (await view(client, ludmila, waiting["id"]))["end_reason"] == "expired"
    assert (await view(client, anna, active["id"]))["status"] == "active"

    await idle_for(active["id"], 61)
    await expire()

    ended = await view(client, anna, active["id"])
    assert (ended["status"], ended["end_reason"]) == ("ended", "expired")
    assert [item["role"] for item in ended["participants"]] == ["owner"]


async def test_session_with_someone_connected_does_not_expire(client):
    headers, _, body = await owner_with_assist(client)
    await idle_for(body["id"], 31)
    viewer = Viewer(
        participant_id=UUID(body["me"]["participant_id"]),
        role="owner",
        status="active",
        display_name="Людмила П.",
    )

    connection, _ = hub.connect(UUID(body["id"]), viewer, object())
    try:
        await expire()
        while_connected = await view(client, headers, body["id"])
    finally:
        hub.disconnect(UUID(body["id"]), viewer.participant_id, connection)
    await expire()
    after_leaving = await view(client, headers, body["id"])

    assert while_connected["status"] == "waiting"
    assert after_leaving["end_reason"] == "expired"


async def test_expiry_job_expires_sessions_and_forgets_rate_limits(client, monkeypatch, caplog):
    _, _, body = await owner_with_assist(client)
    await idle_for(body["id"], 31)
    pruned = []
    monkeypatch.setattr(expiry.commands, "prune_limits", lambda: pruned.append(True))

    with caplog.at_level(logging.INFO, logger="max_assist.assist"):
        await expiry.run_once()

    assert pruned == [True]
    assert "idle assist sessions" in caplog.text


async def test_application_points_to_its_live_assist_session(client):
    headers, application_id, body = await owner_with_assist(client)

    during = (await client.get(f"/api/v1/service-sessions/{application_id}", headers=headers)).json()
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    after = (await client.get(f"/api/v1/service-sessions/{application_id}", headers=headers)).json()

    assert during["active_assist_session_id"] == body["id"]
    assert after["active_assist_session_id"] is None


async def test_application_works_without_assist_module(client, monkeypatch):
    headers, application_id, _ = await owner_with_assist(client)
    monkeypatch.setattr(applications_service, "active_assist_lookup", None)

    response = await client.get(f"/api/v1/service-sessions/{application_id}", headers=headers)

    assert response.status_code == 200
    assert response.json()["active_assist_session_id"] is None
