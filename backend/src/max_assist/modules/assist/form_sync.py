from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.modules.applications import service as applications_service
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.assist import domain, events, journal
from max_assist.modules.assist.models import AssistSession


async def active_assist_id(db: AsyncSession, service_session_id: UUID) -> UUID | None:
    return await db.scalar(
        select(AssistSession.id).where(
            AssistSession.service_session_id == service_session_id,
            AssistSession.status != "ended",
        )
    )


async def on_application_changed(event: str, row: ServiceSession, details: dict[str, Any]) -> None:
    async with session_factory() as db:
        assist = await db.scalar(
            select(AssistSession)
            .where(
                AssistSession.service_session_id == row.id,
                AssistSession.status != "ended",
            )
            .with_for_update()
        )
        if assist is None:
            return

        definition = await applications_service.definition_of(db, row)
        if event == "fields_updated":
            deliveries = events.fields_updated(assist, row, definition, details["element_ids"])
        elif event == "step_changed":
            deliveries = events.step_changed(assist, row, definition, details["from_step_id"])
        elif event == "validation_failed":
            deliveries = events.validation_failed(assist, row, definition, details["step_id"])
        elif event == "submitted":
            recipients = events.live_ids(assist)
            deliveries = events.submitted(assist, row, definition)
            domain.end(assist, "service_submitted")
            deliveries += events.ended(assist, recipients)
        else:
            recipients = events.live_ids(assist)
            domain.end(assist, "cancelled")
            deliveries = events.ended(assist, recipients)

        domain.touch(assist)
        journal.record(db, assist.id, deliveries)
        await db.commit()

    await events.publish(assist.id, deliveries)
