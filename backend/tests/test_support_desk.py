import asyncio
import logging
from uuid import UUID, uuid4

from sqlalchemy import delete

from max_assist import tasks
from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.support_desk import sync
from tests.helpers import STEP_VALUES, fill, forget_user, go_next, login, start_session
from tests.test_assist_api import joined_helper, owner_with_assist


async def ask_for_operator(client, user_key="ludmila", topic="dont_understand"):
    headers = await login(client, user_key)
    application_id = await start_session(client, headers)
    response = await client.post(
        f"/api/v1/service-sessions/{application_id}/operator-requests",
        json={"topic": topic},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return headers, application_id, response.json()


async def queue_ids(client, headers):
    response = await client.get("/api/v1/operator/requests", headers=headers)
    assert response.status_code == 200
    return [item["id"] for item in response.json()]


async def state(client, headers, assist_id):
    return (await client.get(f"/api/v1/assist-sessions/{assist_id}/state", headers=headers)).json()


async def elements(client, headers, assist_id):
    return {
        item["id"]: item for item in (await state(client, headers, assist_id))["current_step"]["elements"]
    }


async def test_staff_profile_is_shown_to_the_person_themselves(client):
    anna = await login(client, "anna")
    sergey = await login(client, "sergey")

    staff = (await client.get("/api/v1/me", headers=anna)).json()["staff"]
    ordinary = (await client.get("/api/v1/me", headers=sergey)).json()["staff"]

    assert staff == {
        "role": "mfc_operator",
        "organization": "МФЦ Фрунзенского района",
        "position": "Главный специалист",
        "verified": True,
    }
    assert ordinary is None


async def test_owner_calls_an_operator_straight_from_the_application(client):
    headers, application_id, body = await ask_for_operator(client)

    again = await client.post(
        f"/api/v1/assist-sessions/{body['assist_session']['id']}/operator-requests",
        json={"topic": "other"},
        headers=headers,
    )
    wrong_topic = await client.post(
        f"/api/v1/service-sessions/{application_id}/operator-requests",
        json={"topic": "anything"},
        headers=headers,
    )

    assert body["assist_session"]["status"] == "waiting"
    assert body["request"]["status"] == "queued"
    assert body["request"]["position"] >= 1
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "operator_request_exists"
    assert wrong_topic.status_code == 422


async def test_operator_sees_where_the_person_is_stuck_without_values(client):
    headers, application_id, body = await ask_for_operator(client, topic="form_error")
    await go_next(client, headers, application_id)
    anna = await login(client, "anna")

    queue = (await client.get("/api/v1/operator/requests", headers=anna)).json()

    item = next(entry for entry in queue if entry["id"] == body["request"]["id"])
    assert item["topic"] == "form_error"
    assert item["context"]["owner_display_name"] == "Людмила П."
    assert item["context"]["service_title"] == "Компенсация расходов на оплату ЖКУ"
    assert item["context"]["step"] == {"index": 1, "total": 7, "title": "Категория заявителя"}
    assert set(item["context"]["error_codes"]) == {"required"}
    assert item["waiting_sec"] >= 0


async def test_queue_is_only_for_staff(client):
    sergey = await login(client, "sergey")

    response = await client.get("/api/v1/operator/requests", headers=sergey)

    assert response.status_code == 403


async def test_operator_takes_the_request_and_joins_with_a_verified_badge(client):
    headers, _, body = await ask_for_operator(client)
    assist_id = body["assist_session"]["id"]
    anna = await login(client, "anna")

    claimed = await client.post(f"/api/v1/operator/requests/{body['request']['id']}/claim", headers=anna)
    session = (await client.get(f"/api/v1/assist-sessions/{assist_id}", headers=headers)).json()
    owner_state = await state(client, headers, assist_id)

    assert claimed.status_code == 200
    assert claimed.json()["assist_session_id"] == assist_id
    assert session["status"] == "active"
    operator = next(item for item in session["participants"] if item["role"] == "government_operator")
    assert operator["display_name"] == "Анна Смирнова"
    assert operator["badge"] == {"label": "Сотрудник МФЦ · МФЦ Фрунзенского района", "verified": True}
    assert owner_state["operator_request"]["status"] == "claimed"
    assert owner_state["operator_request"]["position"] is None
    assert body["request"]["id"] not in await queue_ids(client, anna)


async def test_operator_gets_hints_and_the_address_a_relative_would_not_see(client):
    headers, application_id, body = await ask_for_operator(client)
    assist_id = body["assist_session"]["id"]
    anna = await login(client, "anna")
    await client.post(f"/api/v1/operator/requests/{body['request']['id']}/claim", headers=anna)
    sergey, _ = await joined_helper(client, headers, assist_id)

    on_category = await elements(client, anna, assist_id)

    await fill(client, headers, application_id, STEP_VALUES["category"])
    await go_next(client, headers, application_id)
    await fill(client, headers, application_id, STEP_VALUES["address"])
    for_operator = await elements(client, anna, assist_id)
    for_relative = await elements(client, sergey, assist_id)

    assert on_category["benefit_category"]["operator_hint"]
    assert for_operator["address"]["view"]["value"] == STEP_VALUES["address"]["address"]
    assert for_relative["address"]["view"]["value"] is None


async def test_request_is_taken_only_once(client):
    _, _, body = await ask_for_operator(client)
    anna = await login(client, "anna")
    url = f"/api/v1/operator/requests/{body['request']['id']}/claim"

    first, second = await asyncio.gather(client.post(url, headers=anna), client.post(url, headers=anna))

    loser = first if first.status_code == 409 else second
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert loser.json()["error"]["code"] == "operator_request_taken"


async def test_only_staff_can_take_requests(client):
    _, _, body = await ask_for_operator(client)
    sergey = await login(client, "sergey")

    response = await client.post(f"/api/v1/operator/requests/{body['request']['id']}/claim", headers=sergey)

    assert response.status_code == 403


async def test_operator_without_consent_cannot_take_a_request(client):
    _, _, body = await ask_for_operator(client)
    await forget_user("anna")
    anna = await login(client, "anna", consent=False)

    refused = await client.post(f"/api/v1/operator/requests/{body['request']['id']}/claim", headers=anna)
    queue = await queue_ids(client, anna)

    assert refused.status_code == 409
    assert refused.json()["error"]["code"] == "recording_consent_required"
    assert body["request"]["id"] in queue


async def test_operator_finishes_and_leaves(client):
    headers, _, body = await ask_for_operator(client)
    assist_id = body["assist_session"]["id"]
    anna = await login(client, "anna")
    request_url = f"/api/v1/operator/requests/{body['request']['id']}"
    await client.post(f"{request_url}/claim", headers=anna)

    stranger = await client.post(f"{request_url}/complete", headers=headers)
    done = await client.post(f"{request_url}/complete", headers=anna)
    again = await client.post(f"{request_url}/complete", headers=anna)
    session = (await client.get(f"/api/v1/assist-sessions/{assist_id}", headers=headers)).json()

    assert (stranger.status_code, done.status_code, again.status_code) == (404, 204, 409)
    assert "government_operator" not in [item["role"] for item in session["participants"]]
    assert (await state(client, headers, assist_id))["operator_request"] is None


async def test_owner_changes_their_mind_while_waiting(client):
    headers, _, body = await ask_for_operator(client)
    assist_id = body["assist_session"]["id"]
    anna = await login(client, "anna")
    url = f"/api/v1/assist-sessions/{assist_id}/operator-requests/current"

    cancelled = await client.delete(url, headers=headers)
    again = await client.delete(url, headers=headers)

    assert (cancelled.status_code, again.status_code) == (204, 409)
    assert body["request"]["id"] not in await queue_ids(client, anna)


async def test_queue_keeps_the_order_of_arrival(client):
    ludmila, _, first = await ask_for_operator(client)
    oleg, _, second = await ask_for_operator(client, "oleg")
    anna = await login(client, "anna")

    order = await queue_ids(client, anna)
    before = (await state(client, oleg, second["assist_session"]["id"]))["operator_request"]["position"]
    await client.delete(
        f"/api/v1/assist-sessions/{first['assist_session']['id']}/operator-requests/current",
        headers=ludmila,
    )
    after = (await state(client, oleg, second["assist_session"]["id"]))["operator_request"]["position"]

    assert order.index(first["request"]["id"]) < order.index(second["request"]["id"])
    assert after == before - 1


async def test_ended_help_leaves_the_queue(client):
    headers, _, body = await ask_for_operator(client)
    anna = await login(client, "anna")

    await client.post(f"/api/v1/assist-sessions/{body['assist_session']['id']}/end", headers=headers)
    await tasks.wait_background()

    assert body["request"]["id"] not in await queue_ids(client, anna)


async def test_operator_can_be_called_into_help_that_is_already_going(client):
    headers, application_id, body = await owner_with_assist(client)

    by_session = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/operator-requests",
        json={"topic": "other"},
        headers=headers,
    )
    await client.delete(f"/api/v1/assist-sessions/{body['id']}/operator-requests/current", headers=headers)
    by_application = await client.post(
        f"/api/v1/service-sessions/{application_id}/operator-requests",
        json={"topic": "other"},
        headers=headers,
    )

    assert by_session.status_code == 201
    assert by_session.json()["status"] == "queued"
    assert by_application.json()["assist_session"]["id"] == body["id"]


async def test_unknown_request_cannot_be_taken(client):
    anna = await login(client, "anna")

    response = await client.post(f"/api/v1/operator/requests/{uuid4()}/claim", headers=anna)

    assert response.status_code == 404


async def test_removed_operator_can_still_close_the_request(client):
    headers, _, body = await ask_for_operator(client)
    anna = await login(client, "anna")
    request_url = f"/api/v1/operator/requests/{body['request']['id']}"
    participant = (await client.post(f"{request_url}/claim", headers=anna)).json()["participant_id"]
    await client.delete(
        f"/api/v1/assist-sessions/{body['assist_session']['id']}/participants/{participant}",
        headers=headers,
    )

    done = await client.post(f"{request_url}/complete", headers=anna)

    assert done.status_code == 204


async def test_request_of_a_deleted_application_shows_without_a_step(client):
    headers, application_id, body = await ask_for_operator(client)
    async with session_factory() as db:
        await db.execute(delete(ServiceSession).where(ServiceSession.id == UUID(application_id)))
        await db.commit()
    anna = await login(client, "anna")

    queue = (await client.get("/api/v1/operator/requests", headers=anna)).json()

    item = next(entry for entry in queue if entry["id"] == body["request"]["id"])
    assert (item["context"]["step"], item["context"]["error_codes"]) == (None, [])
    assert item["context"]["service_title"] == "housing_compensation"


async def test_failure_to_close_a_request_is_logged(monkeypatch, caplog):
    async def broken(db, assist_id):
        raise RuntimeError("database is down")

    monkeypatch.setattr(sync.service, "close_for_ended", broken)

    with caplog.at_level(logging.ERROR, logger="max_assist.support_desk"):
        await sync.close_request(uuid4())

    assert "could not close operator request" in caplog.text
