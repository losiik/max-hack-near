import re

from sqlalchemy import delete, select

from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.identity.models import User

STEP_VALUES = {
    "category": {"benefit_category": "pensioner", "benefit_reason": "certificate"},
    "address": {
        "region": "spb",
        "address": "Невский проспект, 1, кв. 2",
        "ownership_type": "owner",
        "living_area": 54.5,
    },
    "family": {
        "full_name": "Петрова Людмила Ивановна",
        "birth_date": "1956-03-12",
        "snils": "123-456-789 00",
        "family_size": 2,
    },
    "income": {"income_type": "pension", "monthly_income": 18400},
    "payment": {"payment_method": "post", "post_office_index": "190000"},
    "review": {"consent_personal_data": True},
}

ALL_VALUES = {key: value for step in STEP_VALUES.values() for key, value in step.items()}


async def forget_user(dev_key: str | None = None, max_user_id: int | None = None):
    async with session_factory() as session:
        if dev_key is not None:
            query = select(User).where(User.dev_key == dev_key)
        else:
            query = select(User).where(User.max_user_id == max_user_id)

        user = await session.scalar(query)
        if user is None:
            return

        await session.execute(delete(ServiceSession).where(ServiceSession.owner_id == user.id))
        await session.delete(user)
        await session.commit()


async def login(client, user_key="ludmila"):
    response = await client.post("/api/v1/auth/dev-login", json={"user_key": user_key})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def start_session(client, headers):
    await client.post("/api/v1/dev/reset", headers=headers)
    response = await client.post(
        "/api/v1/service-sessions",
        json={"service_code": "housing_compensation"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def fill(client, headers, session_id, values):
    response = await client.patch(
        f"/api/v1/service-sessions/{session_id}/fields",
        json={"values": values},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


async def navigate(client, headers, session_id, action, step_id=None):
    return await client.post(
        f"/api/v1/service-sessions/{session_id}/navigation",
        json={"action": action, "step_id": step_id},
        headers=headers,
    )


async def go_next(client, headers, session_id):
    return await navigate(client, headers, session_id, "next")


async def reach_confirmation(client, headers, session_id):
    for values in STEP_VALUES.values():
        await fill(client, headers, session_id, values)
        response = await go_next(client, headers, session_id)
        assert response.status_code == 200, response.text
    assert response.json()["current_step"]["id"] == "confirmation"


async def read_confirmation_code(client, headers, session_id):
    inbox = await client.get(f"/api/v1/service-sessions/{session_id}/demo-inbox", headers=headers)
    return re.search(r"код подтверждения (\d{4})", inbox.json()[0]["text"]).group(1)
