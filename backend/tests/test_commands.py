import json
from datetime import timedelta
from uuid import uuid4

import pytest

from max_assist.modules.assist import commands
from max_assist.modules.assist.annotations import board
from max_assist.modules.assist.realtime import Connection, Viewer
from max_assist.utils import now


def connection(status="active", role="invited_helper"):
    viewer = Viewer(participant_id=uuid4(), role=role, status=status, display_name="Сергей К.")
    return Connection(None, viewer)


async def call(assist_id, sender, command, payload=None, request_id="c-1"):
    body = {"command": command, "request_id": request_id}
    if payload is not None:
        body["payload"] = payload
    return await commands.handle(assist_id, sender, json.dumps(body))


@pytest.fixture(autouse=True)
def journal_off(monkeypatch):
    monkeypatch.setattr(commands.journal, "record_later", lambda assist_id, deliveries: None)


@pytest.fixture
def session_on_first_step():
    assist_id = uuid4()
    board.remember_elements(assist_id, {"benefit_category"})
    yield assist_id
    board.clear_step(assist_id)


async def test_pointer_needs_a_known_element_and_numeric_coordinates(session_on_first_step):
    sender = connection()

    unknown = await call(session_on_first_step, sender, "annotation.pointer", {"element_id": "snils"})
    broken = await call(
        session_on_first_step,
        sender,
        "annotation.pointer",
        {"element_id": "benefit_category", "rel_x": "слева"},
    )
    hidden = await call(session_on_first_step, sender, "annotation.pointer", {"visible": False})

    assert unknown["payload"]["code"] == "unknown_element"
    assert broken["payload"]["code"] == "bad_payload"
    assert hidden is None


async def test_pointer_is_dropped_when_it_comes_too_often(session_on_first_step):
    sender = connection()

    replies = [
        await call(session_on_first_step, sender, "annotation.pointer", {"element_id": "benefit_category"})
        for _ in range(25)
    ]

    assert replies.count(None) == 25
    assert commands.pointer_limit.allow((sender.viewer.participant_id, "pointer")) is False


async def test_owner_cannot_use_pointer(session_on_first_step):
    reply = await call(
        session_on_first_step,
        connection(role="owner"),
        "annotation.pointer",
        {"element_id": "benefit_category"},
    )

    assert reply["payload"]["code"] == "forbidden"


async def test_helper_cannot_control_the_owners_select(session_on_first_step):
    reply = await call(
        session_on_first_step,
        connection(),
        "owner.select_view",
        {"element_id": "benefit_category", "open": True, "scroll_top": 80},
    )

    assert reply["event"] == "error"
    assert reply["payload"]["code"] == "forbidden"


async def test_clear_checks_the_id_and_answers_with_an_empty_list(session_on_first_step):
    sender = connection()

    broken = await call(session_on_first_step, sender, "annotation.clear", {"annotation_id": "не-uuid"})
    nothing = await call(session_on_first_step, sender, "annotation.clear", {})

    assert broken["payload"]["code"] == "bad_payload"
    assert nothing["event"] == "ack"
    assert nothing["payload"]["result"]["annotation_ids"] == []


async def test_waiting_helper_cannot_clear(session_on_first_step):
    reply = await call(session_on_first_step, connection(status="pending"), "annotation.clear", {})

    assert reply["payload"]["code"] == "forbidden"


async def test_clearing_is_rate_limited(session_on_first_step):
    sender = connection()

    replies = [await call(session_on_first_step, sender, "annotation.clear", {}) for _ in range(8)]

    assert any(reply["payload"].get("code") == "rate_limited" for reply in replies)


async def test_payload_must_be_an_object(session_on_first_step):
    reply = await commands.handle(
        session_on_first_step,
        connection(),
        json.dumps({"command": "annotation.clear", "request_id": "c-1", "payload": "нет"}),
    )

    assert reply["payload"]["code"] == "bad_payload"


async def test_there_is_no_chat_anymore(session_on_first_step):
    for sender in (connection(), connection(role="owner")):
        reply = await call(session_on_first_step, sender, "message.send", {"text": "Здравствуйте"})

        assert reply["payload"]["code"] == "unknown_command"


async def test_confusion_flag_is_checked_and_limited(session_on_first_step):
    session = session_on_first_step
    owner = connection(role="owner")
    known = {"element_id": "benefit_category"}

    unknown = await call(session, connection(role="owner"), "owner.flag_confusion", {"element_id": "snils"})
    first = await call(session, owner, "owner.flag_confusion", known)
    second = await call(session, owner, "owner.flag_confusion", known)

    assert unknown["payload"]["code"] == "unknown_element"
    assert first["event"] == "ack"
    assert second["payload"]["code"] == "rate_limited"


async def test_idle_rate_limit_records_are_forgotten(session_on_first_step):
    idle, busy = connection(), connection()
    await call(session_on_first_step, idle, "annotation.clear", {})
    await call(session_on_first_step, busy, "annotation.clear", {})
    idle_key = (idle.viewer.participant_id, "annotation")
    busy_key = (busy.viewer.participant_id, "annotation")
    commands.annotation_limit.buckets[idle_key].updated = now() - timedelta(minutes=11)

    commands.prune_limits()

    assert idle_key not in commands.annotation_limit.buckets
    assert busy_key in commands.annotation_limit.buckets


async def test_unknown_session_has_no_elements_to_show(client):
    reply = await call(uuid4(), connection(), "annotation.highlight", {"element_id": "benefit_category"})

    assert reply["payload"]["code"] == "unknown_element"
