from datetime import timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.config import settings
from max_assist.errors import Conflict, Forbidden, NotFound
from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist import callbacks, domain, events, journal
from max_assist.modules.assist.models import (
    AssistInvite,
    AssistParticipant,
    AssistSession,
    HelpCallback,
    SessionEvent,
)
from max_assist.modules.assist.realtime import hub
from max_assist.modules.identity.models import User
from max_assist.modules.notifications import service as notifications
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


async def live_assist_id(session: AsyncSession, service_session_id: UUID) -> UUID | None:
    return await session.scalar(
        select(AssistSession.id).where(
            AssistSession.service_session_id == service_session_id,
            AssistSession.status != "ended",
        )
    )


async def start(session: AsyncSession, user: User, service_session_id: UUID) -> AssistSession:
    service_session = await applications_service.get_owned(session, user, service_session_id)
    applications_service.require_draft(service_session)

    existing = await live_assist_id(session, service_session.id)
    if existing is not None:
        raise Conflict(
            "assist_session_exists",
            "Помощь по этому заявлению уже идёт",
            {"assist_session_id": str(existing)},
        )

    assist = domain.start(
        user,
        service_session.id,
        service_session.service_code,
        service_session.service_version,
    )
    session.add(assist)
    await session.flush()
    journal.note(session, assist.id, "session.created", {"step_id": service_session.current_step_id})
    return assist


async def create(session: AsyncSession, user: User, service_session_id: UUID) -> AssistSession:
    assist = await start(session, user, service_session_id)
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
    journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist, participant


async def decline_invite(session: AsyncSession, user: User, token: str) -> tuple[AssistSession, HelpCallback]:
    assist, invite = await find_invite(session, token, lock=True)
    domain.decline_invite(assist, invite, user)

    existing = await session.scalar(
        select(HelpCallback)
        .where(
            HelpCallback.owner_id == assist.owner_id,
            HelpCallback.helper_id == user.id,
            HelpCallback.service_session_id == assist.service_session_id,
            HelpCallback.status.in_(callbacks.OPEN_STATUSES),
        )
        .with_for_update()
    )
    callback = callbacks.promise(existing, assist.owner_id, user.id, assist.service_session_id)
    session.add(callback)
    deliveries = events.invite_declined(assist, invite.id, user, callback.id)
    journal.record(session, assist.id, deliveries)
    owner = await session.get(User, assist.owner_id)

    await session.commit()
    await events.publish(assist.id, deliveries)
    notifications.helper_busy(owner.id, user.display_name)
    notifications.come_back_later(user.id, owner.display_name, callback.id)
    return assist, callback


async def service_title(session: AsyncSession, service_session_id: UUID) -> str:
    service_session = await applications_service.get_by_id(session, service_session_id)
    definition = await applications_service.definition_of(session, service_session)
    return definition.title


async def list_callbacks(session: AsyncSession, user: User, as_owner: bool) -> list[HelpCallback]:
    mine = HelpCallback.owner_id == user.id if as_owner else HelpCallback.helper_id == user.id
    query = (
        select(HelpCallback)
        .where(mine, HelpCallback.status.in_(callbacks.OPEN_STATUSES), HelpCallback.expires_at > now())
        .order_by(HelpCallback.created_at.desc())
    )
    return list(await session.scalars(query))


async def find_callback(
    session: AsyncSession,
    callback_id: UUID,
    user_id: UUID,
    as_owner: bool,
) -> HelpCallback:
    callback = await session.get(HelpCallback, callback_id, with_for_update=True)
    if callback is None or (callback.owner_id if as_owner else callback.helper_id) != user_id:
        raise NotFound("Не найдено")
    return callback


async def helper_is_ready(session: AsyncSession, user: User, callback_id: UUID) -> HelpCallback:
    callback = await find_callback(session, callback_id, user.id, as_owner=False)
    callbacks.mark_ready(callback)
    title = await service_title(session, callback.service_session_id)
    await session.commit()
    notifications.helper_ready(callback.owner_id, user.display_name, title)
    return callback


async def call_back(
    session: AsyncSession,
    user: User,
    callback_id: UUID,
) -> tuple[AssistSession, AssistInvite, str]:
    callback = await find_callback(session, callback_id, user.id, as_owner=True)
    callbacks.require_open(callback)

    assist_id = await live_assist_id(session, callback.service_session_id)
    if assist_id is None:
        assist = await start(session, user, callback.service_session_id)
    else:
        assist = await get_visible(session, user, assist_id, lock=True)

    invite, token = domain.create_invite(assist, user)
    invite.target_user_id = callback.helper_id
    callbacks.close(callback, "used")
    title = await service_title(session, callback.service_session_id)
    await session.commit()
    notifications.help_requested(callback.helper_id, user.display_name, title, token)
    return assist, invite, token


async def dismiss_callback(session: AsyncSession, user: User, callback_id: UUID) -> None:
    callback = await find_callback(session, callback_id, user.id, as_owner=True)
    if callbacks.is_open(callback):
        callbacks.close(callback, "dismissed")
        await session.commit()


async def approve(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    was_waiting = assist.status == "waiting"
    participant = domain.approve(assist, user, participant_id)
    deliveries = await events.joined(session, assist, participant, was_waiting)
    journal.record(session, assist.id, deliveries)

    await session.commit()
    hub.update_status(assist.id, participant.id, participant.status)
    await events.publish(assist.id, deliveries)
    return assist


async def reject(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.reject(assist, user, participant_id)
    deliveries = events.rejected(assist, participant)
    journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist


async def remove(session: AsyncSession, user: User, assist_id: UUID, participant_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.remove(assist, user, participant_id)
    deliveries = events.removed(assist, participant)
    journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)
    return assist


async def leave(session: AsyncSession, user: User, assist_id: UUID) -> None:
    assist = await get_visible(session, user, assist_id, lock=True)
    participant = domain.leave(assist, user)
    deliveries = events.left(assist, participant)
    journal.record(session, assist.id, deliveries)

    await session.commit()
    await events.publish(assist.id, deliveries)


async def end(session: AsyncSession, user: User, assist_id: UUID) -> AssistSession:
    assist = await get_visible(session, user, assist_id, lock=True)
    recipients = events.live_ids(assist)
    domain.end_by_owner(assist, user)
    deliveries = events.ended(assist, recipients)
    journal.record(session, assist.id, deliveries)

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
        deliveries = events.ended(assist, recipients)
        journal.record(session, assist.id, deliveries)
        expired.append((assist.id, deliveries))

    await session.commit()
    for assist_id, deliveries in expired:
        await events.publish(assist_id, deliveries)
    return len(expired)


async def get_consultation(session: AsyncSession, user: User, assist_id: UUID) -> AssistSession:
    assist = await session.get(AssistSession, assist_id)
    if assist is None:
        raise NotFound("Консультация не найдена")

    participant = domain.participant_of(assist, user.id)
    if participant is None or participant.status in HIDDEN_STATUSES or participant.joined_at is None:
        raise NotFound("Консультация не найдена")
    return assist


async def list_consultations(
    session: AsyncSession,
    user: User,
    as_owner: bool,
    limit: int,
) -> list[AssistSession]:
    role_filter = AssistParticipant.role == "owner" if as_owner else AssistParticipant.role != "owner"
    query = (
        select(AssistSession)
        .join(AssistSession.participants)
        .where(
            AssistParticipant.user_id == user.id,
            AssistParticipant.joined_at.is_not(None),
            AssistParticipant.status.not_in(HIDDEN_STATUSES),
            role_filter,
        )
        .order_by(AssistSession.created_at.desc())
        .limit(limit)
    )
    return list(await session.scalars(query))


async def journal_of(session: AsyncSession, assist_id: UUID) -> list[SessionEvent]:
    query = (
        select(SessionEvent)
        .where(SessionEvent.assist_session_id == assist_id)
        .order_by(SessionEvent.occurred_at, SessionEvent.id)
    )
    return list(await session.scalars(query))
