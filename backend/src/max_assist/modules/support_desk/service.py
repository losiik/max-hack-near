from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.errors import Conflict, Forbidden, NotFound
from max_assist.modules.assist import domain as assist_domain
from max_assist.modules.assist import events, journal
from max_assist.modules.assist import service as assist_service
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.identity.models import User
from max_assist.modules.support_desk import queries
from max_assist.modules.support_desk.models import OperatorRequest
from max_assist.security import AgentPass
from max_assist.utils import now


def require_staff(user: User) -> None:
    if user.staff is None:
        raise Forbidden("Очередь доступна только сотрудникам МФЦ")


async def add_request(
    session: AsyncSession, user: User, assist: AssistSession, topic: str
) -> OperatorRequest:
    assist_domain.require_owner(assist, user)
    assist_domain.require_open(assist)

    if await queries.open_request(session, assist.id) is not None:
        raise Conflict("operator_request_exists", "Сотрудник уже вызван")

    request = OperatorRequest(assist_session_id=assist.id, source="owner", status="queued", topic=topic)
    session.add(request)
    assist_domain.touch(assist)
    journal.note(session, assist.id, "operator.requested", {"topic": topic})
    return request


async def request_by_agent(
    session: AsyncSession,
    agent: AgentPass,
    assist_id: UUID,
    topic: str,
    summary: str | None,
) -> OperatorRequest:
    # цифровой сотрудник не справился и зовёт человека, резюме увидит сотрудник в очереди
    if agent.assist_session_id != assist_id:
        raise NotFound("Помощь не найдена")
    assist = await session.get(AssistSession, assist_id, with_for_update=True)
    assist_domain.require_open(assist)
    agent_participant = assist_domain.ai_agent_of(assist)
    if agent_participant is None or agent_participant.id != agent.participant_id:
        raise Forbidden("Цифровой сотрудник уже не во встрече")
    if await queries.open_request(session, assist.id) is not None:
        raise Conflict("operator_request_exists", "Сотрудник уже вызван")

    request = OperatorRequest(
        assist_session_id=assist.id,
        source="ai_escalation",
        status="queued",
        topic=topic,
        context={"ai_summary": summary} if summary else {},
    )
    session.add(request)
    assist_domain.touch(assist)
    journal.note(session, assist.id, "operator.requested", {"topic": topic, "source": "ai_escalation"})
    await session.commit()
    await announce_queue(session)
    return request


async def request_operator(session: AsyncSession, user: User, assist_id: UUID, topic: str) -> OperatorRequest:
    assist = await assist_service.get_visible(session, user, assist_id, lock=True)
    request = await add_request(session, user, assist, topic)
    await session.commit()
    await announce_queue(session)
    return request


async def request_from_application(
    session: AsyncSession,
    user: User,
    service_session_id: UUID,
    topic: str,
) -> tuple[AssistSession, OperatorRequest]:
    assist_id = await assist_service.live_assist_id(session, service_session_id)
    if assist_id is None:
        assist = await assist_service.start(session, user, service_session_id)
    else:
        assist = await assist_service.get_visible(session, user, assist_id, lock=True)

    request = await add_request(session, user, assist, topic)
    await session.commit()
    await announce_queue(session)
    return assist, request


async def cancel(session: AsyncSession, user: User, assist_id: UUID) -> None:
    assist = await assist_service.get_visible(session, user, assist_id, lock=True)
    assist_domain.require_owner(assist, user)
    request = await queries.open_request(session, assist.id)
    if request is None or request.status != "queued":
        raise Conflict("operator_request_not_queued", "Сотрудник уже подключился или не вызывался")

    request.status = "cancelled"
    request.closed_at = now()
    await session.commit()
    await announce_queue(session, also=request)


async def claim(session: AsyncSession, user: User, request_id: UUID) -> tuple[AssistSession, UUID]:
    require_staff(user)
    request = await session.get(OperatorRequest, request_id, with_for_update=True)
    if request is None:
        raise NotFound("Обращение не найдено")
    # два сотрудника нажали «Взять» одновременно: второй ждёт блокировку и видит, что обращение занято
    if request.status != "queued":
        raise Conflict("operator_request_taken", "Обращение уже взял другой сотрудник")

    assist = await session.get(AssistSession, request.assist_session_id, with_for_update=True)
    was_waiting = assist.status == "waiting"
    participant = assist_domain.add_operator(assist, user)
    request.status = "claimed"
    request.claimed_by = user.id
    request.claimed_at = now()
    deliveries = await events.joined(session, assist, participant, was_waiting)
    journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)
    await announce_queue(session, also=request)
    return assist, participant.id


async def complete(session: AsyncSession, user: User, request_id: UUID) -> None:
    request = await session.get(OperatorRequest, request_id, with_for_update=True)
    if request is None or request.claimed_by != user.id:
        raise NotFound("Обращение не найдено")
    if request.status != "claimed":
        raise Conflict("operator_request_not_claimed", "Обращение уже закрыто")

    request.status = "completed"
    request.closed_at = now()
    assist = await session.get(AssistSession, request.assist_session_id, with_for_update=True)
    deliveries = []
    participant = assist_domain.participant_of(assist, user.id)
    if assist.status != "ended" and participant.status == "active":
        assist_domain.leave(assist, user)
        deliveries = events.left(assist, participant)
        journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)
    await announce_queue(session, also=request)


async def close_for_ended(session: AsyncSession, assist_id: UUID) -> None:
    request = await queries.open_request(session, assist_id)
    if request is None:
        return
    request.status = "cancelled" if request.status == "queued" else "completed"
    request.closed_at = now()
    await session.commit()
    await announce_queue(session)


async def announce_queue(session: AsyncSession, also: OperatorRequest | None = None) -> None:
    # позиции сдвигаются у всех, кто ждёт, поэтому сообщаем каждому
    waiting = await queries.queue(session)
    changed = [(item, index) for index, item in enumerate(waiting, start=1)]
    if also is not None and also not in waiting:
        changed.append((also, None))

    for request, position in changed:
        assist = await session.get(AssistSession, request.assist_session_id)
        owner = assist_domain.participant_of(assist, assist.owner_id)
        message = events.envelope(assist.id, "operator_request.updated", queries.payload(request, position))
        await events.publish(assist.id, [events.Delivery([owner.id], message)])
