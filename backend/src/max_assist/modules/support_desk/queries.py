from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.modules.assist.models import AssistSession
from max_assist.modules.support_desk.models import OperatorRequest

OPEN = ("queued", "claimed")


async def open_request(session: AsyncSession, assist_id: UUID) -> OperatorRequest | None:
    return await session.scalar(
        select(OperatorRequest).where(
            OperatorRequest.assist_session_id == assist_id,
            OperatorRequest.status.in_(OPEN),
        )
    )


async def queue(session: AsyncSession) -> list[OperatorRequest]:
    query = (
        select(OperatorRequest)
        .join(AssistSession, AssistSession.id == OperatorRequest.assist_session_id)
        .where(OperatorRequest.status == "queued", AssistSession.status != "ended")
        .order_by(OperatorRequest.created_at)
    )
    return list(await session.scalars(query))


def payload(request: OperatorRequest, position: int | None) -> dict[str, Any]:
    return {"id": str(request.id), "status": request.status, "topic": request.topic, "position": position}


async def current(session: AsyncSession, assist_id: UUID) -> dict[str, Any] | None:
    request = await open_request(session, assist_id)
    if request is None:
        return None
    position = None
    if request.status == "queued":
        waiting = [item.id for item in await queue(session)]
        position = waiting.index(request.id) + 1
    return payload(request, position)
