import json

import pytest

from max_assist.config import settings
from tests.helpers import STEP_VALUES
from tests.test_assist_ws import active_helper, auth, closed_code, highlight, next_event, owner_with_assist

# не совпадает с подсказкой формата в описании услуги, поэтому его можно искать в тексте
SNILS = "112-233-445 95"


@pytest.fixture(autouse=True)
def yandex_key(monkeypatch):
    monkeypatch.setattr(settings, "yandex_api_key", "test-key")


def socket_url(assist_id, token):
    return f"/ws/assist/{assist_id}?token={token}"


def call_agent(api, voice, owner, assist_id):
    response = api.post(f"/api/v1/assist-sessions/{assist_id}/ai-agent", headers=auth(owner))
    assert response.status_code == 201, response.text
    call = next(call for call in voice.calls_for(assist_id) if call[0] == "call_agent")
    return json.loads(call[2])


def reach_family_step(api, owner, application_id):
    for step in ("category", "address"):
        api.patch(
            f"/api/v1/service-sessions/{application_id}/fields",
            json={"values": STEP_VALUES[step]},
            headers=auth(owner),
        )
        api.post(
            f"/api/v1/service-sessions/{application_id}/navigation",
            json={"action": "next"},
            headers=auth(owner),
        )
    api.patch(
        f"/api/v1/service-sessions/{application_id}/fields",
        json={"values": {**STEP_VALUES["family"], "snils": SNILS}},
        headers=auth(owner),
    )


def test_digital_employee_sees_the_form_without_personal_values(api, voice):
    owner, assist = owner_with_assist(api)
    reach_family_step(api, owner, assist["service_session_id"])
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], agent["token"])) as ws:
        snapshot = ws.receive_json()

    text = json.dumps(snapshot, ensure_ascii=False)
    me = snapshot["payload"]["session"]["me"]
    elements = {item["id"]: item for item in snapshot["payload"]["current_step"]["elements"]}

    assert snapshot["event"] == "session.snapshot"
    assert me["participant_id"] == agent["participant_id"]
    assert me["role"] == "ai_agent"
    assert "request_operator" in me["capabilities"]
    assert not {"edit_fields", "navigate", "submit", "view_sensitive_values"} & set(me["capabilities"])
    assert snapshot["payload"]["current_step"]["id"] == "family"
    # всё, что видит агент, уходит в модель: ни СНИЛС, ни ФИО, ни адреса там быть не должно
    assert SNILS not in text
    assert "Петрова Людмила Ивановна" not in text
    assert "Невский проспект" not in text
    assert elements["snils"]["view"]["value"] is None
    assert elements["snils"]["operator_hint"] is not None


def test_digital_employee_highlights_a_field_and_the_owner_sees_it(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], agent["token"])) as agent_ws:
            agent_ws.receive_json()
            highlight(agent_ws, "benefit_category")
            created = next_event(owner_ws, "annotation.created")
            ack = agent_ws.receive_json()

    assert created["payload"]["element_id"] == "benefit_category"
    assert created["payload"]["author"]["role"] == "ai_agent"
    assert created["payload"]["author"]["display_name"] == "Цифровой сотрудник"
    assert ack["event"] == "ack"


def test_digital_employee_cannot_highlight_a_field_of_another_step(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], agent["token"])) as ws:
        ws.receive_json()
        highlight(ws, "snils", request_id="a-1")
        error = ws.receive_json()

    assert error["event"] == "error"
    assert error["payload"]["request_id"] == "a-1"


def test_digital_employee_hears_about_validation_errors(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], agent["token"])) as ws:
        ws.receive_json()
        api.post(
            f"/api/v1/service-sessions/{assist['service_session_id']}/navigation",
            json={"action": "next"},
            headers=auth(owner),
        )
        failed = next_event(ws, "form.validation_failed")

    assert failed["payload"]["step_id"] == "category"
    assert failed["payload"]["errors"]


def test_agent_token_does_not_open_another_meeting_socket(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])
    _, other = owner_with_assist(api)

    with api.websocket_connect(socket_url(other["id"], agent["token"])) as ws:
        code = closed_code(ws)

    assert code == 4003


def test_socket_closes_when_the_digital_employee_is_let_go(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], owner)) as owner_ws:
        owner_ws.receive_json()
        with api.websocket_connect(socket_url(assist["id"], agent["token"])) as agent_ws:
            agent_ws.receive_json()
            api.delete(f"/api/v1/assist-sessions/{assist['id']}/ai-agent", headers=auth(owner))
            left = next_event(owner_ws, "participant.left")
            code = closed_code(agent_ws)

    with api.websocket_connect(socket_url(assist["id"], agent["token"])) as again:
        again_code = closed_code(again)

    assert left["payload"] == {"participant_id": agent["participant_id"], "reason": "removed"}
    assert code == 1000
    assert again_code == 4003


def test_digital_employee_learns_that_a_person_joined(api, voice):
    owner, assist = owner_with_assist(api)
    agent = call_agent(api, voice, owner, assist["id"])

    with api.websocket_connect(socket_url(assist["id"], agent["token"])) as ws:
        ws.receive_json()
        active_helper(api, owner, assist["id"])
        joined = next_event(ws, "participant.joined")

    assert joined["payload"]["participant"]["role"] == "invited_helper"
