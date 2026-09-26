from datetime import timedelta
from uuid import UUID, uuid4

from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession
from max_assist.utils import now
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


async def test_second_start_returns_the_same_draft(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    again = await client.post(
        "/api/v1/service-sessions",
        json={"service_code": "housing_compensation"},
        headers=headers,
    )

    assert again.status_code == 200
    assert again.json()["id"] == session_id


async def test_stale_version_is_rejected(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    first = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"benefit_category": "pensioner"}, "version": 1},
        headers=headers,
    )
    second = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"benefit_category": "large_family"}, "version": 1},
        headers=headers,
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "version_conflict"


async def test_navigation_limits(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    back_from_first = await navigate(client, headers, session_id, "back")
    locked = await navigate(client, headers, session_id, "goto", "payment")
    unknown_action = await navigate(client, headers, session_id, "sideways")

    assert back_from_first.status_code == 422
    assert back_from_first.json()["error"]["code"] == "first_step"
    assert locked.json()["error"]["code"] == "step_locked"
    assert unknown_action.status_code == 422


async def test_completed_step_can_be_reopened(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await fill(client, headers, session_id, STEP_VALUES["category"])
    await go_next(client, headers, session_id)

    back = await navigate(client, headers, session_id, "goto", "category")

    assert back.status_code == 200
    assert back.json()["current_step"]["id"] == "category"
    assert [step["status"] for step in back.json()["steps"]][:2] == ["current", "upcoming"]


async def test_code_is_issued_only_on_the_last_step(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await client.post(
        f"/api/v1/service-sessions/{session_id}/confirmation-code",
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "wrong_step"


async def test_code_cannot_be_requested_twice_in_a_row(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)

    first = await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    second = await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 422
    assert second.json()["error"]["code"] == "code_resend_too_soon"


async def test_wrong_code_decreases_attempts(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)

    first = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "0000"},
        headers=headers,
    )
    second = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "1111"},
        headers=headers,
    )

    assert first.json()["error"]["details"]["attempts_left"] == 4
    assert second.json()["error"]["details"]["attempts_left"] == 3


async def test_submit_without_code_request_is_rejected(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)

    response = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "1234"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_code_invalid"


async def test_incomplete_application_cannot_be_submitted(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "1234"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "step_invalid"
    assert response.json()["error"]["details"]["step_id"] == "category"


async def test_submitted_application_is_read_only(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    code = await read_confirmation_code(client, headers, session_id)
    await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": code},
        headers=headers,
    )

    edit = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"family_size": 5}},
        headers=headers,
    )

    assert edit.status_code == 409
    assert edit.json()["error"]["code"] == "service_session_closed"


async def test_cancelled_application_is_read_only(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    cancelled = await client.post(f"/api/v1/service-sessions/{session_id}/cancel", headers=headers)
    edit = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"family_size": 5}},
        headers=headers,
    )

    assert cancelled.json()["status"] == "cancelled"
    assert edit.status_code == 409
    assert edit.json()["error"]["code"] == "service_session_closed"


async def test_unknown_application_is_not_found(client):
    headers = await login(client, "sergey")

    response = await client.get(f"/api/v1/service-sessions/{uuid4()}", headers=headers)

    assert response.status_code == 404


async def test_malformed_body_is_reported_as_validation_error(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": "не объект"},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert response.json()["error"]["details"]["fields"]


async def test_unknown_element_is_not_found(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": {"nope": 1}},
        headers=headers,
    )

    assert response.status_code == 404


async def test_reset_removes_own_applications_only(client):
    owner_headers = await login(client, "sergey")
    await start_session(client, owner_headers)
    other_headers = await login(client, "oleg")
    other_session_id = await start_session(client, other_headers)

    removed = await client.post("/api/v1/dev/reset", headers=owner_headers)
    other_still_there = await client.get(
        f"/api/v1/service-sessions/{other_session_id}",
        headers=other_headers,
    )

    assert removed.json()["removed_service_sessions"] == 1
    assert other_still_there.status_code == 200


async def test_drafts_can_be_listed(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await client.get("/api/v1/service-sessions?status=draft", headers=headers)

    assert [item["id"] for item in response.json()] == [session_id]


async def test_owner_can_delete_application(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    removed = await client.delete(f"/api/v1/service-sessions/{session_id}", headers=headers)
    reread = await client.get(f"/api/v1/service-sessions/{session_id}", headers=headers)

    assert removed.status_code == 204
    assert reread.status_code == 404


async def test_application_cannot_be_deleted_by_another_user(client):
    owner_headers = await login(client, "sergey")
    session_id = await start_session(client, owner_headers)
    stranger_headers = await login(client, "oleg")

    forbidden = await client.delete(
        f"/api/v1/service-sessions/{session_id}",
        headers=stranger_headers,
    )
    reread = await client.get(f"/api/v1/service-sessions/{session_id}", headers=owner_headers)

    assert forbidden.status_code == 403
    assert reread.status_code == 200


async def test_next_from_the_last_step_is_rejected(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)

    response = await go_next(client, headers, session_id)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "last_step"


async def test_goto_without_step_is_rejected(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    response = await navigate(client, headers, session_id, "goto")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_wrong_option_and_wrong_type_are_reported(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    option = await fill(client, headers, session_id, {"benefit_category": "unknown"})
    wrong_type = await fill(client, headers, session_id, {"family_size": "два"})

    assert [(item["element_id"], item["code"]) for item in option["errors"]] == [
        ("benefit_category", "invalid_format")
    ]
    assert "family_size" not in wrong_type["values"]


async def test_value_can_be_cleared(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)

    filled = await fill(client, headers, session_id, {"family_size": 3})
    cleared = await fill(client, headers, session_id, {"family_size": ""})

    assert filled["values"]["family_size"] == 3
    assert "family_size" not in cleared["values"]


async def test_attempts_are_exhausted_after_five_wrong_codes(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)

    for _ in range(5):
        await client.post(
            f"/api/v1/service-sessions/{session_id}/submit",
            json={"confirmation_code": "0000"},
            headers=headers,
        )
    blocked = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": "0000"},
        headers=headers,
    )

    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "confirmation_attempts_exceeded"


async def test_expired_code_is_rejected(client):
    headers = await login(client, "sergey")
    session_id = await start_session(client, headers)
    await reach_confirmation(client, headers, session_id)
    await client.post(f"/api/v1/service-sessions/{session_id}/confirmation-code", headers=headers)
    code = await read_confirmation_code(client, headers, session_id)

    async with session_factory() as session:
        row = await session.get(ServiceSession, UUID(session_id))
        row.confirmation_expires_at = now() - timedelta(minutes=1)
        await session.commit()

    response = await client.post(
        f"/api/v1/service-sessions/{session_id}/submit",
        json={"confirmation_code": code},
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "confirmation_code_expired"
