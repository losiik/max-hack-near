from dataclasses import dataclass, field
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist import service as assist_service
from max_assist.modules.assist.models import AssistSession, SessionEvent
from max_assist.modules.identity.models import User
from max_assist.modules.voice import recordings
from max_assist.modules.voice.models import Recording

SHORTEST = timedelta(seconds=5)
MEETINGS_LIMIT = 20


@dataclass
class Fragment:
    step_id: str
    begins: datetime
    ends: datetime
    helper_ids: set[str] = field(default_factory=set)
    highlights: int = 0
    confusions: int = 0


def chapters(journal: list[SessionEvent], finished: datetime) -> list[tuple[str, datetime, datetime]]:
    marks = []
    for event in journal:
        if event.event_type == "session.created":
            marks.append((event.payload["step_id"], event.occurred_at))
        elif event.event_type == "navigation.step_changed":
            marks.append((event.payload["to_step_id"], event.occurred_at))
    return [
        (step_id, begins, marks[index + 1][1] if index + 1 < len(marks) else finished)
        for index, (step_id, begins) in enumerate(marks)
    ]


def helper_presence(journal: list[SessionEvent]) -> list[tuple[datetime, datetime | None, str]]:
    joined: dict[str, datetime] = {}
    spans = []
    for event in journal:
        if event.event_type == "participant.joined" and event.payload["role"] != "owner":
            joined.setdefault(event.payload["participant_id"], event.occurred_at)
        elif event.event_type == "participant.left" and event.payload["participant_id"] in joined:
            helper = event.payload["participant_id"]
            spans.append((joined.pop(helper), event.occurred_at, helper))
        elif event.event_type == "session.ended":
            spans += [(since, event.occurred_at, helper) for helper, since in joined.items()]
            joined.clear()
    spans += [(since, None, helper) for helper, since in joined.items()]
    return sorted(spans, key=lambda span: span[0])


def fragments(journal: list[SessionEvent], finished: datetime) -> list[Fragment]:
    # шаг считается пройденным с помощником, пока подключён хотя бы один помощник
    presence = helper_presence(journal)
    found = []
    for step_id, step_begins, step_ends in chapters(journal, finished):
        for helper_begins, helper_ends, helper in presence:
            begins = max(step_begins, helper_begins)
            ends = min(step_ends, helper_ends or finished)
            if ends <= begins:
                continue
            current = found[-1] if found else None
            if current and current.step_id == step_id and begins <= current.ends:
                current.ends = max(current.ends, ends)
                current.helper_ids.add(helper)
            else:
                found.append(Fragment(step_id, begins, ends, {helper}))

    kept = [item for item in found if item.ends - item.begins >= SHORTEST]
    for item in kept:
        inside = [event for event in journal if item.begins <= event.occurred_at < item.ends]
        item.highlights = sum(1 for event in inside if event.event_type == "annotation.created")
        item.confusions = sum(1 for event in inside if event.event_type == "owner.confusion_flagged")
    return kept


def milliseconds(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() * 1000))


async def past_help(session: AsyncSession, user: User, service_session_id: UUID) -> dict[str, list[dict]]:
    application = await applications_service.get_owned(session, user, service_session_id)
    definition = await applications_service.definition_of(session, application)
    known_steps = {step.id for step in definition.steps}

    meetings = await session.scalars(
        select(AssistSession)
        .where(
            AssistSession.owner_id == user.id,
            AssistSession.service_code == application.service_code,
            AssistSession.status == "ended",
        )
        .order_by(AssistSession.ended_at.desc())
        .limit(MEETINGS_LIMIT)
    )

    steps: dict[str, list[dict]] = {}
    for meeting in meetings:
        journal = await assist_service.journal_of(session, meeting.id)
        recording = await recordings.find(session, meeting.id)
        names = {str(item.id): (item.display_name, item.role) for item in meeting.participants}
        for item in reversed(fragments(journal, meeting.ended_at)):
            if item.step_id in known_steps:
                steps.setdefault(item.step_id, []).append(fragment_view(meeting, item, recording, names))
    return steps


def fragment_view(
    meeting: AssistSession,
    item: Fragment,
    recording: Recording | None,
    names: dict[str, tuple[str, str]],
) -> dict:
    audible = recording is not None and recording.status == "ready" and recording.started_at is not None
    audio_start = audio_end = None
    if audible:
        length = timedelta(milliseconds=recording.duration_ms or 0)
        audio_start = milliseconds(item.begins - recording.started_at)
        audio_end = min(milliseconds(item.ends - recording.started_at), milliseconds(length))
        audible = audio_end > audio_start

    return {
        "assist_session_id": meeting.id,
        "date": item.begins,
        "helpers": [
            {"display_name": names[helper][0], "role": names[helper][1]}
            for helper in sorted(item.helper_ids)
            if helper in names
        ],
        "has_audio": audible,
        "audio_url": f"/api/v1/consultations/{meeting.id}/recording" if audible else None,
        "audio_start_ms": audio_start if audible else None,
        "audio_end_ms": audio_end if audible else None,
        "replay_from_ms": milliseconds(item.begins - meeting.created_at),
        "replay_to_ms": milliseconds(item.ends - meeting.created_at),
        "highlights": item.highlights,
        "confusions": item.confusions,
    }
