import json
import logging

from max_assist.modules.applications import service as applications_service
from tests.helpers import fill, go_next, login, start_session
from tests.test_assist_api import joined_helper, owner_with_assist

MARKERS = {
    "address": "Тайная улица, дом 7731",
    "full_name": "Секретова Маркерна Тайновна",
    "birth_date": "1937-04-19",
    "snils": "731-555-919 37",
    "monthly_income": 777123,
    "bank_bik": "049731555",
    "account_number": "40817810731555919377",
    "post_office_index": "731955",
}

STEPS = [
    {"benefit_category": "pensioner", "benefit_reason": "certificate"},
    {"region": "spb", "address": MARKERS["address"], "ownership_type": "owner", "living_area": 54.5},
    {
        "full_name": MARKERS["full_name"],
        "birth_date": MARKERS["birth_date"],
        "snils": MARKERS["snils"],
        "family_size": 2,
    },
    {"income_type": "pension", "monthly_income": MARKERS["monthly_income"]},
    {
        "payment_method": "bank",
        "bank_bik": MARKERS["bank_bik"],
        "account_number": MARKERS["account_number"],
        "post_office_index": MARKERS["post_office_index"],
    },
    {"consent_personal_data": True},
]


def as_text(response) -> str:
    assert response.status_code == 200, response.text
    return json.dumps(response.json(), ensure_ascii=False)


async def test_helper_never_receives_sensitive_values(client):
    headers, application_id, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    state_url = f"/api/v1/assist-sessions/{body['id']}/state"
    session_url = f"/api/v1/assist-sessions/{body['id']}"

    helper_payloads = []
    owner_payloads = []
    for values in STEPS:
        await fill(client, headers, application_id, values)
        helper_payloads.append(as_text(await client.get(state_url, headers=helper_headers)))
        helper_payloads.append(as_text(await client.get(session_url, headers=helper_headers)))
        owner_payloads.append(as_text(await client.get(state_url, headers=headers)))
        moved = await go_next(client, headers, application_id)
        assert moved.status_code == 200, moved.text
    helper_payloads.append(as_text(await client.get(state_url, headers=helper_headers)))

    helper_text = "\n".join(helper_payloads)
    owner_text = "\n".join(owner_payloads)
    for marker in MARKERS.values():
        assert str(marker) not in helper_text
    for field in ("full_name", "snils", "account_number"):
        assert MARKERS[field] in owner_text


async def test_form_change_is_recorded_in_the_session_sequence(client):
    headers, application_id, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    state_url = f"/api/v1/assist-sessions/{body['id']}/state"

    before = (await client.get(state_url, headers=helper_headers)).json()["last_seq"]
    await fill(client, headers, application_id, {"family_size": 3})
    after = (await client.get(state_url, headers=helper_headers)).json()["last_seq"]

    assert after == before + 1


async def test_broken_listener_does_not_break_saving(client, monkeypatch, caplog):
    async def broken(event, row, details):
        raise RuntimeError("socket layer is down")

    monkeypatch.setattr(applications_service, "listeners", [broken])
    headers = await login(client, "anna")
    application_id = await start_session(client, headers)

    with caplog.at_level(logging.ERROR, logger="max_assist.applications"):
        response = await client.patch(
            f"/api/v1/service-sessions/{application_id}/fields",
            json={"values": {"family_size": 3}},
            headers=headers,
        )

    assert response.status_code == 200
    assert response.json()["values"]["family_size"] == 3
    assert "listener failed on fields_updated" in caplog.text


async def test_state_is_only_for_connected_participants(client):
    headers, _, body = await owner_with_assist(client)
    waiting_headers, _ = await joined_helper(client, headers, body["id"], "oleg", approve=False)
    active_headers, _ = await joined_helper(client, headers, body["id"], "sergey")
    state_url = f"/api/v1/assist-sessions/{body['id']}/state"

    waiting = await client.get(state_url, headers=waiting_headers)
    await client.post(f"/api/v1/assist-sessions/{body['id']}/leave", headers=active_headers)
    left = await client.get(state_url, headers=active_headers)
    owner = await client.get(state_url, headers=headers)

    assert waiting.status_code == 403
    assert left.status_code == 403
    assert owner.json()["session"]["me"]["role"] == "owner"
    assert owner.json()["current_step"]["id"] == "category"
    assert owner.json()["service"]["total_steps"] == 7
    assert owner.json()["last_seq"] >= 1
