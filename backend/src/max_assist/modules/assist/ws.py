from typing import Any
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.db import session_factory
from max_assist.deps import load_user
from max_assist.errors import AppError
from max_assist.modules.assist import commands, domain, events
from max_assist.modules.assist.models import AssistParticipant, AssistSession
from max_assist.modules.assist.realtime import Viewer, hub
from max_assist.security import read_agent_token
from max_assist.tasks import uncancellable

router = APIRouter()


class Refused(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


def live_participant(assist: AssistSession | None, participant_id: UUID | None) -> AssistParticipant:
    if assist is None:
        raise Refused(events.CLOSE_NOT_FOUND)
    if assist.status == "ended":
        raise Refused(events.CLOSE_ENDED)

    participant = next((item for item in assist.participants if item.id == participant_id), None)
    if participant is None or participant.status not in domain.LIVE_STATUSES:
        raise Refused(events.CLOSE_FORBIDDEN)
    return participant


async def participant_id_of(db: AsyncSession, assist: AssistSession | None, token: str) -> UUID | None:
    # цифровой сотрудник входит своим токеном, и тот открывает только его встречу
    try:
        agent = read_agent_token(token)
        if agent is not None:
            return agent.participant_id if assist and agent.assist_session_id == assist.id else None
        user = await load_user(db, token)
    except AppError as error:
        raise Refused(events.CLOSE_UNAUTHORIZED) from error

    participant = domain.participant_of(assist, user.id) if assist else None
    return participant.id if participant else None


async def check_access(assist_id: UUID, token: str) -> Viewer:
    async with session_factory() as db:
        assist = await db.get(AssistSession, assist_id)
        participant = live_participant(assist, await participant_id_of(db, assist, token))
        return Viewer(
            participant_id=participant.id,
            role=participant.role,
            status=participant.status,
            display_name=participant.display_name,
        )


async def prepare_greeting(assist_id: UUID, participant_id: UUID) -> tuple[dict[str, Any], int]:
    async with session_factory() as db:
        assist = await db.get(AssistSession, assist_id)
        participant = live_participant(assist, participant_id)
        return await events.greeting(db, assist, participant), assist.last_seq


@router.websocket("/ws/assist/{assist_id}")
async def assist_socket(websocket: WebSocket, assist_id: UUID, token: str = "") -> None:
    await websocket.accept()

    try:
        viewer = await uncancellable(check_access(assist_id, token))
    except Refused as refused:
        await websocket.close(refused.code)
        return

    connection, came_online = hub.connect(assist_id, viewer, websocket)
    try:
        greeting, last_seq = await uncancellable(prepare_greeting(assist_id, viewer.participant_id))
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
            active_select = hub.get_select_view(assist_id)
            if viewer.role == "owner" and active_select:
                hub.set_select_view(assist_id, None)
                helpers = hub.active_participants(assist_id, exclude=viewer.participant_id)
                await events.publish(assist_id, events.select_view(assist_id, None, helpers))
            events.announce_presence_later(assist_id, viewer.participant_id)
