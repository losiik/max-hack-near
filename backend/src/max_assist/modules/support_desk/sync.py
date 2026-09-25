import logging
from uuid import UUID

from max_assist.db import session_factory
from max_assist.modules.assist.events import Delivery
from max_assist.modules.support_desk import service
from max_assist.tasks import run_in_background

logger = logging.getLogger("max_assist.support_desk")


async def close_request(assist_id: UUID) -> None:
    try:
        async with session_factory() as db:
            await service.close_for_ended(db, assist_id)
    except Exception:
        logger.exception("could not close operator request of %s", assist_id)


def on_published(assist_id: UUID, deliveries: list[Delivery]) -> None:
    if any(item.message and item.message["event"] == "session.ended" for item in deliveries):
        run_in_background(close_request(assist_id))
