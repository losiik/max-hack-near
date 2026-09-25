import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.modules.assist.events import Delivery
from max_assist.modules.assist.models import SessionEvent
from max_assist.tasks import run_in_background
from max_assist.utils import now

logger = logging.getLogger("max_assist.assist")


def participant_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {"participant_id": payload["participant"]["id"], "role": payload["participant"]["role"]}


def fields_entry(payload: dict[str, Any]) -> dict[str, Any]:
    changed = list(payload["element_ids"])
    states = {
        element["id"]: element["view"]["state"]
        for element in payload["current_step"]["elements"]
        if element["id"] in changed and element.get("view")
    }
    return {"element_ids": changed, "states": states}


def errors_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "step_id": payload["step_id"],
        "errors": [{"element_id": item["element_id"], "code": item["code"]} for item in payload["errors"]],
    }


def annotation_entry(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "annotation_id": payload["id"],
        "kind": payload["kind"],
        "element_id": payload["element_id"],
        "label": payload["label"],
    }


# в журнал попадают только перечисленные здесь поля — значения полей формы сюда не проходят
ENTRIES: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "participant.join_requested": participant_entry,
    "participant.joined": participant_entry,
    "participant.left": lambda payload: {
        "participant_id": payload["participant_id"],
        "reason": payload["reason"],
    },
    "participant.status_changed": lambda payload: {
        "participant_id": payload["participant_id"],
        "status": payload["status"],
    },
    "invite.declined": lambda payload: {"invite_id": payload["invite_id"]},
    "session.activated": lambda payload: {},
    "session.ended": lambda payload: {"reason": payload["reason"]},
    "navigation.step_changed": lambda payload: {
        "from_step_id": payload["from_step_id"],
        "to_step_id": payload["current_step"]["id"],
    },
    "form.field_updated": fields_entry,
    "form.validation_failed": errors_entry,
    "form.submitted": lambda payload: {},
    "annotation.created": annotation_entry,
    "annotation.cleared": lambda payload: {"annotation_ids": list(payload["annotation_ids"])},
    "owner.confusion_flagged": lambda payload: {"element_id": payload["element_id"]},
}


def entries(assist_id: UUID, deliveries: list[Delivery]) -> list[SessionEvent]:
    seen: set[int] = set()
    rows = []
    for delivery in deliveries:
        message = delivery.message
        if message is None or message["event"] not in ENTRIES:
            continue
        if message["seq"] is not None:
            if message["seq"] in seen:
                continue
            seen.add(message["seq"])

        actor = message.get("actor") or {}
        rows.append(
            SessionEvent(
                assist_session_id=assist_id,
                seq=message["seq"],
                occurred_at=datetime.fromisoformat(message["sent_at"]),
                actor_participant_id=UUID(actor["participant_id"]) if actor.get("participant_id") else None,
                event_type=message["event"],
                payload=ENTRIES[message["event"]](message["payload"]),
            )
        )
    return rows


def record(db: AsyncSession, assist_id: UUID, deliveries: list[Delivery]) -> None:
    db.add_all(entries(assist_id, deliveries))


def note(db: AsyncSession, assist_id: UUID, event_type: str, payload: dict[str, Any]) -> None:
    db.add(
        SessionEvent(
            assist_session_id=assist_id,
            occurred_at=now(),
            event_type=event_type,
            payload=payload,
        )
    )


async def store(rows: list[SessionEvent]) -> None:
    try:
        async with session_factory() as db:
            db.add_all(rows)
            await db.commit()
    except Exception:
        logger.exception("journal write failed")


def record_later(assist_id: UUID, deliveries: list[Delivery]) -> None:
    rows = entries(assist_id, deliveries)
    if rows:
        run_in_background(store(rows))
