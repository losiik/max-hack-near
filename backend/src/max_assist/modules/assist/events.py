from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.assist import domain
from max_assist.modules.assist.annotations import Annotation, board
from max_assist.modules.assist.models import AssistParticipant, AssistSession
from max_assist.modules.assist.realtime import Viewer, hub
from max_assist.modules.assist.schemas import (
    application_of,
    application_snapshot,
    participant_out,
    snapshot_view,
    users_by_id,
)
from max_assist.modules.assist.visibility import ProjectedState, project
from max_assist.modules.catalog.schema import ServiceDefinition
from max_assist.modules.identity.models import User
from max_assist.tasks import run_in_background
from max_assist.utils import now

CLOSE_NORMAL = 1000
CLOSE_UNAUTHORIZED = 4001
CLOSE_FORBIDDEN = 4003
CLOSE_NOT_FOUND = 4004
CLOSE_ENDED = 4009


@dataclass
class Delivery:
    recipients: list[UUID]
    message: dict[str, Any] | None = None
    close_code: int | None = None


def next_seq(assist: AssistSession) -> int:
    assist.last_seq += 1
    return assist.last_seq


def actor_of(participant: AssistParticipant) -> dict[str, Any]:
    return {
        "participant_id": str(participant.id),
        "role": participant.role,
        "display_name": participant.display_name,
    }


def actor_of_viewer(viewer: Viewer) -> dict[str, Any]:
    return {
        "participant_id": str(viewer.participant_id),
        "role": viewer.role,
        "display_name": viewer.display_name,
    }


def envelope(
    assist_id: UUID,
    event: str,
    payload: dict[str, Any],
    seq: int | None = None,
    actor: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event": event,
        "session_id": str(assist_id),
        "seq": seq,
        "sent_at": now().isoformat(),
        "actor": actor,
        "payload": payload,
    }


def active_ids(assist: AssistSession, exclude: UUID | None = None) -> list[UUID]:
    return [item.id for item in assist.participants if item.status == "active" and item.id != exclude]


def live_ids(assist: AssistSession) -> list[UUID]:
    return [item.id for item in assist.participants if item.status in domain.LIVE_STATUSES]


listeners: list[Callable[[UUID, list[Delivery]], None]] = []


async def publish(assist_id: UUID, deliveries: list[Delivery]) -> None:
    for listener in listeners:
        listener(assist_id, deliveries)
    for delivery in deliveries:
        if delivery.message is not None:
            await hub.send(assist_id, delivery.recipients, delivery.message)
        if delivery.close_code is not None:
            await hub.close(assist_id, delivery.recipients, delivery.close_code)


async def participant_payload(
    db: AsyncSession,
    assist: AssistSession,
    participant: AssistParticipant,
) -> dict[str, Any]:
    users = await users_by_id(db, {participant.user_id})
    view = participant_out(participant, users, hub.online(assist.id))
    return {"participant": view.model_dump(mode="json")}


def status_changed(assist: AssistSession, participant: AssistParticipant) -> dict[str, Any]:
    return envelope(
        assist.id,
        "participant.status_changed",
        {"participant_id": str(participant.id), "status": participant.status},
        next_seq(assist),
    )


async def snapshot(db: AsyncSession, assist: AssistSession, viewer_id: UUID) -> dict[str, Any]:
    view = await snapshot_view(db, assist, viewer_id)
    return envelope(assist.id, "session.snapshot", view.model_dump(mode="json"))


async def greeting(db: AsyncSession, assist: AssistSession, participant: AssistParticipant) -> dict[str, Any]:
    if participant.status == "active":
        return await snapshot(db, assist, participant.user_id)

    owner = await db.get(User, assist.owner_id)
    _, definition = await application_of(db, assist)
    return envelope(
        assist.id,
        "session.pending",
        {
            "participant_id": str(participant.id),
            "owner": {"display_name": owner.display_name},
            "service": {"title": definition.title},
        },
    )


async def join_requested(
    db: AsyncSession,
    assist: AssistSession,
    participant: AssistParticipant,
) -> list[Delivery]:
    owner = domain.participant_of(assist, assist.owner_id)
    message = envelope(
        assist.id,
        "participant.join_requested",
        await participant_payload(db, assist, participant),
        next_seq(assist),
        actor_of(participant),
    )
    return [Delivery([owner.id], message)]


def invite_declined(
    assist: AssistSession,
    invite_id: UUID,
    helper: User,
    callback_id: UUID,
) -> list[Delivery]:
    owner = domain.participant_of(assist, assist.owner_id)
    message = envelope(
        assist.id,
        "invite.declined",
        {
            "invite_id": str(invite_id),
            "helper": {"display_name": helper.display_name},
            "help_callback_id": str(callback_id),
        },
        next_seq(assist),
    )
    return [Delivery([owner.id], message)]


async def joined(
    db: AsyncSession,
    assist: AssistSession,
    participant: AssistParticipant,
    was_waiting: bool,
) -> list[Delivery]:
    others = active_ids(assist, exclude=participant.id)
    deliveries = [
        Delivery(
            others,
            envelope(
                assist.id,
                "participant.joined",
                await participant_payload(db, assist, participant),
                next_seq(assist),
                actor_of(participant),
            ),
        )
    ]

    if was_waiting and assist.status == "active":
        deliveries.append(
            Delivery(
                others,
                envelope(
                    assist.id,
                    "session.activated",
                    {"started_at": assist.started_at.isoformat()},
                    next_seq(assist),
                ),
            )
        )

    deliveries.append(Delivery([participant.id], status_changed(assist, participant)))
    deliveries.append(Delivery([participant.id], await snapshot(db, assist, participant.user_id)))
    return deliveries


def rejected(assist: AssistSession, participant: AssistParticipant) -> list[Delivery]:
    return [Delivery([participant.id], status_changed(assist, participant), CLOSE_FORBIDDEN)]


def removed(assist: AssistSession, participant: AssistParticipant) -> list[Delivery]:
    return [
        Delivery(
            active_ids(assist),
            envelope(
                assist.id,
                "participant.left",
                {"participant_id": str(participant.id), "reason": "removed"},
                next_seq(assist),
            ),
        ),
        Delivery([participant.id], status_changed(assist, participant), CLOSE_FORBIDDEN),
    ]


def left(assist: AssistSession, participant: AssistParticipant) -> list[Delivery]:
    return [
        Delivery(
            active_ids(assist),
            envelope(
                assist.id,
                "participant.left",
                {"participant_id": str(participant.id), "reason": "left"},
                next_seq(assist),
                actor_of(participant),
            ),
        ),
        Delivery([participant.id], close_code=CLOSE_NORMAL),
    ]


def ended(assist: AssistSession, recipients: list[UUID]) -> list[Delivery]:
    board.clear_step(assist.id)
    message = envelope(
        assist.id,
        "session.ended",
        {
            "reason": assist.end_reason,
            "summary_url": f"/api/v1/assist-sessions/{assist.id}/summary",
        },
        next_seq(assist),
    )
    return [Delivery(recipients, message, CLOSE_ENDED)]


def presence(assist: AssistSession, participant: AssistParticipant, online: bool) -> list[Delivery]:
    message = envelope(
        assist.id,
        "presence.changed",
        {"participant_id": str(participant.id), "online": online},
    )
    return [Delivery(active_ids(assist, exclude=participant.id), message)]


async def announce_presence(assist_id: UUID, participant_id: UUID) -> None:
    async with session_factory() as db:
        assist = await db.get(AssistSession, assist_id)
    if assist is None or assist.status == "ended":
        return

    participant = next((item for item in assist.participants if item.id == participant_id), None)
    if participant is None or participant.status != "active":
        return
    online = participant_id in hub.online(assist_id)
    await publish(assist_id, presence(assist, participant, online))


def announce_presence_later(assist_id: UUID, participant_id: UUID) -> None:
    # задачу сокета могут отменить, а статус берём на момент отправки
    run_in_background(announce_presence(assist_id, participant_id))


def for_each_participant(
    assist: AssistSession,
    row: ServiceSession,
    definition: ServiceDefinition,
    event: str,
    payload: Callable[[AssistParticipant, ProjectedState], dict[str, Any]],
) -> list[Delivery]:
    seq = next_seq(assist)
    snapshot = application_snapshot(row)
    deliveries = []
    for participant in assist.participants:
        if participant.status != "active":
            continue
        state = project(definition, snapshot, participant.role)
        message = envelope(assist.id, event, payload(participant, state), seq)
        deliveries.append(Delivery([participant.id], message))
    return deliveries


def fields_updated(
    assist: AssistSession,
    row: ServiceSession,
    definition: ServiceDefinition,
    element_ids: list[str],
) -> list[Delivery]:
    def payload(_: AssistParticipant, state: ProjectedState) -> dict[str, Any]:
        return {
            "element_ids": element_ids,
            "current_step": state.current_step.model_dump(mode="json"),
            "errors": [error.model_dump(mode="json") for error in state.errors],
        }

    return for_each_participant(assist, row, definition, "form.field_updated", payload)


def step_changed(
    assist: AssistSession,
    row: ServiceSession,
    definition: ServiceDefinition,
    from_step_id: str,
) -> list[Delivery]:
    board.clear_step(assist.id)

    def payload(_: AssistParticipant, state: ProjectedState) -> dict[str, Any]:
        return {
            "from_step_id": from_step_id,
            "steps": [step.model_dump(mode="json") for step in state.steps],
            "current_step": state.current_step.model_dump(mode="json"),
            "errors": [error.model_dump(mode="json") for error in state.errors],
        }

    return for_each_participant(assist, row, definition, "navigation.step_changed", payload)


def validation_failed(
    assist: AssistSession,
    row: ServiceSession,
    definition: ServiceDefinition,
    step_id: str,
) -> list[Delivery]:
    failing = replace(
        application_snapshot(row),
        current_step_id=step_id,
        errors=row.last_errors.get(step_id, []),
    )

    def payload(participant: AssistParticipant, _: ProjectedState) -> dict[str, Any]:
        errors = project(definition, failing, participant.role).errors
        return {"step_id": step_id, "errors": [error.model_dump(mode="json") for error in errors]}

    return for_each_participant(assist, row, definition, "form.validation_failed", payload)


def submitted(assist: AssistSession, row: ServiceSession, definition: ServiceDefinition) -> list[Delivery]:
    def payload(participant: AssistParticipant, _: ProjectedState) -> dict[str, Any]:
        number = row.application_number if participant.role == "owner" else None
        return {"application_number": number}

    return for_each_participant(assist, row, definition, "form.submitted", payload)


def annotation_payload(annotation: Annotation, author: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(annotation.id),
        "kind": annotation.kind,
        "element_id": annotation.element_id,
        "label": annotation.label,
        "author": author,
        "expires_at": None if annotation.expires_at is None else annotation.expires_at.isoformat(),
    }


def annotation_created(assist_id: UUID, viewer: Viewer, annotation: Annotation) -> list[Delivery]:
    author = actor_of_viewer(viewer)
    message = envelope(
        assist_id,
        "annotation.created",
        annotation_payload(annotation, author),
        actor=author,
    )
    return [Delivery(hub.active_participants(assist_id, exclude=viewer.participant_id), message)]


def annotation_cleared(assist_id: UUID, viewer: Viewer, removed_ids: list[UUID]) -> list[Delivery]:
    author = actor_of_viewer(viewer)
    message = envelope(
        assist_id,
        "annotation.cleared",
        {
            "annotation_ids": [str(item) for item in removed_ids],
            "author_participant_id": str(viewer.participant_id),
        },
        actor=author,
    )
    return [Delivery(hub.active_participants(assist_id, exclude=viewer.participant_id), message)]


def pointer(
    assist_id: UUID,
    viewer: Viewer,
    element_id: str | None,
    rel_x: float,
    rel_y: float,
    visible: bool,
) -> list[Delivery]:
    message = envelope(
        assist_id,
        "annotation.pointer",
        {"element_id": element_id, "rel_x": rel_x, "rel_y": rel_y, "visible": visible},
        actor=actor_of_viewer(viewer),
    )
    return [Delivery(hub.active_participants(assist_id, exclude=viewer.participant_id), message)]


def confusion_flagged(assist_id: UUID, viewer: Viewer, element_id: str) -> list[Delivery]:
    message = envelope(
        assist_id,
        "owner.confusion_flagged",
        {"element_id": element_id},
        actor=actor_of_viewer(viewer),
    )
    return [Delivery(hub.active_participants(assist_id, exclude=viewer.participant_id), message)]


def error(assist_id: UUID, request_id: Any, code: str, message: str) -> dict[str, Any]:
    return envelope(assist_id, "error", {"request_id": request_id, "code": code, "message": message})


def ack(assist_id: UUID, request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return envelope(assist_id, "ack", {"request_id": request_id, "result": result})
