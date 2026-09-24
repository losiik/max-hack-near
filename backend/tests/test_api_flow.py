from tests.helpers import fill, go_next, login, read_confirmation_code, start_session


async def test_owner_passes_all_steps_and_submits(client):
    headers = await login(client, "ludmila")
    session_id = await start_session(client, headers)

    empty_step = await go_next(client, headers, session_id)
    assert empty_step.status_code == 422
    assert {item["element_id"] for item in empty_step.json()["error"]["details"]["errors"]} == {
        "benefit_category",
        "benefit_reason",
    }

    await fill(
        client,
        headers,
        session_id,
        {"benefit_category": "pensioner", "benefit_reason": "certificate"},
    )
    assert (await go_next(client, headers, session_id)).status_code == 200

    await fill(
        client,
        headers,
        session_id,
        {
            "region": "spb",
            "address": "Невский проспект, 1, кв. 2",
            "ownership_type": "owner",
            "living_area": 2,
        },
    )
    too_small = await go_next(client, headers, session_id)
    assert too_small.status_code == 422
    assert too_small.json()["error"]["details"]["errors"][0]["code"] == "out_of_range"

    await fill(client, headers, session_id, {"living_area": 54.5})
    assert (await go_next(client, headers, session_id)).status_code == 200

    state = await fill(
        client,
        headers,
        session_id,
        {
            "full_name": "Петрова Людмила Ивановна",
            "birth_date": "1956-03-12",
            "snils": "123456",
            "family_size": 2,
        },
    )
    assert [item["element_id"] for item in state["errors"]] == ["snils"]
    assert state["errors"][0]["details"] == "Формат: 123-456-789 00"

    await fill(client, headers, session_id, {"snils": "123-456-789 00"})
    assert (await go_next(client, headers, session_id)).status_code == 200

    await fill(client, headers, session_id, {"income_type": "pension", "monthly_income": 18400})
    assert (await go_next(client, headers, session_id)).status_code == 200

    await fill(
        client,
        headers,
        session_id,
        {
            "payment_method": "bank",
            "bank_bik": "044030653",
            "account_number": "40817810099910004312",
        },
    )
    assert (await go_next(client, headers, session_id)).status_code == 200

    await fill(client, headers, session_id, {"consent_personal_data": True})
    last_step = await go_next(client, headers, session_id)
    assert last_step.json()["current_step"]["id"] == "confirmation"

    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    code = await read_confirmation_code(client, headers, session_id)

    submitted = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": code},
        headers=headers,
    )
    assert submitted.status_code == 200
    assert submitted.json()["application_number"].startswith("ЖКУ-")

    final = await client.get(f"/api/v1/service-sessions/{session_id}", headers=headers)
    assert final.json()["status"] == "submitted"
    assert final.json()["values"]["snils"] == "123-456-789 00"


async def test_confirmation_code_cannot_be_stored_in_form(client):
    headers = await login(client, "ludmila")
    session_id = await start_session(client, headers)

    response = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"confirmation_code": "1234"}},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_another_user_cannot_touch_foreign_application(client):
    owner_headers = await login(client, "ludmila")
    session_id = await start_session(client, owner_headers)

    stranger_headers = await login(client, "oleg")
    read = await client.get(f"/api/v1/service-sessions/{session_id}", headers=stranger_headers)
    edit = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"family_size": 9}},
        headers=stranger_headers,
    )
    submit = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "1234"},
        headers=stranger_headers,
    )

    assert read.status_code == 403
    assert edit.status_code == 403
    assert submit.status_code == 403


async def test_requests_without_token_are_rejected(client):
    response = await client.get("/api/v1/services")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
