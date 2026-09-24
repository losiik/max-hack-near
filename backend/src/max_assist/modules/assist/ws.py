from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from max_assist.db import session_factory
from max_assist.deps import load_user
from max_assist.errors import AppError
from max_assist.modules.assist import commands, domain, events
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.assist.realtime import Viewer, hub
from max_assist.modules.identity.models import User
from max_assist.tasks import uncancellable

router = APIRouter()


class Refused(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def refusal(assist: AssistSession | None, user: User) -> int | None:
    if assist is None:
        return events.CLOSE_NOT_FOUND
    if assist.status == "ended":
        return events.CLOSE_ENDED

    participant = domain.participant_of(assist, user.id)
    if participant is None or participant.status not in domain.LIVE_STATUSES:
        return events.CLOSE_FORBIDDEN
    return None


async def check_access(assist_id: UUID, token: str) -> tuple[User, Viewer]:
    async with session_factory() as db:
        try:
            user = await load_user(db, token)
        except AppError as error:
            raise Refused(events.CLOSE_UNAUTHORIZED) from error

        assist = await db.get(AssistSession, assist_id)
        code = refusal(assist, user)
        if code is not None:
            raise Refused(code)

        participant = domain.participant_of(assist, user.id)
        viewer = Viewer(
            participant_id=participant.id,
            role=participant.role,
            status=participant.status,
            display_name=participant.display_name,
        )
        return user, viewer


async def prepare_greeting(assist_id: UUID, user: User, participant_id: UUID) -> tuple[dict[str, Any], int]:
    async with session_factory() as db:
        assist = await db.get(AssistSession, assist_id)
        code = refusal(assist, user)
        if code is not None:
            raise Refused(code)

        participant = domain.find_participant(assist, participant_id)
        return await events.greeting(db, assist, participant), assist.last_seq


@router.websocket("/ws/assist/{assist_id}")
async def assist_socket(websocket: WebSocket, assist_id: UUID, token: str = "") -> None:
    await websocket.accept()

    try:
        user, viewer = await uncancellable(check_access(assist_id, token))
    except Refused as refused:
        await websocket.close(refused.code)
        return

    connection, came_online = hub.connect(assist_id, viewer, websocket)
    try:
        greeting, last_seq = await uncancellable(prepare_greeting(assist_id, user, viewer.participant_id))
        await connection.open(greeting, last_seq)
        if came_online:
            events.announce_presence_later(assist_id, viewer.participant_id)

        while True:
            reply = await commands.handle(assist_id, connection, await websocket.receive_text())
            if reply is not None:
                await connection.send(reply)
    except Refused as refused:
        await websocket.close(refused.code)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        if hub.disconnect(assist_id, viewer.participant_id, connection):
            events.announce_presence_later(assist_id, viewer.participant_id)
