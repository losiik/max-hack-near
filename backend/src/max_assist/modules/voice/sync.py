import asyncio
import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from functools import partial
from uuid import UUID

from max_assist.modules.assist.events import Delivery
from max_assist.modules.voice.livekit import rooms
from max_assist.tasks import run_in_background

logger = logging.getLogger("max_assist.voice")

# действия с одной комнатой идут по очереди: закрытие не обгонит открытие
room_locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)


async def in_turn(assist_id: UUID, action: Callable[[], Awaitable[None]], what: str) -> None:
    async with room_locks[assist_id]:
        try:
            await action()
        except Exception:
            logger.exception("voice room %s: %s failed", assist_id, what)


def on_published(assist_id: UUID, deliveries: list[Delivery]) -> None:
    room = str(assist_id)
    for delivery in deliveries:
        message = delivery.message
        if message is None:
            continue

        event = message["event"]
        if event == "session.activated":
            run_in_background(in_turn(assist_id, partial(rooms.open, room), "open"))
        elif event == "participant.left":
            identity = message["payload"]["participant_id"]
            run_in_background(in_turn(assist_id, partial(rooms.remove, room, identity), "remove"))
        elif event == "session.ended":
            run_in_background(close(assist_id))


async def call_agent(assist_id: UUID, metadata: str) -> None:
    # комната должна появиться раньше, чем агент в неё войдёт; ошибку отдаём наверх
    async with room_locks[assist_id]:
        await rooms.open(str(assist_id))
        await rooms.call_agent(str(assist_id), metadata)


async def close(assist_id: UUID) -> None:
    await in_turn(assist_id, partial(rooms.close, str(assist_id)), "close")
    room_locks.pop(assist_id, None)
