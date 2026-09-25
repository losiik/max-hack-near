import json
from uuid import UUID

from max_assist import tasks
from max_assist.modules.assist import commands
from max_assist.modules.assist.realtime import Connection, Viewer
from tests.helpers import STEP_VALUES, fill, go_next, login
from tests.test_assist_api import joined_helper, owner_with_assist

SECRET_ADDRESS = "Тайная улица, дом 7731"


async def says(assist_id, participant_id, command, payload, role="invited_helper"):
    viewer = Viewer(participant_id=UUID(participant_id), role=role, status="active", display_name="Сергей К.")
    raw = json.dumps({"command": command, "request_id": "c-1", "payload": payload})
    return await commands.handle(UUID(assist_id), Connection(None, viewer), raw)


async def recorded_consultation(client):
    headers, application_id, body = await owner_with_assist(client)
    helper_headers, participant_id = await joined_helper(client, headers, body["id"])

    await client.post(
        f"/api/v1/service-sessions/{application_id}/submit",
        json={"confirmation_code": "1234"},
        headers=headers,
    )
    await fill(client, headers, application_id, STEP_VALUES["category"])
    await says(body["id"], participant_id, "annotation.highlight", {"element_id": "benefit_category"})
    owner_id = body["me"]["participant_id"]
    await says(body["id"], owner_id, "owner.flag_confusion", {"element_id": "benefit_reason"}, role="owner")
    await go_next(client, headers, application_id)
    await fill(client, headers, application_id, {"region": "spb", "address": SECRET_ADDRESS})
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    await tasks.wait_background()
    return headers, helper_headers, body


async def test_both_sides_find_the_consultation_in_their_history(client):
    headers, helper_headers, body = await recorded_consultation(client)

    as_owner = (await client.get("/api/v1/consultations?as=owner", headers=headers)).json()
    as_helper = (await client.get("/api/v1/consultations?as=helper", headers=helper_headers)).json()
    owner_as_helper = (await client.get("/api/v1/consultations?as=helper", headers=headers)).json()

    item = next(entry for entry in as_owner if entry["assist_session_id"] == body["id"])
    assert item["my_role"] == "owner"
    assert item["owner_display_name"] == "Людмила П."
    assert item["stats"] == {"highlights": 1, "confusions": 1}
    assert item["helpers"][0]["display_name"] == "Сергей К."
    assert body["id"] in [entry["assist_session_id"] for entry in as_helper]
    assert body["id"] not in [entry["assist_session_id"] for entry in owner_as_helper]


async def test_consultation_is_split_into_chapters_by_steps(client):
    headers, _, body = await recorded_consultation(client)

    detail = (await client.get(f"/api/v1/consultations/{body['id']}", headers=headers)).json()

    chapters = detail["chapters"]
    assert [chapter["step_id"] for chapter in chapters] == ["category", "address"]
    assert chapters[0]["title"] == "Категория заявителя"
    assert (chapters[0]["highlights"], chapters[0]["confusions"], chapters[0]["had_errors"]) == (1, 1, True)
    assert (chapters[1]["highlights"], chapters[1]["had_errors"]) == (0, False)
    assert chapters[1]["start_offset_ms"] >= chapters[0]["start_offset_ms"]
    assert detail["end_reason"] == "owner_ended"


async def test_replay_tells_the_story_without_values(client):
    headers, helper_headers, body = await recorded_consultation(client)

    owner_replay = await client.get(f"/api/v1/consultations/{body['id']}/replay", headers=headers)
    helper_replay = await client.get(f"/api/v1/consultations/{body['id']}/replay", headers=helper_headers)

    replay = owner_replay.json()
    events = replay["events"]
    assert [event["type"] for event in events] == [
        "session.created",
        "participant.join_requested",
        "participant.joined",
        "session.activated",
        "participant.status_changed",
        "form.validation_failed",
        "form.field_updated",
        "annotation.created",
        "owner.confusion_flagged",
        "navigation.step_changed",
        "form.field_updated",
        "session.ended",
    ]
    offsets = [event["offset_ms"] for event in events]
    assert offsets == sorted(offsets)
    numbered = [event["seq"] for event in events if event["seq"] is not None]
    assert len(numbered) == len(set(numbered))
    assert events[-2]["payload"] == {
        "element_ids": ["region", "address"],
        "states": {"region": "filled", "address": "filled"},
    }
    assert events[8]["payload"] == {"element_id": "benefit_reason"}
    assert [step["id"] for step in replay["steps"]][:2] == ["category", "address"]
    assert [participant["role"] for participant in replay["participants"]] == ["owner", "invited_helper"]
    assert helper_replay.status_code == 200
    assert SECRET_ADDRESS not in json.dumps([replay, helper_replay.json()], ensure_ascii=False)


async def test_consultation_is_closed_to_strangers_and_rejected_people(client):
    headers, _, body = await owner_with_assist(client)
    rejected_headers, participant_id = await joined_helper(client, headers, body["id"], "oleg", approve=False)
    await client.post(
        f"/api/v1/assist-sessions/{body['id']}/participants/{participant_id}/reject",
        headers=headers,
    )
    stranger_headers = await login(client, "anna")

    detail_url = f"/api/v1/consultations/{body['id']}"
    for other in (rejected_headers, stranger_headers):
        assert (await client.get(detail_url, headers=other)).status_code == 404
        assert (await client.get(f"{detail_url}/replay", headers=other)).status_code == 404

    history = (await client.get("/api/v1/consultations?as=helper", headers=rejected_headers)).json()
    assert body["id"] not in [entry["assist_session_id"] for entry in history]


async def test_meeting_stays_readable_after_the_application_is_gone(client):
    headers, helper_headers, body = await recorded_consultation(client)
    await client.post("/api/v1/dev/reset", headers=headers)

    history = (await client.get("/api/v1/consultations?as=owner", headers=headers)).json()
    item = next(entry for entry in history if entry["assist_session_id"] == body["id"])
    detail = (await client.get(f"/api/v1/consultations/{body['id']}", headers=headers)).json()
    replay = await client.get(f"/api/v1/consultations/{body['id']}/replay", headers=helper_headers)
    session = (await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)).json()

    assert item["service"]["title"] == "Компенсация расходов на оплату ЖКУ"
    assert item["service_session_status"] == "deleted"
    assert (item["steps_completed"], item["stopped_at_step"]) == (None, None)
    assert item["actions"]["can_continue"] is False
    assert [chapter["step_id"] for chapter in detail["chapters"]] == ["category", "address"]
    assert replay.status_code == 200
    assert (session["service_session_id"], session["current_step"]) == (None, None)


async def test_unknown_consultation_is_not_found(client):
    headers = await login(client, "ludmila")

    response = await client.get(f"/api/v1/consultations/{UUID(int=1)}", headers=headers)

    assert response.status_code == 404
