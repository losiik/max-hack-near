import asyncio
from uuid import UUID

from sqlalchemy import func, select

from max_assist.db import session_factory
from max_assist.modules.assist.models import AssistParticipant
from tests.helpers import fill
from tests.test_assist_api import joined_helper, owner_with_assist


async def active_helpers(assist_id: str) -> int:
    async with session_factory() as db:
        return await db.scalar(
            select(func.count()).where(
                AssistParticipant.assist_session_id == UUID(assist_id),
                AssistParticipant.role != "owner",
                AssistParticipant.status == "active",
            )
        )


async def test_parallel_approvals_do_not_exceed_the_helpers_limit(client):
    headers, _, body = await owner_with_assist(client)
    await joined_helper(client, headers, body["id"], "sergey")
    _, anna = await joined_helper(client, headers, body["id"], "anna", approve=False)
    _, oleg = await joined_helper(client, headers, body["id"], "oleg", approve=False)

    responses = await asyncio.gather(
        client.post(f"/api/v1/assist-sessions/{body['id']}/participants/{anna}/approve", headers=headers),
        client.post(f"/api/v1/assist-sessions/{body['id']}/participants/{oleg}/approve", headers=headers),
    )

    assert sorted(response.status_code for response in responses) == [200, 409]
    assert await active_helpers(body["id"]) == 2


async def test_parallel_form_changes_get_distinct_event_numbers(client):
    headers, application_id, body = await owner_with_assist(client)
    helper_headers, _ = await joined_helper(client, headers, body["id"])
    state_url = f"/api/v1/assist-sessions/{body['id']}/state"
    before = (await client.get(state_url, headers=helper_headers)).json()["last_seq"]

    await asyncio.gather(
        *[fill(client, headers, application_id, {"family_size": size}) for size in range(1, 6)]
    )
    after = (await client.get(state_url, headers=helper_headers)).json()["last_seq"]

    assert after == before + 5
