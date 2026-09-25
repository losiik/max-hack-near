from datetime import datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.modules.applications import service as applications_service
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.assist import domain
from max_assist.modules.assist.annotations import Annotation, board
from max_assist.modules.assist.models import (
    AssistInvite,
    AssistParticipant,
    AssistSession,
    HelpCallback,
    SessionEvent,
)
from max_assist.modules.assist.realtime import hub
from max_assist.modules.assist.visibility import ApplicationSnapshot, ProjectedState, project
from max_assist.modules.catalog import service as catalog_service
from max_assist.modules.catalog.schema import Option, ServiceDefinition
from max_assist.modules.identity.models import User
from max_assist.modules.voice.models import Recording
from max_assist.utils import now


class CreateAssistRequest(BaseModel):
    service_session_id: UUID


class InviteRequest(BaseModel):
    kind: Literal["link"] = "link"


class ServiceRefOut(BaseModel):
    code: str
    title: str


class PersonOut(BaseModel):
    id: UUID
    display_name: str
    photo_url: str | None


class StepOut(BaseModel):
    id: str
    index: int
    title: str


class BadgeOut(BaseModel):
    label: str
    verified: bool


class ParticipantOut(BaseModel):
    id: UUID
    role: str
    status: str
    display_name: str
    photo_url: str | None
    badge: BadgeOut | None
    online: bool


class MeOut(BaseModel):
    participant_id: UUID
    role: str
    status: str
    capabilities: list[str]


class InviteRefOut(BaseModel):
    id: UUID
    kind: str
    expires_at: datetime


class RecordingStateOut(BaseModel):
    status: str
    duration_ms: int | None


class AssistSessionOut(BaseModel):
    id: UUID
    status: str
    service: ServiceRefOut
    service_session_id: UUID | None
    owner: PersonOut
    current_step: StepOut | None
    total_steps: int
    me: MeOut
    participants: list[ParticipantOut]
    pending_invites: list[InviteRefOut] | None
    recording: RecordingStateOut | None
    ws_url: str
    created_at: datetime
    started_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None


class AnnotationAuthorOut(BaseModel):
    participant_id: UUID
    role: str
    display_name: str


class AnnotationOut(BaseModel):
    id: UUID
    kind: str
    element_id: str
    label: str | None
    author: AnnotationAuthorOut
    expires_at: datetime | None


class SnapshotOut(ProjectedState):
    last_seq: int
    session: AssistSessionOut
    annotations: list[AnnotationOut]


class InviteOut(BaseModel):
    id: UUID
    kind: str
    token: str
    deep_link: str
    share_text: str
    expires_at: datetime
    delivery: Literal["share_required"]


class OwnerOut(BaseModel):
    display_name: str
    photo_url: str | None


class ServiceTitleOut(BaseModel):
    title: str


class InviteStepOut(BaseModel):
    index: int
    total: int
    title: str


class InvitePreviewOut(BaseModel):
    status: Literal["valid", "expired", "used", "declined", "revoked", "session_ended"]
    assist_session_id: UUID
    owner: OwnerOut
    service: ServiceTitleOut
    current_step: InviteStepOut
    is_owner: bool
    you_are_trusted: bool
    requires_owner_approval: bool
    expires_at: datetime


class AcceptOut(BaseModel):
    assist_session_id: UUID
    participant_id: UUID
    status: str


class NameOut(BaseModel):
    display_name: str


class DeclineOut(BaseModel):
    help_callback_id: UUID
    owner: NameOut


class HelpCallbackOut(BaseModel):
    id: UUID
    status: str
    owner: NameOut
    helper: NameOut
    service_session_id: UUID
    service: ServiceTitleOut
    created_at: datetime
    ready_at: datetime | None
    expires_at: datetime


class CallBackOut(BaseModel):
    assist_session: AssistSessionOut
    invite: InviteOut


class ShortStepOut(BaseModel):
    index: int
    title: str


class ActiveAssistOut(BaseModel):
    id: UUID
    status: str
    my_role: str
    my_status: str
    service_title: str
    owner_display_name: str
    current_step: ShortStepOut
    total_steps: int


class HelperOut(BaseModel):
    display_name: str
    role: str
    badge: BadgeOut | None


class SummaryActionsOut(BaseModel):
    can_continue: bool


class SummaryOut(BaseModel):
    assist_session_id: UUID
    service: ServiceTitleOut
    status: str
    end_reason: str | None
    started_at: datetime | None
    ended_at: datetime | None
    duration_sec: int
    helpers: list[HelperOut]
    steps_completed: int | None
    total_steps: int
    stopped_at_step: StepOut | None
    service_session_status: str
    recording: RecordingStateOut | None
    actions: SummaryActionsOut


class StatsOut(BaseModel):
    highlights: int
    confusions: int


class ChapterOut(BaseModel):
    step_id: str
    title: str
    start_offset_ms: int
    duration_ms: int
    highlights: int
    confusions: int
    had_errors: bool


class ConsultationItemOut(SummaryOut):
    my_role: str
    owner_display_name: str
    stats: StatsOut


class ConsultationOut(ConsultationItemOut):
    chapters: list[ChapterOut]


class ReplayElementOut(BaseModel):
    id: str
    type: str
    label: str | None
    options: list[Option] | None


class ReplayStepOut(BaseModel):
    id: str
    index: int
    title: str
    elements: list[ReplayElementOut]


class ReplayParticipantOut(BaseModel):
    id: UUID
    role: str
    display_name: str


class ReplayEventOut(BaseModel):
    seq: int | None
    offset_ms: int
    type: str
    actor_participant_id: UUID | None
    payload: dict[str, Any]


class ReplayRecordingOut(BaseModel):
    status: str
    url: str | None
    offset_ms: int | None
    duration_ms: int | None


class ReplayOut(BaseModel):
    assist_session_id: UUID
    service: ServiceRefOut
    service_version: int
    started_at: datetime
    duration_ms: int
    steps: list[ReplayStepOut]
    participants: list[ReplayParticipantOut]
    recording: ReplayRecordingOut | None
    events: list[ReplayEventOut]


def deep_link(token: str) -> str:
    return f"https://max.ru/{settings.max_bot_username}?startapp=as_{token}"


def ws_url(assist_id: UUID) -> str:
    return f"/ws/assist/{assist_id}"


def badge_of(participant: AssistParticipant) -> BadgeOut | None:
    if participant.badge_label is None:
        return None
    return BadgeOut(label=participant.badge_label, verified=participant.badge_verified)


def participant_out(
    participant: AssistParticipant,
    users: dict[UUID, User],
    online: set[UUID],
) -> ParticipantOut:
    user = users.get(participant.user_id)
    return ParticipantOut(
        id=participant.id,
        role=participant.role,
        status=participant.status,
        display_name=participant.display_name,
        photo_url=user.photo_url if user else None,
        badge=badge_of(participant),
        online=participant.id in online,
    )


def current_step_of(service_session: ServiceSession | None, definition: ServiceDefinition) -> StepOut | None:
    if service_session is None:
        return None
    step = definition.step(service_session.current_step_id)
    return StepOut(id=step.id, index=definition.step_index(step.id), title=step.title)


async def application_of(
    db: AsyncSession,
    assist: AssistSession,
) -> tuple[ServiceSession | None, ServiceDefinition]:
    # встреча хранится и после того, как старое заявление удалено
    definition = await catalog_service.load_definition(db, assist.service_code, assist.service_version)
    if assist.service_session_id is None:
        return None, definition
    return await applications_service.get_by_id(db, assist.service_session_id), definition


async def recording_of(db: AsyncSession, assist_id: UUID) -> Recording | None:
    return await db.scalar(select(Recording).where(Recording.assist_session_id == assist_id))


def recording_state(recording: Recording | None) -> RecordingStateOut | None:
    if recording is None:
        return None
    return RecordingStateOut(status=recording.status, duration_ms=recording.duration_ms)


async def users_by_id(db: AsyncSession, ids: set[UUID | None]) -> dict[UUID, User]:
    rows = await db.scalars(select(User).where(User.id.in_([item for item in ids if item])))
    return {row.id: row for row in rows}


async def session_view(db: AsyncSession, assist: AssistSession, viewer_id: UUID) -> AssistSessionOut:
    service_session, definition = await application_of(db, assist)
    live = [item for item in assist.participants if item.status in domain.LIVE_STATUSES]
    users = await users_by_id(db, {assist.owner_id, *(item.user_id for item in live)})
    owner = users[assist.owner_id]
    me = domain.participant_of(assist, viewer_id)
    online = hub.online(assist.id)

    return AssistSessionOut(
        id=assist.id,
        status=assist.status,
        service=ServiceRefOut(code=definition.code, title=definition.title),
        service_session_id=assist.service_session_id,
        owner=PersonOut(id=owner.id, display_name=owner.display_name, photo_url=owner.photo_url),
        current_step=current_step_of(service_session, definition),
        total_steps=definition.total_steps,
        me=MeOut(
            participant_id=me.id,
            role=me.role,
            status=me.status,
            capabilities=sorted(domain.capabilities_of(me.role)),
        ),
        participants=[participant_out(item, users, online) for item in live],
        pending_invites=[
            InviteRefOut(id=invite.id, kind=invite.kind, expires_at=invite.expires_at)
            for invite in domain.open_invites(assist)
        ]
        if viewer_id == assist.owner_id
        else None,
        recording=recording_state(await recording_of(db, assist.id)),
        ws_url=ws_url(assist.id),
        created_at=assist.created_at,
        started_at=assist.started_at,
        ended_at=assist.ended_at,
        end_reason=assist.end_reason,
    )


async def invite_view(
    db: AsyncSession,
    assist: AssistSession,
    invite: AssistInvite,
    token: str,
    user: User,
) -> InviteOut:
    _, definition = await application_of(db, assist)
    return InviteOut(
        id=invite.id,
        kind=invite.kind,
        token=token,
        deep_link=deep_link(token),
        share_text=f"{user.display_name} просит помочь с услугой «{definition.title}». Подключиться:",
        expires_at=invite.expires_at,
        delivery="share_required",
    )


async def preview_view(
    db: AsyncSession,
    assist: AssistSession,
    invite: AssistInvite,
    viewer_id: UUID,
) -> InvitePreviewOut:
    service_session, definition = await application_of(db, assist)
    owner = await db.get(User, assist.owner_id)
    step = current_step_of(service_session, definition)

    return InvitePreviewOut(
        status=domain.invite_status(assist, invite),
        assist_session_id=assist.id,
        owner=OwnerOut(display_name=owner.display_name, photo_url=owner.photo_url),
        service=ServiceTitleOut(title=definition.title),
        current_step=InviteStepOut(index=step.index, total=definition.total_steps, title=step.title),
        is_owner=viewer_id == assist.owner_id,
        you_are_trusted=False,
        requires_owner_approval=True,
        expires_at=invite.expires_at,
    )


async def active_view(db: AsyncSession, assist: AssistSession, viewer_id: UUID) -> ActiveAssistOut:
    service_session, definition = await application_of(db, assist)
    owner = await db.get(User, assist.owner_id)
    me = domain.participant_of(assist, viewer_id)
    step = current_step_of(service_session, definition)

    return ActiveAssistOut(
        id=assist.id,
        status=assist.status,
        my_role=me.role,
        my_status=me.status,
        service_title=definition.title,
        owner_display_name=owner.display_name,
        current_step=ShortStepOut(index=step.index, title=step.title),
        total_steps=definition.total_steps,
    )


async def summary_view(db: AsyncSession, assist: AssistSession) -> SummaryOut:
    service_session, definition = await application_of(db, assist)
    can_continue = service_session is not None and service_session.status == "draft"

    duration = 0
    if assist.started_at is not None:
        duration = int(((assist.ended_at or now()) - assist.started_at).total_seconds())

    return SummaryOut(
        assist_session_id=assist.id,
        service=ServiceTitleOut(title=definition.title),
        status=assist.status,
        end_reason=assist.end_reason,
        started_at=assist.started_at,
        ended_at=assist.ended_at,
        duration_sec=duration,
        helpers=[
            HelperOut(display_name=item.display_name, role=item.role, badge=badge_of(item))
            for item in assist.participants
            if item.role != "owner" and item.joined_at is not None
        ],
        steps_completed=len(service_session.completed_step_ids) if service_session else None,
        total_steps=definition.total_steps,
        stopped_at_step=current_step_of(service_session, definition),
        service_session_status=service_session.status if service_session else "deleted",
        recording=recording_state(await recording_of(db, assist.id)),
        actions=SummaryActionsOut(can_continue=can_continue),
    )


def milliseconds(delta: timedelta) -> int:
    return max(0, int(delta.total_seconds() * 1000))


def stats_of(journal: list[SessionEvent]) -> StatsOut:
    return StatsOut(
        highlights=sum(1 for event in journal if event.event_type == "annotation.created"),
        confusions=sum(1 for event in journal if event.event_type == "owner.confusion_flagged"),
    )


def chapters_of(
    journal: list[SessionEvent],
    definition: ServiceDefinition,
    started: datetime,
    finished: datetime,
) -> list[ChapterOut]:
    marks = []
    for event in journal:
        if event.event_type == "session.created":
            marks.append((event.payload["step_id"], event.occurred_at))
        elif event.event_type == "navigation.step_changed":
            marks.append((event.payload["to_step_id"], event.occurred_at))

    chapters = []
    for index, (step_id, begins) in enumerate(marks):
        ends = marks[index + 1][1] if index + 1 < len(marks) else finished
        inside = [event for event in journal if begins <= event.occurred_at < ends]
        chapters.append(
            ChapterOut(
                step_id=step_id,
                title=definition.step(step_id).title,
                start_offset_ms=milliseconds(begins - started),
                duration_ms=milliseconds(ends - begins),
                highlights=sum(1 for event in inside if event.event_type == "annotation.created"),
                confusions=sum(1 for event in inside if event.event_type == "owner.confusion_flagged"),
                had_errors=any(event.event_type == "form.validation_failed" for event in inside),
            )
        )
    return chapters


async def consultation_item(
    db: AsyncSession,
    assist: AssistSession,
    viewer_id: UUID,
    journal: list[SessionEvent],
) -> ConsultationItemOut:
    summary = await summary_view(db, assist)
    owner = await db.get(User, assist.owner_id)
    me = domain.participant_of(assist, viewer_id)
    return ConsultationItemOut(
        **dict(summary),
        my_role=me.role,
        owner_display_name=owner.display_name,
        stats=stats_of(journal),
    )


async def consultation_view(
    db: AsyncSession,
    assist: AssistSession,
    viewer_id: UUID,
    journal: list[SessionEvent],
) -> ConsultationOut:
    item = await consultation_item(db, assist, viewer_id, journal)
    _, definition = await application_of(db, assist)
    finished = assist.ended_at or now()
    return ConsultationOut(
        **dict(item),
        chapters=chapters_of(journal, definition, assist.created_at, finished),
    )


def replay_recording(
    assist: AssistSession, recording: Recording | None, viewer_id: UUID
) -> ReplayRecordingOut | None:
    if recording is None:
        return None
    audible = recording.status == "ready" and viewer_id == assist.owner_id
    return ReplayRecordingOut(
        status=recording.status,
        url=f"/api/v1/consultations/{assist.id}/recording" if audible else None,
        offset_ms=milliseconds(recording.started_at - assist.created_at) if recording.started_at else None,
        duration_ms=recording.duration_ms,
    )


async def replay_view(
    db: AsyncSession,
    assist: AssistSession,
    journal: list[SessionEvent],
    viewer_id: UUID,
) -> ReplayOut:
    _, definition = await application_of(db, assist)
    finished = assist.ended_at or now()
    return ReplayOut(
        assist_session_id=assist.id,
        service=ServiceRefOut(code=definition.code, title=definition.title),
        service_version=definition.version,
        started_at=assist.created_at,
        duration_ms=milliseconds(finished - assist.created_at),
        steps=[
            ReplayStepOut(
                id=step.id,
                index=index,
                title=step.title,
                elements=[
                    ReplayElementOut(id=item.id, type=item.type, label=item.label, options=item.options)
                    for item in step.elements
                ],
            )
            for index, step in enumerate(definition.steps, start=1)
        ],
        participants=[
            ReplayParticipantOut(id=item.id, role=item.role, display_name=item.display_name)
            for item in assist.participants
            if item.joined_at is not None
        ],
        recording=replay_recording(assist, await recording_of(db, assist.id), viewer_id),
        events=[
            ReplayEventOut(
                seq=event.seq,
                offset_ms=milliseconds(event.occurred_at - assist.created_at),
                type=event.event_type,
                actor_participant_id=event.actor_participant_id,
                payload=event.payload,
            )
            for event in journal
        ],
    )


def application_snapshot(service_session: ServiceSession) -> ApplicationSnapshot:
    return ApplicationSnapshot(
        values=applications_service.read_values(service_session),
        current_step_id=service_session.current_step_id,
        completed_step_ids=list(service_session.completed_step_ids),
        errors=service_session.last_errors.get(service_session.current_step_id, []),
        status=service_session.status,
    )


def annotation_out(annotation: Annotation, assist: AssistSession) -> AnnotationOut | None:
    author = next(
        (item for item in assist.participants if item.id == annotation.author_participant_id),
        None,
    )
    if author is None:
        return None

    return AnnotationOut(
        id=annotation.id,
        kind=annotation.kind,
        element_id=annotation.element_id,
        label=annotation.label,
        author=AnnotationAuthorOut(
            participant_id=author.id,
            role=author.role,
            display_name=author.display_name,
        ),
        expires_at=annotation.expires_at,
    )


async def snapshot_view(db: AsyncSession, assist: AssistSession, viewer_id: UUID) -> SnapshotOut:
    service_session, definition = await application_of(db, assist)
    me = domain.participant_of(assist, viewer_id)
    state = project(definition, application_snapshot(service_session), me.role)
    annotations = [annotation_out(item, assist) for item in board.active(assist.id)]

    return SnapshotOut(
        last_seq=assist.last_seq,
        session=await session_view(db, assist, viewer_id),
        annotations=[item for item in annotations if item is not None],
        **dict(state),
    )


async def callback_view(db: AsyncSession, callback: HelpCallback) -> HelpCallbackOut:
    users = await users_by_id(db, {callback.owner_id, callback.helper_id})
    service_session = await applications_service.get_by_id(db, callback.service_session_id)
    definition = await applications_service.definition_of(db, service_session)
    return HelpCallbackOut(
        id=callback.id,
        status=callback.status,
        owner=NameOut(display_name=users[callback.owner_id].display_name),
        helper=NameOut(display_name=users[callback.helper_id].display_name),
        service_session_id=callback.service_session_id,
        service=ServiceTitleOut(title=definition.title),
        created_at=callback.created_at,
        ready_at=callback.ready_at,
        expires_at=callback.expires_at,
    )
