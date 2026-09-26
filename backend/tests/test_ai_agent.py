import json
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy import select, update

from max_assist.config import settings
from max_assist.db import session_factory
from max_assist.modules.ai_assistant import service as ai_service
from max_assist.modules.ai_assistant.models import AgentTurn
from max_assist.modules.assist.models import AssistParticipant, SessionEvent
from max_assist.modules.assist.realtime import Viewer, hub
from max_assist.utils import now
from tests.helpers import login, start_session
from tests.test_assist_api import joined_helper, owner_with_assist

TURN = {
    "trigger": "question",
    "reply_text": "Если вы получаете пенсию по старости, выберите первый вариант",
    "tools": [{"name": "highlight", "element_id": "benefit_category"}],
    "guard_result": "passed",
    "latency_ms": 1840,
    "provider": "yandex/qwen3-235b-a22b-fp8/yandex",
}


@pytest.fixture(autouse=True)
def yandex_key(monkeypatch):
    monkeypatch.setattr(settings, "yandex_api_key", "test-key")


def agent_call(voice, assist_id):
    calls = [call for call in voice.calls_for(assist_id) if call[0] == "call_agent"]
    assert len(calls) == 1
    return json.loads(calls[0][2])


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


async def with_agent(client, voice):
    headers, application_id, assist = await owner_with_assist(client)
    response = await client.post(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=headers)
    assert response.status_code == 201, response.text
    return headers, application_id, response.json(), agent_call(voice, assist["id"])


async def roles(client, headers, assist_id):
    body = (await client.get(f"/api/v1/assist-sessions/{assist_id}", headers=headers)).json()
    return [item["role"] for item in body["participants"]]


async def last_leave_reason(assist_id):
    async with session_factory() as db:
        rows = await db.scalars(
            select(SessionEvent)
            .where(SessionEvent.assist_session_id == assist_id, SessionEvent.event_type == "participant.left")
            .order_by(SessionEvent.id)
        )
        return [row.payload["reason"] for row in rows][-1]


async def silent_for_minutes(participant_id, minutes):
    async with session_factory() as db:
        await db.execute(
            update(AssistParticipant)
            .where(AssistParticipant.id == participant_id)
            .values(joined_at=now() - timedelta(minutes=minutes))
        )
        await db.commit()


async def test_owner_calls_the_digital_employee_from_the_application(client, voice):
    headers = await login(client)
    application_id = await start_session(client, headers)

    response = await client.post(f"/api/v1/service-sessions/{application_id}/ai-agent", headers=headers)
    assist = response.json()["assist_session"]
    agent = next(item for item in assist["participants"] if item["role"] == "ai_agent")
    metadata = agent_call(voice, assist["id"])

    assert response.status_code == 201
    assert assist["status"] == "active"
    assert agent["status"] == "active"
    assert agent["display_name"] == "Цифровой сотрудник"
    assert agent["badge"] == {"label": "Цифровой сотрудник", "verified": True}
    assert metadata["assist_session_id"] == assist["id"]
    assert metadata["participant_id"] == agent["id"]
    # сначала комната с записью, потом агент
    calls = [call[0] for call in voice.calls_for(assist["id"])]
    assert calls.index("open") < calls.index("call_agent")


async def test_digital_employee_joins_a_waiting_session_without_approval(client, voice):
    _, _, body, metadata = await with_agent(client, voice)

    assert body["status"] == "active"
    assert body["started_at"] is not None
    assert metadata["participant_id"] in [item["id"] for item in body["participants"]]


async def test_only_one_digital_employee_per_meeting(client, voice):
    headers, _, body, _ = await with_agent(client, voice)

    again = await client.post(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "ai_agent_exists"


async def test_digital_employee_is_not_called_while_a_person_helps(client):
    headers, _, assist = await owner_with_assist(client)
    await joined_helper(client, headers, assist["id"])

    response = await client.post(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "human_helper_present"


async def test_helper_cannot_call_the_digital_employee(client):
    headers, _, assist = await owner_with_assist(client)
    helper, _ = await joined_helper(client, headers, assist["id"])

    response = await client.post(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=helper)

    assert response.status_code == 403


async def test_without_yandex_key_the_digital_employee_is_unavailable(client, voice, monkeypatch):
    monkeypatch.setattr(settings, "yandex_api_key", "")
    headers, _, assist = await owner_with_assist(client)

    response = await client.post(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=headers)

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "digital_employee_unavailable"
    assert await roles(client, headers, assist["id"]) == ["owner"]
    assert voice.calls_for(assist["id"]) == []


async def test_when_livekit_cannot_call_the_agent_he_leaves_at_once(client, voice):
    voice.agent_up = False
    headers, _, assist = await owner_with_assist(client)

    response = await client.post(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=headers)

    assert response.status_code == 503
    assert await roles(client, headers, assist["id"]) == ["owner"]
    assert await last_leave_reason(assist["id"]) == "agent_unavailable"


async def test_owner_lets_the_digital_employee_go(client, voice):
    headers, _, body, _ = await with_agent(client, voice)

    response = await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)
    again = await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    assert response.status_code == 204
    assert await roles(client, headers, body["id"]) == ["owner"]
    assert await last_leave_reason(body["id"]) == "removed"
    assert again.status_code == 404


async def test_person_joins_while_the_digital_employee_is_there_but_cannot_send_him_away(client, voice):
    headers, _, body, _ = await with_agent(client, voice)
    helper, _ = await joined_helper(client, headers, body["id"])

    response = await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=helper)

    assert response.status_code == 403
    assert sorted(await roles(client, headers, body["id"])) == ["ai_agent", "invited_helper", "owner"]


async def test_digital_employee_leaves_by_himself(client, voice):
    headers, _, body, metadata = await with_agent(client, voice)

    response = await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=bearer(metadata["token"])
    )

    assert response.status_code == 204
    assert await roles(client, headers, body["id"]) == ["owner"]
    assert await last_leave_reason(body["id"]) == "left"


async def test_new_digital_employee_can_be_called_after_the_first_left(client, voice):
    headers, _, body, _ = await with_agent(client, voice)
    await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    again = await client.post(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    assert again.status_code == 201
    assert (await roles(client, headers, body["id"])).count("ai_agent") == 1


async def test_agent_token_does_not_open_another_meeting(client, voice):
    _, _, _, metadata = await with_agent(client, voice)
    sergey = await login(client, "sergey")
    application_id = await start_session(client, sergey)
    other = await client.post(
        "/api/v1/assist-sessions", json={"service_session_id": application_id}, headers=sergey
    )
    other_id = other.json()["id"]

    agent = bearer(metadata["token"])

    leave = await client.delete(f"/api/v1/assist-sessions/{other_id}/ai-agent", headers=agent)
    operator = await client.post(
        f"/api/v1/assist-sessions/{other_id}/operator-requests",
        json={"topic": "dont_understand"},
        headers=agent,
    )

    assert leave.status_code == 404
    assert operator.status_code == 404


async def test_agent_token_is_not_a_user_login(client, voice):
    _, application_id, body, metadata = await with_agent(client, voice)
    agent = bearer(metadata["token"])

    me = await client.get("/api/v1/me", headers=agent)
    edit = await client.patch(
        f"/api/v1/service-sessions/{application_id}/fields",
        json={"values": {"benefit_category": "pensioner"}},
        headers=agent,
    )
    submit = await client.post(f"/api/v1/service-sessions/{application_id}/submit", json={}, headers=agent)
    state = await client.get(f"/api/v1/assist-sessions/{body['id']}/state", headers=agent)

    assert me.status_code == 401
    assert edit.status_code == 401
    assert submit.status_code == 401
    assert state.status_code == 401


async def test_user_token_is_not_an_agent_token(client, voice):
    headers, _, _, _ = await with_agent(client, voice)

    response = await client.post("/api/v1/ai-turns", json=TURN, headers=headers)

    assert response.status_code == 401


async def test_digital_employee_records_what_he_said(client, voice):
    _, _, body, metadata = await with_agent(client, voice)

    response = await client.post("/api/v1/ai-turns", json=TURN, headers=bearer(metadata["token"]))
    async with session_factory() as db:
        row = await db.get(AgentTurn, UUID(response.json()["id"]))

    assert response.status_code == 201
    assert str(row.assist_session_id) == body["id"]
    assert str(row.participant_id) == metadata["participant_id"]
    assert row.reply_text == TURN["reply_text"]
    assert row.tools == [{"name": "highlight", "element_id": "benefit_category"}]
    assert (row.guard_result, row.latency_ms) == ("passed", 1840)


async def test_turn_with_unknown_trigger_or_tool_is_rejected(client, voice):
    _, _, _, metadata = await with_agent(client, voice)
    agent = bearer(metadata["token"])

    trigger = await client.post("/api/v1/ai-turns", json={**TURN, "trigger": "chat"}, headers=agent)
    tool = await client.post("/api/v1/ai-turns", json={**TURN, "tools": [{"name": "submit"}]}, headers=agent)

    assert trigger.status_code == 422
    assert tool.status_code == 422


async def test_digital_employee_calls_an_operator_with_a_summary(client, voice):
    _, _, body, metadata = await with_agent(client, voice)
    anna = await login(client, "anna")
    summary = "Людмила на шаге «Категория», не понимает, какую категорию выбрать"

    response = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/operator-requests",
        json={"topic": "dont_understand", "summary": summary},
        headers=bearer(metadata["token"]),
    )
    queue = (await client.get("/api/v1/operator/requests", headers=anna)).json()
    item = next(entry for entry in queue if entry["id"] == response.json()["id"])

    assert response.status_code == 201
    assert item["source"] == "ai_escalation"
    assert item["context"]["ai_summary"] == summary


async def test_summary_from_the_owner_is_ignored(client):
    headers, _, assist = await owner_with_assist(client)
    anna = await login(client, "anna")

    response = await client.post(
        f"/api/v1/assist-sessions/{assist['id']}/operator-requests",
        json={"topic": "other", "summary": "Напишите мне на почту"},
        headers=headers,
    )
    queue = (await client.get("/api/v1/operator/requests", headers=anna)).json()
    item = next(entry for entry in queue if entry["id"] == response.json()["id"])

    assert (item["source"], item["context"]["ai_summary"]) == ("owner", None)


async def test_digital_employee_that_left_cannot_call_an_operator(client, voice):
    headers, _, body, metadata = await with_agent(client, voice)
    await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    response = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/operator-requests",
        json={"topic": "dont_understand"},
        headers=bearer(metadata["token"]),
    )

    assert response.status_code == 403


async def test_digital_employee_that_never_came_is_let_go(client, voice):
    headers, _, body, metadata = await with_agent(client, voice)
    await silent_for_minutes(metadata["participant_id"], 5)

    async with session_factory() as db:
        dropped = await ai_service.drop_silent(db)

    assert dropped >= 1
    assert await roles(client, headers, body["id"]) == ["owner"]
    assert await last_leave_reason(body["id"]) == "agent_unavailable"


async def test_digital_employee_on_the_line_stays(client, voice):
    headers, _, body, metadata = await with_agent(client, voice)
    await silent_for_minutes(metadata["participant_id"], 5)
    assist_id, participant_id = UUID(body["id"]), UUID(metadata["participant_id"])
    connection, _ = hub.connect(assist_id, Viewer(participant_id, "ai_agent", "active", "агент"), object())

    try:
        async with session_factory() as db:
            await ai_service.drop_silent(db)
    finally:
        hub.disconnect(assist_id, participant_id, connection)

    assert "ai_agent" in await roles(client, headers, body["id"])


async def test_just_called_digital_employee_is_not_let_go(client, voice):
    headers, _, body, _ = await with_agent(client, voice)

    async with session_factory() as db:
        await ai_service.drop_silent(db)

    assert "ai_agent" in await roles(client, headers, body["id"])


async def test_digital_employee_calls_an_operator_only_once(client, voice):
    _, _, body, metadata = await with_agent(client, voice)
    url = f"/api/v1/assist-sessions/{body['id']}/operator-requests"
    await client.post(url, json={"topic": "dont_understand"}, headers=bearer(metadata["token"]))

    again = await client.post(url, json={"topic": "dont_understand"}, headers=bearer(metadata["token"]))

    assert again.status_code == 409
    assert again.json()["error"]["code"] == "operator_request_exists"


async def test_turn_without_a_token_is_refused(client):
    response = await client.post("/api/v1/ai-turns", json=TURN)

    assert response.status_code == 401


async def test_digital_employee_joins_the_help_that_is_already_going(client, voice):
    headers, application_id, assist = await owner_with_assist(client)

    response = await client.post(f"/api/v1/service-sessions/{application_id}/ai-agent", headers=headers)

    assert response.status_code == 201
    assert response.json()["assist_session"]["id"] == assist["id"]


async def test_token_of_the_previous_digital_employee_does_not_send_away_the_new_one(client, voice):
    headers, _, body, first = await with_agent(client, voice)
    await client.delete(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)
    await client.post(f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=headers)

    response = await client.delete(
        f"/api/v1/assist-sessions/{body['id']}/ai-agent", headers=bearer(first["token"])
    )

    assert response.status_code == 404
    assert "ai_agent" in await roles(client, headers, body["id"])
