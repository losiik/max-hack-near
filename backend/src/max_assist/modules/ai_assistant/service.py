import json
import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.errors import AppError, Forbidden, NotFound
from max_assist.modules.ai_assistant.models import AgentTurn
from max_assist.modules.assist import domain, events, journal
from max_assist.modules.assist import service as assist_service
from max_assist.modules.assist.models import AssistParticipant, AssistSession
from max_assist.modules.assist.realtime import hub
from max_assist.modules.identity.models import User
from max_assist.modules.voice import sync as voice_sync
from max_assist.security import AgentPass, create_agent_token
from max_assist.utils import now

logger = logging.getLogger("max_assist.ai")


def unavailable() -> AppError:
    return AppError(
        "digital_employee_unavailable",
        "Цифровой сотрудник сейчас недоступен, позовите близкого или сотрудника МФЦ",
        503,
    )


async def call(db: AsyncSession, user: User, assist: AssistSession) -> AssistSession:
    if not settings.yandex_api_key:
        raise unavailable()

    was_waiting = assist.status == "waiting"
    participant = domain.add_ai_agent(assist, user)
    deliveries = await events.joined(db, assist, participant, was_waiting)
    journal.record(db, assist.id, deliveries)
    await db.commit()
    await events.publish(assist.id, deliveries)

    metadata = json.dumps(
        {
            "assist_session_id": str(assist.id),
            "participant_id": str(participant.id),
            "token": create_agent_token(participant.id, assist.id),
        }
    )
    try:
        await voice_sync.call_agent(assist.id, metadata)
    except Exception as error:
        logger.exception("could not call the digital employee to %s", assist.id)
        await drop(db, assist.id, "agent_unavailable")
        raise unavailable() from error
    return assist


async def call_to_session(db: AsyncSession, user: User, assist_id: UUID) -> AssistSession:
    assist = await assist_service.get_visible(db, user, assist_id, lock=True)
    return await call(db, user, assist)


async def call_to_application(db: AsyncSession, user: User, service_session_id: UUID) -> AssistSession:
    assist_id = await assist_service.live_assist_id(db, service_session_id)
    if assist_id is None:
        assist = await assist_service.start(db, user, service_session_id)
    else:
        assist = await assist_service.get_visible(db, user, assist_id, lock=True)
    return await call(db, user, assist)


async def drop(db: AsyncSession, assist_id: UUID, reason: str) -> None:
    assist = await db.get(AssistSession, assist_id, with_for_update=True, populate_existing=True)
    participant = domain.remove_ai_agent(assist)
    deliveries = events.agent_left(assist, participant, reason)
    journal.record(db, assist.id, deliveries)
    await db.commit()
    await events.publish(assist.id, deliveries)


def require_own_session(agent: AgentPass, assist_id: UUID) -> None:
    if agent.assist_session_id != assist_id:
        raise NotFound("Помощь не найдена")


async def release(db: AsyncSession, caller: User | AgentPass, assist_id: UUID) -> None:
    # отпустить агента может владелец, а уйти сам — только агент этой встречи
    if isinstance(caller, AgentPass):
        require_own_session(caller, assist_id)
        assist = await db.get(AssistSession, assist_id, with_for_update=True)
        agent = domain.ai_agent_of(assist) if assist else None
        if agent is None or agent.id != caller.participant_id:
            raise NotFound("Цифровой сотрудник не подключён")
        reason = "left"
    else:
        assist = await assist_service.get_visible(db, caller, assist_id, lock=True)
        domain.require_owner(assist, caller)
        reason = "removed"
    await drop(db, assist.id, reason)


async def agent_participant(db: AsyncSession, agent: AgentPass) -> AssistParticipant:
    participant = await db.get(AssistParticipant, agent.participant_id)
    if participant is None or participant.assist_session_id != agent.assist_session_id:
        raise Forbidden("Токен цифрового сотрудника недействителен")
    return participant


async def record_turn(db: AsyncSession, agent: AgentPass, turn: dict[str, Any]) -> AgentTurn:
    participant = await agent_participant(db, agent)
    row = AgentTurn(assist_session_id=participant.assist_session_id, participant_id=participant.id, **turn)
    db.add(row)
    await db.commit()
    return row


async def drop_silent(db: AsyncSession) -> int:
    # агента позвали, но он так и не подключился или отвалился — не держим место помощника
    border = now() - timedelta(seconds=settings.agent_join_timeout_seconds)
    rows = await db.execute(
        select(AssistParticipant.assist_session_id, AssistParticipant.id).where(
            AssistParticipant.role == "ai_agent",
            AssistParticipant.status == "active",
            AssistParticipant.joined_at < border,
        )
    )
    dropped = 0
    for assist_id, participant_id in rows.all():
        if participant_id in hub.online(assist_id):
            continue
        try:
            await drop(db, assist_id, "agent_unavailable")
        except AppError:
            # пока проверяли, агента уже отпустили или встреча закончилась
            await db.rollback()
            continue
        dropped += 1
    return dropped
