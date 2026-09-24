from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.errors import Conflict, Forbidden, NotFound
from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist import domain, events
from max_assist.modules.assist.models import AssistInvite, AssistParticipant, AssistSession
from max_assist.modules.assist.realtime import hub
from max_assist.modules.identity.models import User
from max_assist.utils import now

HIDDEN_STATUSES = {"rejected", "removed"}


async def get_visible(
    session: AsyncSession,
    user: User,
    assist_id: UUID,
    lock: bool = False,
) -> AssistSession:
    # блокировка строки выстраивает изменения одной сессии в очередь: номера событий не повторяются
    assist = await session.get(AssistSession, assist_id, with_for_update=lock)
    if assist is None:
        raise NotFound("Помощь не найдена")

    participant = domain.participant_of(assist, user.id)
    if participant is None or participant.status in HIDDEN_STATUSES:
        raise NotFound("Помощь не найдена")
    return assist


async def get_active(session: AsyncSession, user: User, assist_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id)
    if domain.participant_of(assist, user.id).status != "active":
        raise Forbidden("Форма доступна только подключённым участникам")
    return assist


async def create(session: AsyncSession, user: User, service_session_id: UUID) -> AssistSession:
    service_session = await applications_service.get_owned(session, user, service_session_id)
    applications_service.require_draft(service_session)

    existing = await session.scalar(
        select(AssistSession.id).where(
            AssistSession.service_session_id == service_session.id,
            AssistSession.status != "ended",
        )
    )
    if existing is not None:
        raise Conflict(
            "assist_session_exists",
            "Помощь по этому заявлению уже идёт",
            {"assist_session_id": str(existing)},
        )

    assist = domain.start(user, service_session.id)
    session.add(assist)
    await session.commit()
    return assist


async def list_active(session: AsyncSession, user: User) -> list[AssistSession]:
    query = (
        select(AssistSession)
        .join(AssistSession.participants)
        .where(
            AssistParticipant.user_id == user.id,
            AssistParticipant.status.in_(domain.LIVE_STATUSES),
            AssistSession.status != "ended",
        )
        .order_by(AssistSession.created_at.desc())
    )
    return list(await session.scalars(query))


async def create_invite(
    session: AsyncSession,
    user: User,
    assist_id: UUID,
) -> tuple[AssistSession, AssistInvite, str]:
    assist = await get_visible(session, user, assist_id, lock=True)
    invite, token = domain.create_invite(assist, user)
    await session.commit()
    return assist, invite, token


async def revoke_invite(session: AsyncSession, user: User, assist_id: UUID, invite_id: UUID) -> None:
    assist = await get_visible(session, user, assist_id, lock=True)
    domain.revoke_invite(assist, user, invite_id)
    await session.commit()


async def find_invite(
    session: AsyncSession,
    token: str,
    lock: bool = False,
) -> tuple[AssistSession, AssistInvite]:
    invite = await session.scalar(
        select(AssistInvite).where(AssistInvite.token_hash == domain.hash_token(token))
    )
    if invite is None:
        raise NotFound("Приглашение не найдено")
    assist = await session.get(AssistSession, invite.assist_session_id, with_for_update=lock)
    return assist, invite


async def accept_invite(
    session: AsyncSession,
    user: User,
    token: str,
) -> tuple[AssistSession, AssistParticipant]:
    assist, invite = await find_invite(session, token, lock=True)
    participant = domain.accept_invite(assist, invite, user)
    deliveries = await events.join_requested(session, assist, participant)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist, participant


async def approve(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    was_waiting = assist.status == "waiting"
    participant = domain.approve(assist, user, participant_id)
    deliveries = await events.joined(session, assist, participant, was_waiting)

    await session.commit()
    hub.update_status(assist.id, participant.id, participant.status)
    await events.publish(assist.id, deliveries)
    return assist


async def reject(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.reject(assist, user, participant_id)
    deliveries = events.rejected(assist, participant)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist


async def remove(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.remove(assist, user, participant_id)
    deliveries = events.removed(assist, participant)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist


async def leave(session: AsyncSession, user: User, assist_id: UUID) -> None:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.leave(assist, user)
    deliveries = events.left(assist, participant)

    await session.commit()
    await events.publish(assist.id, deliveries)


async def end(session: AsyncSession, user: User, assist_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    recipients = events.live_ids(assist)
    domain.end_by_owner(assist, user)
    deliveries = events.ended(assist, recipients)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist


async def expire_idle(session: AsyncSession) -> int:
    moment = now()
    waiting_border = moment - timedelta(minutes=settings.assist_waiting_timeout_minutes)
    idle_border = moment - timedelta(minutes=settings.assist_idle_timeout_minutes)
    candidates = await session.scalars(
        select(AssistSession)
        .where(
            or_(
                and_(AssistSession.status == "waiting", AssistSession.last_activity_at < waiting_border),
                and_(AssistSession.status == "active", AssistSession.last_activity_at < idle_border),
            )
        )
        .with_for_update(skip_locked=True)
    )

    expired = []
    for assist in list(candidates):
        # пока кто-то подключён, помощь идёт, даже если в базу давно ничего не писали
        if hub.online(assist.id):
            continue
        recipients = events.live_ids(assist)
        domain.end(assist, "expired")
        expired.append((assist.id, events.ended(assist, recipients)))

    await session.commit()
    for assist_id, deliveries in expired:
        await events.publish(assist_id, deliveries)
    return len(expired)
