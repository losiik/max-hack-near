from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from max_assist.db import engine, session_factory
from max_assist.errors import Conflict, Forbidden
from max_assist.modules.identity.models import User
from max_assist.modules.notifications import service as notifications
from max_assist.modules.trust import domain
from max_assist.modules.trust.models import Pairing, TrustedHelper
from max_assist.utils import now
from tests.helpers import login
from tests.test_assist_api import invite, owner_with_assist


async def forget_trust():
    async with session_factory() as db:
        await db.execute(delete(TrustedHelper))
        await db.execute(delete(Pairing))
        await db.commit()


@pytest.fixture(autouse=True)
async def clean_trust():
    # связь «близкий» меняет подключение по приглашениям, поэтому другим тестам она не должна остаться
    await forget_trust()
    notifications.outbox.clear()
    yield
    await forget_trust()
    await engine.dispose()


async def user_id(key):
    async with session_factory() as db:
        return await db.scalar(select(User.id).where(User.dev_key == key))


async def make_trusted(owner_key, helper_key, alias=None):
    async with session_factory() as db:
        trusted = TrustedHelper(
            owner_id=await user_id(owner_key),
            helper_id=await user_id(helper_key),
            alias=alias,
            status="active",
            verification_method="qr",
        )
        db.add(trusted)
        await db.commit()
        return str(trusted.id)


async def paired(client, method="qr", helper_key="oleg"):
    owner = await login(client, "ludmila")
    helper = await login(client, helper_key)
    pairing = (await client.post("/api/v1/pairings", json={"method": method}, headers=owner)).json()
    return owner, helper, pairing


async def test_qr_pairing_from_start_to_the_list_of_close_people(client):
    owner, helper, pairing = await paired(client)
    token = pairing["token"]

    preview = (await client.get(f"/api/v1/pairing-tokens/{token}", headers=helper)).json()
    claimed = await client.post(f"/api/v1/pairing-tokens/{token}/claim", headers=helper)
    waiting = (await client.get(f"/api/v1/pairings/{pairing['id']}", headers=owner)).json()
    confirmed = await client.post(
        f"/api/v1/pairings/{pairing['id']}/confirm", json={"alias": "Сосед Олег"}, headers=owner
    )
    mine = (await client.get("/api/v1/trusted-helpers", headers=owner)).json()
    theirs = (await client.get("/api/v1/trusted-helpers/helping-for", headers=helper)).json()
    counters = (await client.get("/api/v1/me", headers=owner)).json()["counters"]

    assert pairing["deep_link"] == pairing["qr_payload"]
    assert pairing["deep_link"].endswith(f"?startapp=pr_{token}")
    assert pairing["expires_at"] is not None
    assert preview == {"status": "valid", "owner": {"display_name": "Людмила П.", "photo_url": None}}
    assert claimed.json()["status"] == "claimed"
    assert waiting["status"] == "claimed"
    assert waiting["claimed_by"]["max_username"] == "oleg_n"
    assert confirmed.status_code == 201
    assert [(item["alias"], item["verification_method"]) for item in mine] == [("Сосед Олег", "qr")]
    assert mine[0]["helper"]["display_name"] == "Олег Н."
    assert mine[0]["last_helped_at"] is None
    assert [item["owner"]["display_name"] for item in theirs] == ["Людмила П."]
    assert counters["trusted_helpers"] == 1


async def test_used_code_and_second_pairing_of_the_same_person(client):
    owner, helper, pairing = await paired(client)
    await client.post(f"/api/v1/pairing-tokens/{pairing['token']}/claim", headers=helper)
    await client.post(f"/api/v1/pairings/{pairing['id']}/confirm", json={}, headers=owner)
    second = (await client.post("/api/v1/pairings", json={"method": "link"}, headers=owner)).json()

    used = (await client.get(f"/api/v1/pairing-tokens/{pairing['token']}", headers=helper)).json()
    again = (await client.get(f"/api/v1/pairing-tokens/{second['token']}", headers=helper)).json()
    claim_again = await client.post(f"/api/v1/pairing-tokens/{second['token']}/claim", headers=helper)
    reuse = await client.post(f"/api/v1/pairing-tokens/{pairing['token']}/claim", headers=helper)

    assert used["status"] == "used"
    assert again["status"] == "already_trusted"
    assert claim_again.json()["error"]["code"] == "already_trusted"
    assert reuse.json()["error"]["code"] == "pairing_used"


async def test_owner_cannot_add_themselves(client):
    owner, _, pairing = await paired(client)

    preview = (await client.get(f"/api/v1/pairing-tokens/{pairing['token']}", headers=owner)).json()
    claimed = await client.post(f"/api/v1/pairing-tokens/{pairing['token']}/claim", headers=owner)

    assert preview["status"] == "self"
    assert claimed.status_code == 422


async def test_qr_lives_five_minutes_and_link_a_day(client):
    owner, helper, qr = await paired(client)
    link = (await client.post("/api/v1/pairings", json={"method": "link"}, headers=owner)).json()
    async with session_factory() as db:
        await db.execute(
            update(Pairing)
            .where(Pairing.id == UUID(qr["id"]))
            .values(expires_at=now() - timedelta(seconds=1))
        )
        await db.commit()

    expired = await client.post(f"/api/v1/pairing-tokens/{qr['token']}/claim", headers=helper)
    state = (await client.get(f"/api/v1/pairings/{qr['id']}", headers=owner)).json()

    assert expired.status_code == 410
    assert state["status"] == "expired"
    lives = (now() - timedelta(minutes=1), now() + timedelta(days=1, minutes=1))
    assert lives[0] < now() + domain.TTL["link"] < lives[1]
    assert link["method"] == "link"


async def test_owner_who_does_not_answer_in_ten_minutes_has_to_start_again(client):
    owner, helper, pairing = await paired(client)
    await client.post(f"/api/v1/pairing-tokens/{pairing['token']}/claim", headers=helper)
    async with session_factory() as db:
        await db.execute(
            update(Pairing)
            .where(Pairing.id == UUID(pairing["id"]))
            .values(claimed_at=now() - timedelta(minutes=11))
        )
        await db.commit()

    late = await client.post(f"/api/v1/pairings/{pairing['id']}/confirm", json={}, headers=owner)

    assert late.status_code == 410


async def test_owner_says_this_is_not_the_right_person(client):
    owner, helper, pairing = await paired(client)
    await client.post(f"/api/v1/pairing-tokens/{pairing['token']}/claim", headers=helper)
    stranger = await login(client, "anna")

    foreign = await client.get(f"/api/v1/pairings/{pairing['id']}", headers=stranger)
    rejected = (await client.post(f"/api/v1/pairings/{pairing['id']}/reject", headers=owner)).json()
    confirm_after = await client.post(f"/api/v1/pairings/{pairing['id']}/confirm", json={}, headers=owner)
    mine = (await client.get("/api/v1/trusted-helpers", headers=owner)).json()

    assert foreign.status_code == 404
    assert rejected["status"] == "rejected"
    assert confirm_after.json()["error"]["code"] == "pairing_not_claimed"
    assert mine == []


async def test_owner_closes_the_code_before_anyone_scans_it(client):
    owner, helper, pairing = await paired(client)

    cancelled = await client.delete(f"/api/v1/pairings/{pairing['id']}", headers=owner)
    preview = (await client.get(f"/api/v1/pairing-tokens/{pairing['token']}", headers=helper)).json()
    unknown = await client.get("/api/v1/pairing-tokens/nothing-like-this", headers=helper)

    assert cancelled.status_code == 204
    assert preview["status"] == "used"
    assert unknown.status_code == 404


async def test_close_person_is_renamed_by_the_owner_and_either_side_can_leave(client):
    owner = await login(client, "ludmila")
    helper = await login(client, "sergey")
    trusted_id = await make_trusted("ludmila", "sergey")

    renamed = await client.patch(
        f"/api/v1/trusted-helpers/{trusted_id}", json={"alias": " Сын "}, headers=owner
    )
    too_long = await client.patch(
        f"/api/v1/trusted-helpers/{trusted_id}", json={"alias": "я" * 41}, headers=owner
    )
    by_helper = await client.patch(
        f"/api/v1/trusted-helpers/{trusted_id}", json={"alias": "Я"}, headers=helper
    )
    left = await client.delete(f"/api/v1/trusted-helpers/{trusted_id}", headers=helper)
    gone = await client.delete(f"/api/v1/trusted-helpers/{trusted_id}", headers=owner)

    assert renamed.json()["alias"] == "Сын"
    assert (too_long.status_code, by_helper.status_code) == (422, 403)
    assert (left.status_code, gone.status_code) == (204, 404)
    assert (await client.get("/api/v1/trusted-helpers", headers=owner)).json() == []


def test_no_more_than_five_close_people():
    owner = User(id=uuid4(), first_name="Людмила")
    pairing, _ = domain.create_pairing(owner, "qr")
    pairing.status, pairing.claimed_by, pairing.claimed_at = "claimed", uuid4(), now()

    with pytest.raises(Conflict) as error:
        domain.confirm(pairing, owner, domain.MAX_TRUSTED, None)

    assert error.value.code == "trusted_limit_reached"


async def delivered_by_bot(*args, **kwargs):
    return True


async def test_close_person_is_called_by_the_bot_and_joins_without_approval(client, monkeypatch):
    headers, _, body = await owner_with_assist(client)
    sergey = await login(client, "sergey")
    oleg = await login(client, "oleg")
    trusted_id = await make_trusted("ludmila", "sergey", "Сын Сергей")

    called = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/invites",
        json={"kind": "trusted_call", "trusted_helper_id": trusted_id},
        headers=headers,
    )
    token = called.json()["token"]
    [message] = notifications.messages_for(await user_id("sergey"))
    forwarded = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=oleg)
    preview = (await client.get(f"/api/v1/assist-invites/{token}", headers=sergey)).json()
    joined = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=sergey)
    monkeypatch.setattr(notifications, "help_requested", delivered_by_bot)
    with_bot = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/invites",
        json={"kind": "trusted_call", "trusted_helper_id": trusted_id},
        headers=headers,
    )

    assert called.json()["kind"] == "trusted_call"
    assert called.json()["delivery"] == "share_required"
    assert with_bot.json()["delivery"] == "bot_message"
    assert message.buttons[0].start_param == f"as_{token}"
    assert forwarded.status_code == 403
    assert (preview["you_are_trusted"], preview["requires_owner_approval"]) == (True, False)
    assert joined.json()["status"] == "active"
    session = (await client.get(f"/api/v1/assist-sessions/{body['id']}", headers=headers)).json()
    sergey_in = next(item for item in session["participants"] if item["display_name"] == "Сергей К.")
    assert (session["status"], sergey_in["role"]) == ("active", "trusted_helper")


async def test_close_person_opening_an_ordinary_link_joins_at_once(client):
    headers, _, body = await owner_with_assist(client)
    sergey = await login(client, "sergey")
    await make_trusted("ludmila", "sergey")
    token = (await invite(client, headers, body["id"]))["token"]

    joined = await client.post(f"/api/v1/assist-invites/{token}/accept", headers=sergey)

    assert joined.json()["status"] == "active"


async def test_only_own_close_people_can_be_called(client):
    headers, _, body = await owner_with_assist(client)
    oleg_link = await make_trusted("oleg", "sergey")
    url = f"/api/v1/assist-sessions/{body['id']}/invites"

    foreign = await client.post(
        url, json={"kind": "trusted_call", "trusted_helper_id": oleg_link}, headers=headers
    )
    missing = await client.post(url, json={"kind": "trusted_call"}, headers=headers)

    assert (foreign.status_code, missing.status_code) == (404, 422)


async def test_busy_close_person_called_again_joins_at_once(client):
    headers, _, body = await owner_with_assist(client)
    sergey = await login(client, "sergey")
    await make_trusted("ludmila", "sergey")
    token = (await invite(client, headers, body["id"]))["token"]
    callback_id = (await client.post(f"/api/v1/assist-invites/{token}/decline", headers=sergey)).json()[
        "help_callback_id"
    ]

    called = (await client.post(f"/api/v1/help-callbacks/{callback_id}/call", headers=headers)).json()
    joined = await client.post(f"/api/v1/assist-invites/{called['invite']['token']}/accept", headers=sergey)

    assert called["invite"]["kind"] == "trusted_call"
    assert joined.json()["status"] == "active"


async def test_after_help_the_owner_can_call_the_same_person_again(client):
    headers, _, body = await owner_with_assist(client)
    sergey = await login(client, "sergey")
    trusted_id = await make_trusted("ludmila", "sergey", "Сын Сергей")
    token = (await invite(client, headers, body["id"]))["token"]
    await client.post(f"/api/v1/assist-invites/{token}/accept", headers=sergey)

    helping = (await client.get("/api/v1/trusted-helpers/helping-for", headers=sergey)).json()
    summary = (await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)).json()
    mine = (await client.get("/api/v1/trusted-helpers", headers=headers)).json()

    assert helping[0]["active_assist_session_id"] == body["id"]
    assert summary["actions"]["can_call_again"] == [
        {"trusted_helper_id": trusted_id, "display_name": "Сын Сергей"}
    ]
    assert mine[0]["last_helped_at"] is not None


async def test_two_codes_scanned_by_one_person_add_them_once(client):
    owner, helper, first = await paired(client)
    second = (await client.post("/api/v1/pairings", json={"method": "qr"}, headers=owner)).json()
    await client.post(f"/api/v1/pairing-tokens/{first['token']}/claim", headers=helper)
    await client.post(f"/api/v1/pairing-tokens/{second['token']}/claim", headers=helper)

    added = await client.post(f"/api/v1/pairings/{first['id']}/confirm", json={}, headers=owner)
    twice = await client.post(f"/api/v1/pairings/{second['id']}/confirm", json={}, headers=owner)
    closing_used = await client.delete(f"/api/v1/pairings/{first['id']}", headers=owner)
    state = (await client.get(f"/api/v1/pairings/{first['id']}", headers=owner)).json()

    assert added.status_code == 201
    assert twice.json()["error"]["code"] == "already_trusted"
    assert closing_used.status_code == 204
    assert state["status"] == "confirmed"


def test_code_and_link_are_guarded_by_their_owners():
    owner = User(id=uuid4(), first_name="Людмила")
    stranger = User(id=uuid4(), first_name="Олег")
    pairing, _ = domain.create_pairing(owner, "qr")
    trusted = TrustedHelper(owner_id=owner.id, helper_id=uuid4(), status="active")

    with pytest.raises(Forbidden):
        domain.reject(pairing, stranger)
    with pytest.raises(Forbidden):
        domain.revoke(trusted, stranger)


async def test_stranger_cannot_answer_busy_for_the_close_person(client):
    headers, _, body = await owner_with_assist(client)
    oleg = await login(client, "oleg")
    trusted_id = await make_trusted("ludmila", "sergey")
    called = await client.post(
        f"/api/v1/assist-sessions/{body['id']}/invites",
        json={"kind": "trusted_call", "trusted_helper_id": trusted_id},
        headers=headers,
    )

    response = await client.post(f"/api/v1/assist-invites/{called.json()['token']}/decline", headers=oleg)

    assert response.status_code == 403
