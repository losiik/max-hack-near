import json
from datetime import timedelta
from typing import Any
from uuid import UUID

from max_assist.db import session_factory
from max_assist.modules.applications import service as applications_service
from max_assist.modules.applications.domain import ApplicationForm
from max_assist.modules.assist import domain, events, journal
from max_assist.modules.assist.annotations import KINDS, LABEL_LIMIT, board
from max_assist.modules.assist.limits import RateLimiter
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.assist.realtime import Connection

DENIED = {
    "annotate": "Показывать элементы может только помощник",
    "flag_confusion": "Отмечать непонятное может только владелец",
}

annotation_limit = RateLimiter(per_second=3, burst=5)
pointer_limit = RateLimiter(per_second=20, burst=20)
confusion_limit = RateLimiter(per_second=0.2, burst=1)


def prune_limits() -> None:
    for limiter in (annotation_limit, pointer_limit, confusion_limit):
        limiter.prune(timedelta(minutes=10))


async def elements_of_current_step(assist_id: UUID) -> set[str]:
    known = board.known_elements(assist_id)
    if known is not None:
        return known

    async with session_factory() as db:
        assist = await db.get(AssistSession, assist_id)
        if assist is None:
            return set()

        row = await applications_service.get_by_id(db, assist.service_session_id)
        definition = await applications_service.definition_of(db, row)
        form = ApplicationForm(definition, applications_service.read_values(row))
        step = definition.step(row.current_step_id)
        element_ids = {element.id for element in step.elements if form.is_visible(element)}

    board.remember_elements(assist_id, element_ids)
    return element_ids


def refusal(
    assist_id: UUID,
    connection: Connection,
    request_id: Any,
    capability: str,
) -> dict[str, Any] | None:
    viewer = connection.viewer
    if viewer.status != "active":
        return events.error(assist_id, request_id, "forbidden", "Дождитесь подтверждения владельца")
    if capability not in domain.capabilities_of(viewer.role):
        return events.error(assist_id, request_id, "forbidden", DENIED[capability])
    return None


async def annotate(
    assist_id: UUID,
    connection: Connection,
    request_id: Any,
    kind: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    denied = refusal(assist_id, connection, request_id, "annotate")
    if denied is not None:
        return denied
    if not annotation_limit.allow((connection.viewer.participant_id, "annotation")):
        return events.error(assist_id, request_id, "rate_limited", "Слишком часто")

    element_id = payload.get("element_id")
    if element_id not in await elements_of_current_step(assist_id):
        return events.error(assist_id, request_id, "unknown_element", "Этого поля нет на текущем шаге")

    label = (payload.get("label") or "").strip() or None
    if label is not None and len(label) > LABEL_LIMIT:
        return events.error(assist_id, request_id, "bad_payload", f"Подпись длиннее {LABEL_LIMIT} символов")

    annotation = board.add(assist_id, connection.viewer.participant_id, kind, element_id, label)
    deliveries = events.annotation_created(assist_id, connection.viewer, annotation)
    await events.publish(assist_id, deliveries)
    journal.record_later(assist_id, deliveries)
    return events.ack(assist_id, request_id, {"annotation_id": str(annotation.id)})


async def clear(
    assist_id: UUID,
    connection: Connection,
    request_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    denied = refusal(assist_id, connection, request_id, "annotate")
    if denied is not None:
        return denied
    if not annotation_limit.allow((connection.viewer.participant_id, "annotation")):
        return events.error(assist_id, request_id, "rate_limited", "Слишком часто")

    raw_id = payload.get("annotation_id")
    try:
        annotation_id = None if raw_id is None else UUID(str(raw_id))
    except ValueError:
        return events.error(assist_id, request_id, "bad_payload", "Неверный annotation_id")

    removed = board.clear(assist_id, connection.viewer.participant_id, annotation_id)
    removed_ids = [item.id for item in removed]
    if removed_ids:
        deliveries = events.annotation_cleared(assist_id, connection.viewer, removed_ids)
        await events.publish(assist_id, deliveries)
        journal.record_later(assist_id, deliveries)
    return events.ack(assist_id, request_id, {"annotation_ids": [str(item) for item in removed_ids]})


async def pointer(
    assist_id: UUID,
    connection: Connection,
    request_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    denied = refusal(assist_id, connection, request_id, "annotate")
    if denied is not None:
        return denied
    if not pointer_limit.allow((connection.viewer.participant_id, "pointer")):
        return None

    visible = bool(payload.get("visible", True))
    element_id = payload.get("element_id")
    try:
        rel_x = min(1.0, max(0.0, float(payload.get("rel_x", 0))))
        rel_y = min(1.0, max(0.0, float(payload.get("rel_y", 0))))
    except (TypeError, ValueError):
        return events.error(assist_id, request_id, "bad_payload", "Координаты должны быть числами")

    if visible and element_id not in await elements_of_current_step(assist_id):
        return events.error(assist_id, request_id, "unknown_element", "Этого поля нет на текущем шаге")

    await events.publish(
        assist_id,
        events.pointer(assist_id, connection.viewer, element_id, rel_x, rel_y, visible),
    )
    return None


async def flag_confusion(
    assist_id: UUID,
    connection: Connection,
    request_id: Any,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    denied = refusal(assist_id, connection, request_id, "flag_confusion")
    if denied is not None:
        return denied
    if not confusion_limit.allow((connection.viewer.participant_id, "confusion")):
        return events.error(assist_id, request_id, "rate_limited", "Слишком часто")

    element_id = payload.get("element_id")
    if element_id not in await elements_of_current_step(assist_id):
        return events.error(assist_id, request_id, "unknown_element", "Этого поля нет на текущем шаге")

    deliveries = events.confusion_flagged(assist_id, connection.viewer, element_id)
    await events.publish(assist_id, deliveries)
    journal.record_later(assist_id, deliveries)
    return events.ack(assist_id, request_id, {})


async def handle(assist_id: UUID, connection: Connection, raw: str) -> dict[str, Any] | None:
    try:
        command = json.loads(raw)
    except ValueError:
        command = None

    if not isinstance(command, dict):
        return events.error(assist_id, None, "bad_message", "Сообщение должно быть JSON-объектом")

    name = command.get("command")
    request_id = command.get("request_id")
    payload = command.get("payload") or {}
    if not isinstance(payload, dict):
        return events.error(assist_id, request_id, "bad_payload", "Поле payload должно быть объектом")

    if name == "presence.ping":
        return None
    if name == "annotation.clear":
        return await clear(assist_id, connection, request_id, payload)
    if name == "annotation.pointer":
        return await pointer(assist_id, connection, request_id, payload)
    if name == "owner.flag_confusion":
        return await flag_confusion(assist_id, connection, request_id, payload)

    kind = name.removeprefix("annotation.") if isinstance(name, str) else ""
    if kind in KINDS:
        return await annotate(assist_id, connection, request_id, kind, payload)
    return events.error(assist_id, request_id, "unknown_command", "Команда не поддерживается")
