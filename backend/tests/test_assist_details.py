from datetime import timedelta
from uuid import UUID

from max_assist.db import session_factory
from max_assist.modules.assist.models import AssistInvite
from max_assist.utils import now
from tests.test_assist_api import invite, joined_helper, owner_with_assist


async def test_helper_who_left_does_not_see_session_as_active(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])

    await client.post(f"/api/v1/assist-sessions/{body['id']}/leave", headers=helper_headers)
    listed = await client.get("/api/v1/assist-sessions?scope=active", headers=helper_headers)

    assert body["id"] not in [item["id"] for item in listed.json()]


async def test_expired_invite_is_not_offered_to_owner(client):
    headers, _, body = await owner_with_assist(client)
    created = await invite(client, headers, body["id"])

    async with session_factory() as db:
        row = await db.get(AssistInvite, UUID(created["id"]))
        row.expires_at = now() - timedelta(minutes=1)
        await db.commit()

    view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)

    assert view.json()["pending_invites"] == []


async def test_summary_of_session_nobody_joined(client):
    headers, _, body = await owner_with_assist(client)

    ended = await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)

    summary = ended.json()
    assert summary["started_at"] is None
    assert summary["duration_sec"] == 0
    assert summary["helpers"] == []
    assert summary["steps_completed"] == 0
