from datetime import timedelta
from uuid import UUID

from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession
from tests.helpers import (
    STEP_VALUES,
    fill,
    go_next,
    login,
    navigate,
    reach_confirmation,
    read_confirmation_code,
    start_session,
)


async def reach_step(client, headers, session_id, step_id):
    for name, values in STEP_VALUES.items():
        if name == step_id:
            return
        await fill(client, headers, session_id, values)
        response = await go_next(client, headers, session_id)
        assert response.status_code == 200, response.text


async def submit(client, headers, session_id):
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    code = await read_confirmation_code(client, headers, session_id)
    response = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": code},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["application_number"]


async def test_application_numbers_stay_unique_after_reset(client):
    ludmila = await login(client, "ludmila")
    anna = await login(client, "anna")
    oleg = await login(client, "oleg")
    await client.post("/api/v1/dev/reset", headers=oleg)

    first = await submit(client, ludmila, await start_session(client, ludmila))
    second = await submit(client, anna, await start_session(client, anna))
    await client.post("/api/v1/dev/reset", headers=ludmila)
    created = await client.post(
        "/api/v1/service-sessions",
        json={"service_code": "housing_compensation"},
        headers=oleg,
    )
    third = await submit(client, oleg, created.json()["id"])

    assert len({first, second, third}) == 3


async def test_errors_of_hidden_fields_disappear(client):
    headers = await login(client, "anna")
    session_id = await start_session(client, headers)
    await reach_step(client, headers, session_id, "payment")

    await fill(client, headers, session_id, {"payment_method": "bank"})
    failed = await go_next(client, headers, session_id)
    switched = await fill(
        client,
        headers,
        session_id,
        {"payment_method": "post", "post_office_index": "190000"},
    )
    passed = await go_next(client, headers, session_id)
    back = await navigate(client, headers, session_id, "back")

    assert {item["element_id"] for item in failed.json()["error"]["details"]["errors"]} == {
        "bank_bik",
        "account_number",
    }
    assert switched["errors"] == []
    assert passed.status_code == 200
    assert back.json()["current_step"]["id"] == "payment"
    assert back.json()["errors"] == []


async def test_all_applications_are_listed_without_filter(client):
    headers = await login(client, "anna")
    first = await start_session(client, headers)
    await client.post(f"/api/v1/service-sessions/{first}/cancel", headers=headers)
    created = await client.post(
        "/api/v1/service-sessions",
        json={"service_code": "housing_compensation"},
        headers=headers,
    )
    second = created.json()["id"]

    everything = await client.get("/api/v1/service-sessions", headers=headers)
    drafts = await client.get("/api/v1/service-sessions?status=draft", headers=headers)

    assert created.status_code == 201
    assert {item["id"] for item in everything.json()} == {first, second}
    assert [item["id"] for item in drafts.json()] == [second]


async def test_back_and_forth_keeps_progress_without_duplicates(client):
    headers = await login(client, "anna")
    session_id = await start_session(client, headers)
    await fill(client, headers, session_id, STEP_VALUES["category"])
    await go_next(client, headers, session_id)

    back = await navigate(client, headers, session_id, "back")
    stay = await navigate(client, headers, session_id, "goto", "category")
    forward = await go_next(client, headers, session_id)

    async with session_factory() as db:
        row = await db.get(ServiceSession, UUID(session_id))

    assert back.status_code == 200
    assert back.json()["current_step"]["id"] == "category"
    assert back.json()["values"]["benefit_category"] == "pensioner"
    assert stay.status_code == 200
    assert forward.json()["current_step"]["id"] == "address"
    assert [step["status"] for step in forward.json()["steps"]][:3] == ["completed", "current", "upcoming"]
    assert row.completed_step_ids == ["category"]


async def test_field_errors_are_kept_until_that_field_is_fixed(client):
    headers = await login(client, "anna")
    session_id = await start_session(client, headers)
    await reach_step(client, headers, session_id, "family")

    broken = await fill(client, headers, session_id, {"snils": "123", "family_size": 0})
    other_field = await fill(client, headers, session_id, {"full_name": "Петрова Анна Сергеевна"})
    fixed_one = await fill(client, headers, session_id, {"snils": "123-456-789 00"})
    reread = await client.get(f"/api/v1/service-sessions/{session_id}", headers=headers)

    assert {item["element_id"] for item in broken["errors"]} == {"snils", "family_size"}
    assert {item["element_id"] for item in other_field["errors"]} == {"snils", "family_size"}
    assert {item["element_id"] for item in fixed_one["errors"]} == {"family_size"}
    assert {item["element_id"] for item in reread.json()["errors"]} == {"family_size"}


async def test_new_code_after_delay_replaces_the_old_one(client):
    headers = await login(client, "anna")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    old_code = await read_confirmation_code(client, headers, session_id)

    async with session_factory() as db:
        row = await db.get(ServiceSession, UUID(session_id))
        row.confirmation_expires_at = row.confirmation_expires_at - timedelta(seconds=31)
        await db.commit()

    resent = await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    new_code = await read_confirmation_code(client, headers, session_id)

    if new_code != old_code:
        with_old = await client.post(
            f"/api/v1/service-sessions/{session_id}/submit",
            json={"confirmation_code": old_code},
            headers=headers,
        )
        assert with_old.json()["error"]["code"] == "confirmation_code_invalid"
        assert with_old.json()["error"]["details"]["attempts_left"] == 4

    with_new = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": new_code},
        headers=headers,
    )

    assert resent.status_code == 200
    assert with_new.status_code == 200
