from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.modules.applications import service as applications_service
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.assist import domain
from max_assist.modules.assist.annotations import Annotation, board
from max_assist.modules.assist.models import AssistInvite, AssistParticipant, AssistSession
from max_assist.modules.assist.realtime import hub
from max_assist.modules.assist.visibility import ApplicationSnapshot, ProjectedState, project
from max_assist.modules.catalog.schema import ServiceDefinition
from max_assist.modules.identity.models import User
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


class AssistSessionOut(BaseModel):
    id: UUID
    status: str
    service: ServiceRefOut
    service_session_id: UUID
    owner: PersonOut
    current_step: StepOut
    total_steps: int
    me: MeOut
    participants: list[ParticipantOut]
    pending_invites: list[InviteRefOut] | None
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
    status: Literal["valid", "expired", "used", "revoked", "session_ended"]
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
    steps_completed: int
    total_steps: int
    stopped_at_step: StepOut
    service_session_status: str
    actions: SummaryActionsOut


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


def current_step_of(service_session: ServiceSession, definition: ServiceDefinition) -> StepOut:
    step = definition.step(service_session.current_step_id)
    return StepOut(id=step.id, index=definition.step_index(step.id), title=step.title)


async def application_of(
    db: AsyncSession,
    assist: AssistSession,
) -> tuple[ServiceSession, ServiceDefinition]:
    service_session = await applications_service.get_by_id(db, assist.service_session_id)
    definition = await applications_service.definition_of(db, service_session)
    return service_session, definition


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
        steps_completed=len(service_session.completed_step_ids),
        total_steps=definition.total_steps,
        stopped_at_step=current_step_of(service_session, definition),
        service_session_status=service_session.status,
        actions=SummaryActionsOut(can_continue=service_session.status == "draft"),
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
