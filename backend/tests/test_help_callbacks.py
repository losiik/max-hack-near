from datetime import timedelta
from uuid import UUID

from sqlalchemy import select, update

from max_assist.db import session_factory
from max_assist.modules.assist.models import HelpCallback, SessionEvent
from max_assist.utils import now
from tests.helpers import login
from tests.test_assist_api import invite, joined_helper, owner_with_assist


async def busy_helper(client, user_key="sergey"):
    headers, application_id, body = await owner_with_assist(client)
    helper_headers = await login(client, user_key)
    token = (await invite(client, headers, body["id"]))["token"]
    declined = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=helper_headers)
    assert declined.status_code == 200, declined.text
    return headers, helper_headers, body, token, declined.json()["help_callback_id"]


async def callbacks_of(client, headers, role):
    return (await client.get(f"/api/v1/help-callbacks?as={role}", headers=headers)).json()


async def test_busy_helper_closes_the_invite_and_promises_to_come_back(client):
    headers, helper_headers, body, token, callback_id = await busy_helper(client)

    preview = (await client.get(f"/api/v1/assist-invites/{token}", headers=helper_headers)).json()
    accept = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=helper_headers)
    [for_owner] = await callbacks_of(client, headers, "owner")
    [for_helper] = await callbacks_of(client, helper_headers, "helper")

    assert preview["status"] == "declined"
    assert accept.status_code == 410
    assert accept.json()["error"]["code"] == "invite_declined"
    assert for_owner["id"] == for_helper["id"] == callback_id
    assert for_owner["status"] == "busy"
    assert for_owner["owner"]["display_name"] == "Людмила П."
    assert for_owner["helper"]["display_name"] == "Сергей К."
    assert for_owner["service"]["title"] == "Компенсация расходов на оплату ЖКУ"
    assert await callbacks_of(client, headers, "helper") == []

    async with session_factory() as db:
        journal = await db.scalars(
            select(SessionEvent.event_type).where(SessionEvent.assist_session_id == UUID(body["id"]))
        )
        assert "invite.declined" in list(journal)


async def test_helper_says_ready_and_owner_calls_again_with_one_tap(client):
    headers, helper_headers, body, _, callback_id = await busy_helper(client)
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)

    ready = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)
    [listed] = await callbacks_of(client, headers, "owner")
    called = await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)
    again = await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)

    assert ready.json()["status"] == "ready"
    assert ready.json()["ready_at"] is not None
    assert listed["status"] == "ready"
    assert called.status_code == 201, called.text
    new_session = called.json()["assist_session"]
    assert new_session["id"] != body["id"]
    assert new_session["status"] == "waiting"
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "help_callback_closed"
    assert await callbacks_of(client, headers, "owner") == []

    token = called.json()["invite"]["token"]
    joined = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=helper_headers)
    assert joined.json()["assist_session_id"] == new_session["id"]


async def test_calling_back_during_live_help_invites_into_the_same_session(client):
    headers, _, body, _, callback_id = await busy_helper(client)

    called = await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)

    assert called.status_code == 201
    assert called.json()["assist_session"]["id"] == body["id"]
    assert len(called.json()["assist_session"]["pending_invites"]) == 1


async def test_only_the_right_side_can_touch_the_promise(client):
    headers, helper_headers, _, _, callback_id = await busy_helper(client)
    stranger = await login(client, "anna")

    owner_ready = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=headers)
    stranger_ready = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=stranger)
    helper_call = await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=helper_headers)
    helper_dismiss = await client.delete(f"/api/v1/help-callbacks/{callback_id}", headers=helper_headers)
    unknown = await client.post(f"/api/v1/help-callbacks/{UUID(int=5)}/ready", headers=helper_headers)

    assert [
        response.status_code
        for response in (owner_ready, stranger_ready, helper_call, helper_dismiss, unknown)
    ] == [404, 404, 404, 404, 404]


async def test_owner_dismisses_the_promise(client):
    headers, helper_headers, _, _, callback_id = await busy_helper(client)

    first = await client.delete(f"/api/v1/help-callbacks/{callback_id}", headers=headers)
    second = await client.delete(f"/api/v1/help-callbacks/{callback_id}", headers=headers)
    ready = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)

    assert (first.status_code, second.status_code) == (204, 204)
    assert await callbacks_of(client, headers, "owner") == []
    assert ready.status_code == 409


async def test_pressing_ready_twice_changes_nothing(client):
    _, helper_headers, _, _, callback_id = await busy_helper(client)

    first = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)
    second = await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)

    assert second.status_code == 200
    assert second.json()["ready_at"] == first.json()["ready_at"]


async def test_saying_busy_twice_keeps_one_promise(client):
    headers, helper_headers, body, _, callback_id = await busy_helper(client)
    await client.post(f"/api/v1/help-callbacks/{callback_id}/ready", headers=helper_headers)
    token = (await invite(client, headers, body["id"]))["token"]

    declined = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=helper_headers)
    [listed] = await callbacks_of(client, headers, "owner")

    assert declined.json()["help_callback_id"] == callback_id
    assert listed["status"] == "busy"
    assert listed["ready_at"] is None


async def test_expired_promise_is_hidden_and_cannot_be_used(client):
    headers, _, _, _, callback_id = await busy_helper(client)
    async with session_factory() as db:
        await db.execute(
            update(HelpCallback)
            .where(HelpCallback.id == UUID(callback_id))
            .values(expires_at=now() - timedelta(minutes=1))
        )
        await db.commit()

    called = await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)

    assert await callbacks_of(client, headers, "owner") == []
    assert called.status_code == 409


async def test_owner_and_joined_helper_cannot_say_busy(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    token = (await invite(client, headers, body["id"]))["token"]

    own = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=headers)
    joined = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=helper_headers)

    assert own.status_code == 422
    assert joined.status_code == 409
    assert joined.json()["error"]["code"] == "already_participant"


async def test_busy_after_help_ended_creates_no_promise(client):
    headers, _, body = await owner_with_assist(client)
    helper_headers = await login(client, "sergey")
    token = (await invite(client, headers, body["id"]))["token"]
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)

    declined = await client.post(f"/api/v1/assist-invites/{token}/decline", headers=helper_headers)

    assert declined.status_code == 410
    assert declined.json()["error"]["code"] == "session_ended"
    assert await callbacks_of(client, helper_headers, "helper") == []
