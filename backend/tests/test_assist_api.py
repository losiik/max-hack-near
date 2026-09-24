from datetime import timedelta
from uuid import UUID, uuid4

from max_assist.db import session_factory
from max_assist.modules.assist.models import AssistInvite
from max_assist.utils import now
from tests.helpers import STEP_VALUES, fill, go_next, login, start_session


async def owner_with_assist(client):
    headers = await login(client, "ludmila")
    service_session_id = await start_session(client, headers)
    response = await client.post(
        "/api/v1/assist-sessions",
        json={"service_session_id": service_session_id},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return headers, service_session_id, response.json()


async def invite(client, headers, assist_id):
    response = await client.post(
        f"/api/v1/assist-sessions/{assist_id}/invites",
        json={"kind": "link"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def joined_helper(client, owner_headers, assist_id, user_key="sergey", approve=True):
    helper_headers = await login(client, user_key)
    token = (await invite(client, owner_headers, assist_id))["token"]
    accepted = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=helper_headers)
    assert accepted.status_code == 200, accepted.text
    participant_id = accepted.json()["participant_id"]

    if approve:
        approved = await client.post(
            f"/api/v1/assist-sessions/{assist_id}/participants/{participant_id}/approve",
            headers=owner_headers,
        )
        assert approved.status_code == 200, approved.text

    return helper_headers, participant_id


async def test_owner_starts_assist_for_own_draft(client):
    _, service_session_id, body = await owner_with_assist(client)

    assert body["status"] == "waiting"
    assert body["service_session_id"] == service_session_id
    assert body["owner"]["display_name"] == "Людмила П."
    assert body["me"]["role"] == "owner"
    assert "invite" in body["me"]["capabilities"]
    assert body["current_step"] == {"id": "category", "index": 1, "title": "Категория заявителя"}
    assert body["total_steps"] == 7
    assert [item["role"] for item in body["participants"]] == ["owner"]
    assert body["pending_invites"] == []


async def test_second_live_assist_points_to_the_first_one(client):
    headers, service_session_id, body = await owner_with_assist(client)

    again = await client.post(
        "/api/v1/assist-sessions",
        json={"service_session_id": service_session_id},
        headers=headers,
    )

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "assist_session_exists"
    assert again.json()["error"]["details"]["assist_session_id"] == body["id"]


async def test_assist_needs_own_open_application(client):
    owner_headers = await login(client, "ludmila")
    service_session_id = await start_session(client, owner_headers)
    stranger_headers = await login(client, "oleg")

    foreign = await client.post(
        "/api/v1/assist-sessions",
        json={"service_session_id": service_session_id},
        headers=stranger_headers,
    )
    await client.post(f"/api/v1/service-sessions/{service_session_id}/cancel", headers=owner_headers)
    closed = await client.post(
        "/api/v1/assist-sessions",
        json={"service_session_id": service_session_id},
        headers=owner_headers,
    )

    assert foreign.status_code == 403
    assert closed.status_code == 409
    assert closed.json()["error"]["code"] == "service_session_closed"


async def test_invite_link_and_preview(client):
    headers, _, body = await owner_with_assist(client)
    created = await invite(client, headers, body["id"])
    helper_headers = await login(client, "sergey")

    preview = await client.get(f"/api/v1/assist-invites/{created['token']}", headers=helper_headers)
    own_preview = await client.get(f"/api/v1/assist-invites/{created['token']}", headers=headers)
    owner_view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)

    assert created["deep_link"].endswith(f"?startapp=as_{created['token']}")
    assert created["delivery"] == "share_required"
    assert "Людмила П." in created["share_text"]
    assert preview.json()["status"] == "valid"
    assert preview.json()["owner"]["display_name"] == "Людмила П."
    assert preview.json()["current_step"] == {"index": 1, "total": 7, "title": "Категория заявителя"}
    assert preview.json()["requires_owner_approval"] is True
    assert preview.json()["is_owner"] is False
    assert own_preview.json()["is_owner"] is True
    assert [item["id"] for item in owner_view.json()["pending_invites"]] == [created["id"]]


async def test_stranger_does_not_see_the_session(client):
    headers, _, body = await owner_with_assist(client)
    stranger_headers = await login(client, "oleg")

    read = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=stranger_headers)
    invite_attempt = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/invites",
        json={"kind": "link"},
        headers=stranger_headers,
    )

    assert read.status_code == 404
    assert invite_attempt.status_code == 404


async def test_helper_waits_for_approval_then_joins(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"], approve=False)

    pending_view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=helper_headers)
    approved = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}/approve",
        headers=headers,
    )
    helper_view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=helper_headers)

    assert pending_view.json()["me"]["status"] == "pending"
    assert pending_view.json()["status"] == "waiting"
    assert approved.json()["status"] == "active"
    assert [(item["role"], item["status"]) for item in approved.json()["participants"]] == [
        ("owner", "active"),
        ("invited_helper", "active"),
    ]
    me = helper_view.json()["me"]
    assert me["role"] == "invited_helper"
    assert "annotate" in me["capabilities"]
    assert "invite" not in me["capabilities"]
    assert helper_view.json()["pending_invites"] is None


async def test_helper_cannot_manage_the_session(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"])

    invite_attempt = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/invites",
        json={"kind": "link"},
        headers=helper_headers,
    )
    end_attempt = await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=helper_headers)
    remove_attempt = await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}",
        headers=helper_headers,
    )

    assert invite_attempt.status_code == 403
    assert end_attempt.status_code == 403
    assert remove_attempt.status_code == 403


async def test_rejected_helper_loses_access(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"], "oleg", approve=False)

    rejected = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}/reject",
        headers=headers,
    )
    read = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=helper_headers)

    assert [item["role"] for item in rejected.json()["participants"]] == ["owner"]
    assert read.status_code == 404


async def test_removed_helper_loses_access(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"])

    removed = await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}",
        headers=headers,
    )
    read = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=helper_headers)

    assert [item["role"] for item in removed.json()["participants"]] == ["owner"]
    assert read.status_code == 404


async def test_helper_leaves_and_session_goes_on(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])

    left = await client.post(f"/api/v1/assist-sessions/{body['id']}/leave", headers=helper_headers)
    owner_view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)
    owner_leave = await client.post(f"/api/v1/assist-sessions/{body['id']}/leave", headers=headers)

    assert left.status_code == 204
    assert owner_view.json()["status"] == "active"
    assert [item["role"] for item in owner_view.json()["participants"]] == ["owner"]
    assert owner_leave.json()["error"]["code"] == "owner_cannot_leave"


async def test_invite_works_once_and_not_for_owner(client):
    headers, _, body = await owner_with_assist(client)
    created = await invite(client, headers, body["id"])
    sergey_headers = await login(client, "sergey")
    anna_headers = await login(client, "anna")

    owner_accept = await client.post(f"/api/v1/assist-invites/{created['token']}/accept", headers=headers)
    first = await client.post(f"/api/v1/assist-invites/{created['token']}/accept", headers=sergey_headers)
    second = await client.post(f"/api/v1/assist-invites/{created['token']}/accept", headers=anna_headers)
    preview = await client.get(f"/api/v1/assist-invites/{created['token']}", headers=anna_headers)

    assert owner_accept.status_code == 422
    assert owner_accept.json()["error"]["code"] == "owner_cannot_join"
    assert first.json()["status"] == "pending"
    assert second.status_code == 410
    assert second.json()["error"]["code"] == "invite_used"
    assert preview.json()["status"] == "used"


async def test_revoked_invite_cannot_be_used(client):
    headers, _, body = await owner_with_assist(client)
    created = await invite(client, headers, body["id"])
    helper_headers = await login(client, "sergey")

    revoked = await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/invites/{created['id']}",
        headers=headers,
    )
    preview = await client.get(f"/api/v1/assist-invites/{created['token']}", headers=helper_headers)
    accept = await client.post(f"/api/v1/assist-invites/{created['token']}/accept", headers=helper_headers)
    owner_view = await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)

    assert revoked.status_code == 204
    assert preview.json()["status"] == "revoked"
    assert accept.status_code == 410
    assert accept.json()["error"]["code"] == "invite_revoked"
    assert owner_view.json()["pending_invites"] == []


async def test_expired_invite_cannot_be_used(client):
    headers, _, body = await owner_with_assist(client)
    created = await invite(client, headers, body["id"])
    helper_headers = await login(client, "sergey")

    async with session_factory() as db:
        row = await db.get(AssistInvite, UUID(created["id"]))
        row.expires_at = now() - timedelta(minutes=1)
        await db.commit()

    preview = await client.get(f"/api/v1/assist-invites/{created['token']}", headers=helper_headers)
    accept = await client.post(f"/api/v1/assist-invites/{created['token']}/accept", headers=helper_headers)

    assert preview.json()["status"] == "expired"
    assert accept.status_code == 410
    assert accept.json()["error"]["code"] == "invite_expired"


async def test_unknown_invite_is_not_found(client):
    headers = await login(client, "sergey")

    preview = await client.get("/api/v1/assist-invites/not-a-real-token", headers=headers)
    accept = await client.post("/api/v1/assist-invites/not-a-real-token/accept", headers=headers)

    assert preview.status_code == 404
    assert accept.status_code == 404


async def test_unknown_session_is_not_found(client):
    headers = await login(client, "ludmila")

    read = await client.get(f"/api/v1/assist-sessions/{uuid4()}", headers=headers)
    end = await client.post(f"/api/v1/assist-sessions/{uuid4()}/end", headers=headers)

    assert read.status_code == 404
    assert end.status_code == 404


async def test_end_returns_summary_and_closes_everything(client):
    headers, service_session_id, body = await owner_with_assist(client)
    await fill(client, headers, service_session_id, STEP_VALUES["category"])
    await go_next(client, headers, service_session_id)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    spare = await invite(client, headers, body["id"])

    ended = await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    helper_summary = await client.get(f"/api/v1/assist-sessions/{body['id']}/summary", headers=helper_headers)
    anna_headers = await login(client, "anna")
    late = await client.post(f"/api/v1/assist-invites/{spare['token']}/accept", headers=anna_headers)
    again = await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)

    summary = ended.json()
    assert (summary["status"], summary["end_reason"]) == ("ended", "owner_ended")
    assert [item["display_name"] for item in summary["helpers"]] == ["Сергей К."]
    assert summary["steps_completed"] == 1
    assert summary["stopped_at_step"]["id"] == "address"
    assert summary["duration_sec"] >= 0
    assert summary["actions"]["can_continue"] is True
    assert helper_summary.status_code == 200
    assert late.status_code == 410
    assert late.json()["error"]["code"] == "session_ended"
    assert again.status_code == 410


async def test_active_scope_lists_only_live_sessions(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"], approve=False)

    owner_list = await client.get("/api/v1/assist-sessions?scope=active", headers=headers)
    helper_list = await client.get("/api/v1/assist-sessions?scope=active", headers=helper_headers)
    owner_item = next(item for item in owner_list.json() if item["id"] == body["id"])
    helper_item = next(item for item in helper_list.json() if item["id"] == body["id"])

    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    after = await client.get("/api/v1/assist-sessions?scope=active", headers=helper_headers)

    assert owner_item["my_role"] == "owner"
    assert helper_item["my_status"] == "pending"
    assert helper_item["owner_display_name"] == "Людмила П."
    assert helper_item["current_step"] == {"index": 1, "title": "Категория заявителя"}
    assert body["id"] not in [item["id"] for item in after.json()]
