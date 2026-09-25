from uuid import uuid4

from max_assist.modules.assist import journal
from max_assist.modules.assist.events import Delivery
from max_assist.modules.assist.models import SessionEvent


def message(event, payload, seq=None, actor=None):
    return {
        "event": event,
        "session_id": str(uuid4()),
        "seq": seq,
        "sent_at": "2026-09-18T10:00:00+00:00",
        "actor": actor,
        "payload": payload,
    }


def test_field_values_never_reach_the_journal():
    owner_payload = {
        "element_ids": ["snils"],
        "current_step": {
            "elements": [
                {"id": "snils", "view": {"state": "filled", "value": "123-456-789 00", "locked": False}},
                {"id": "full_name", "view": {"state": "filled", "value": "Петрова Людмила", "locked": False}},
                {"id": "family_info", "view": None},
            ]
        },
        "errors": [],
    }

    delivery = Delivery([uuid4()], message("form.field_updated", owner_payload, seq=5))

    rows = journal.entries(uuid4(), [delivery])

    assert rows[0].payload == {"element_ids": ["snils"], "states": {"snils": "filled"}}
    assert "123-456-789" not in str(rows[0].payload)
    assert rows[0].seq == 5


def test_one_event_sent_to_many_is_written_once_and_without_details():
    payload = {
        "step_id": "family",
        "errors": [
            {
                "element_id": "snils",
                "code": "invalid_format",
                "message": "Неверный формат",
                "details": "Формат",
            }
        ],
    }
    deliveries = [Delivery([uuid4()], message("form.validation_failed", payload, seq=7)) for _ in range(3)]

    rows = journal.entries(uuid4(), deliveries)

    assert len(rows) == 1
    assert rows[0].payload == {
        "step_id": "family",
        "errors": [{"element_id": "snils", "code": "invalid_format"}],
    }


def test_snapshots_pointer_and_closing_are_not_written():
    deliveries = [
        Delivery([uuid4()], message("session.snapshot", {"values": {"snils": "123-456-789 00"}})),
        Delivery([uuid4()], message("annotation.pointer", {"element_id": "snils", "rel_x": 0.5})),
        Delivery([uuid4()], close_code=4009),
    ]

    assert journal.entries(uuid4(), deliveries) == []


def test_author_of_the_event_is_kept():
    author = uuid4()
    actor = {"participant_id": str(author), "role": "owner", "display_name": "Людмила П."}

    rows = journal.entries(
        uuid4(),
        [Delivery([], message("owner.confusion_flagged", {"element_id": "snils"}, actor=actor))],
    )

    assert rows[0].actor_participant_id == author
    assert rows[0].seq is None
    assert rows[0].event_type == "owner.confusion_flagged"


async def test_failed_journal_write_is_logged_not_raised(client, caplog):
    orphan = SessionEvent(assist_session_id=uuid4(), event_type="session.activated", payload={})

    await journal.store([orphan])

    assert "journal write failed" in caplog.text
