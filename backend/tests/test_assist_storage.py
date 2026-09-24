from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from max_assist.db import session_factory
from max_assist.modules.assist import domain
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.identity.models import User
from tests.helpers import login, start_session


async def user_by_key(db, key: str) -> User:
    return await db.scalar(select(User).where(User.dev_key == key))


async def new_application(client) -> tuple[dict[str, str], UUID]:
    headers = await login(client, "ludmila")
    await login(client, "sergey")
    return headers, UUID(await start_session(client, headers))


async def test_session_with_participants_and_invites_is_stored(client):
    _, service_session_id = await new_application(client)

    async with session_factory() as db:
        owner = await user_by_key(db, "ludmila")
        helper = await user_by_key(db, "sergey")
        assist = domain.start(owner, service_session_id)
        invite, token = domain.create_invite(assist, owner)
        db.add(assist)
        await db.flush()
        domain.accept_invite(assist, invite, helper)
        await db.commit()
        assist_id = assist.id

    async with session_factory() as db:
        stored = await db.get(AssistSession, assist_id)

        assert stored.status == "waiting"
        assert [(item.role, item.status) for item in stored.participants] == [
            ("owner", "active"),
            ("invited_helper", "pending"),
        ]
        assert stored.invites[0].token_hash == domain.hash_token(token)
        assert stored.invites[0].used_by == helper.id
        assert stored.participants[1].invite_id == stored.invites[0].id


async def test_only_one_live_session_per_application(client):
    _, service_session_id = await new_application(client)

    async with session_factory() as db:
        owner = await user_by_key(db, "ludmila")
        db.add(domain.start(owner, service_session_id))
        await db.commit()

        db.add(domain.start(owner, service_session_id))
        with pytest.raises(IntegrityError):
            await db.commit()


async def test_ended_session_does_not_block_a_new_one(client):
    _, service_session_id = await new_application(client)

    async with session_factory() as db:
        owner = await user_by_key(db, "ludmila")
        first = domain.start(owner, service_session_id)
        db.add(first)
        await db.commit()

        domain.end_by_owner(first, owner)
        db.add(domain.start(owner, service_session_id))
        await db.commit()


async def test_same_user_is_stored_once_per_session(client):
    _, service_session_id = await new_application(client)

    async with session_factory() as db:
        owner = await user_by_key(db, "ludmila")
        helper = await user_by_key(db, "sergey")
        assist = domain.start(owner, service_session_id)
        db.add(assist)
        await db.flush()

        first_invite, _ = domain.create_invite(assist, owner)
        await db.flush()
        waiting = domain.accept_invite(assist, first_invite, helper)
        domain.reject(assist, owner, waiting.id)
        await db.flush()

        second_invite, _ = domain.create_invite(assist, owner)
        await db.flush()
        domain.accept_invite(assist, second_invite, helper)
        await db.commit()

        assert len(assist.participants) == 2


async def test_reset_removes_assist_sessions_of_the_application(client):
    headers, service_session_id = await new_application(client)

    async with session_factory() as db:
        owner = await user_by_key(db, "ludmila")
        assist = domain.start(owner, service_session_id)
        db.add(assist)
        await db.commit()
        assist_id = assist.id

    reset = await client.post("/api/v1/dev/reset", headers=headers)

    async with session_factory() as db:
        assert reset.status_code == 200
        assert await db.get(AssistSession, assist_id) is None
