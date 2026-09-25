from datetime import timedelta
from uuid import UUID

from sqlalchemy import update

from max_assist.db import session_factory
from max_assist.modules.assist.models import AssistSession, SessionEvent
from max_assist.modules.voice import past_help
from max_assist.modules.voice.past_help import fragments
from max_assist.utils import now
from tests.helpers import STEP_VALUES, fill, go_next, login, start_session
from tests.test_assist_api import joined_helper, owner_with_assist
from tests.test_recordings import SECOND, egress_event, finished, send

START = now().replace(microsecond=0)


def at(seconds, event_type, **payload):
    return SessionEvent(
        occurred_at=START + timedelta(seconds=seconds), event_type=event_type, payload=payload
    )


def created(step="category"):
    return at(0, "session.created", step_id=step)


def step(seconds, to):
    return at(seconds, "navigation.step_changed", from_step_id="", to_step_id=to)


def joined(seconds, helper="sergey"):
    return at(seconds, "participant.joined", participant_id=helper, role="invited_helper")


def left(seconds, helper="sergey"):
    return at(seconds, "participant.left", participant_id=helper, reason="left")


def spans(found):
    return [(item.step_id, (item.begins - START).seconds, (item.ends - START).seconds) for item in found]


def test_steps_count_only_while_a_helper_is_there():
    journal = [
        created(),
        joined(30),
        step(60, "address"),
        step(120, "family"),
        left(150),
        step(200, "income"),
    ]

    found = fragments(journal, START + timedelta(seconds=300))

    assert spans(found) == [("category", 30, 60), ("address", 60, 120), ("family", 120, 150)]


def test_going_back_to_a_step_makes_a_second_fragment():
    journal = [created(), joined(0), step(40, "address"), step(80, "category"), at(120, "session.ended")]

    found = fragments(journal, START + timedelta(seconds=120))

    assert spans(found) == [("category", 0, 40), ("address", 40, 80), ("category", 80, 120)]


def test_two_helpers_on_one_step_make_one_fragment():
    journal = [created(), joined(10, "sergey"), joined(20, "anna"), left(50, "sergey"), left(70, "anna")]

    [found] = fragments(journal, START + timedelta(seconds=100))

    assert spans([found]) == [("category", 10, 70)]
    assert found.helper_ids == {"sergey", "anna"}


def test_owner_alone_and_short_visits_are_not_fragments():
    alone = [created(), step(60, "address")]
    short = [created(), joined(10), step(13, "address"), left(40)]

    assert fragments(alone, START + timedelta(seconds=100)) == []
    assert spans(fragments(short, START + timedelta(seconds=100))) == [("address", 13, 40)]


def test_fragment_counts_what_happened_inside():
    journal = [
        created(),
        joined(0),
        at(5, "annotation.created", element_id="benefit_category"),
        at(8, "owner.confusion_flagged", element_id="benefit_category"),
        at(9, "annotation.created", element_id="benefit_reason"),
        step(30, "address"),
        at(35, "annotation.created", element_id="region"),
    ]

    first, second = fragments(journal, START + timedelta(seconds=60))

    assert (first.highlights, first.confusions) == (2, 1)
    assert (second.highlights, second.confusions) == (1, 0)


def test_helper_still_there_at_the_end_is_counted_to_the_end():
    journal = [created(), joined(10)]

    assert spans(fragments(journal, START + timedelta(seconds=40))) == [("category", 10, 40)]


async def meeting_with_help(client, monkeypatch):
    monkeypatch.setattr(past_help, "SHORTEST", timedelta(0))
    headers, application_id, body = await owner_with_assist(client)
    await joined_helper(client, headers, body["id"])
    await fill(client, headers, application_id, STEP_VALUES["category"])
    await go_next(client, headers, application_id)
    await client.post(f"/api/v1/assist-sessions/{body['id']}/end", headers=headers)
    return headers, application_id, body["id"]


async def past_help_of(client, headers, application_id):
    response = await client.get(f"/api/v1/service-sessions/{application_id}/past-help", headers=headers)
    assert response.status_code == 200
    return response.json()["steps"]


def of_meeting(steps, assist_id):
    return {
        step_id: [item for item in items if item["assist_session_id"] == assist_id]
        for step_id, items in steps.items()
        if any(item["assist_session_id"] == assist_id for item in items)
    }


async def test_owner_sees_past_help_on_the_steps(client, monkeypatch):
    headers, application_id, assist_id = await meeting_with_help(client, monkeypatch)

    steps = of_meeting(await past_help_of(client, headers, application_id), assist_id)

    assert set(steps) == {"category", "address"}
    [category] = steps["category"]
    assert category["helpers"] == [{"display_name": "Сергей К.", "role": "invited_helper"}]
    assert category["has_audio"] is False
    assert category["audio_url"] is None
    assert category["replay_to_ms"] >= category["replay_from_ms"]


async def test_past_help_brings_the_sound_of_the_step(client, monkeypatch):
    headers, application_id, assist_id = await meeting_with_help(client, monkeypatch)
    async with session_factory() as db:
        meeting = await db.get(AssistSession, UUID(assist_id))
        file_started = int(meeting.created_at.timestamp() * SECOND)
    await send(client, egress_event("egress_started", assist_id))
    await send(client, finished(assist_id, file_started=file_started))

    steps = of_meeting(await past_help_of(client, headers, application_id), assist_id)

    [category] = steps["category"]
    assert category["has_audio"] is True
    assert category["audio_url"] == f"/api/v1/consultations/{assist_id}/recording"
    assert 0 <= category["audio_start_ms"] <= category["audio_end_ms"] <= 5000
    assert category["audio_start_ms"] == category["replay_from_ms"]


async def test_past_help_survives_a_new_application(client, monkeypatch):
    headers, _, assist_id = await meeting_with_help(client, monkeypatch)
    new_application = await start_session(client, headers)

    steps = of_meeting(await past_help_of(client, headers, new_application), assist_id)

    assert set(steps) == {"category", "address"}


async def test_newest_meeting_comes_first(client, monkeypatch):
    headers, application_id, first = await meeting_with_help(client, monkeypatch)
    again = await client.post(
        "/api/v1/assist-sessions", json={"service_session_id": application_id}, headers=headers
    )
    second = again.json()["id"]
    await joined_helper(client, headers, second, "anna")
    await client.post(f"/api/v1/assist-sessions/{second}/end", headers=headers)

    order = [
        item["assist_session_id"] for item in (await past_help_of(client, headers, application_id))["address"]
    ]

    assert order.index(second) < order.index(first)


async def test_steps_that_no_longer_exist_are_skipped(client, monkeypatch):
    headers, application_id, assist_id = await meeting_with_help(client, monkeypatch)
    async with session_factory() as db:
        await db.execute(
            update(SessionEvent)
            .where(
                SessionEvent.assist_session_id == UUID(assist_id),
                SessionEvent.event_type == "navigation.step_changed",
            )
            .values(payload={"from_step_id": "category", "to_step_id": "removed_step"})
        )
        await db.commit()

    steps = await past_help_of(client, headers, application_id)

    assert set(of_meeting(steps, assist_id)) == {"category"}
    assert "removed_step" not in steps


async def test_only_own_meetings_are_shown(client, monkeypatch):
    headers, application_id, assist_id = await meeting_with_help(client, monkeypatch)
    stranger = await login(client, "anna")
    stranger_application = await start_session(client, stranger)

    foreign = await client.get(f"/api/v1/service-sessions/{application_id}/past-help", headers=stranger)
    own = await client.get(f"/api/v1/service-sessions/{stranger_application}/past-help", headers=stranger)

    shown = [item["assist_session_id"] for items in own.json()["steps"].values() for item in items]
    assert foreign.status_code == 403
    assert assist_id not in shown
