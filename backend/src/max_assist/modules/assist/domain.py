import hashlib
import secrets
import uuid
from datetime import timedelta

from max_assist.errors import Conflict, Forbidden, Gone, NotFound, Unprocessable
from max_assist.modules.assist.models import AssistInvite, AssistParticipant, AssistSession
from max_assist.modules.identity.models import User
from max_assist.utils import now

INVITE_TTL = timedelta(minutes=30)
MAX_ACTIVE_HELPERS = 2
LIVE_STATUSES = {"pending", "active"}

BADGES = {
    "trusted_helper": "Доверенный помощник",
    "invited_helper": "Помощник по ссылке",
}

VIEW = {"view_step", "view_structure", "view_public_values", "view_validation_errors"}
HELPER = {"annotate", "speak", "leave_session"}

ROLE_CAPABILITIES = {
    "owner": frozenset(
        VIEW
        | {
            "view_sensitive_values",
            "view_validation_details",
            "flag_confusion",
            "speak",
            "listen_recording",
            "edit_fields",
            "navigate",
            "submit",
            "manage_participants",
            "invite",
            "end_session",
            "request_operator",
        }
    ),
    "trusted_helper": frozenset(VIEW | HELPER),
    "invited_helper": frozenset(VIEW | HELPER),
    "government_operator": frozenset(VIEW | HELPER | {"view_validation_details", "view_operator_hints"}),
    "ai_agent": frozenset(
        VIEW | HELPER | {"view_validation_details", "view_operator_hints", "request_operator"}
    ),
}

INVITE_PROBLEMS = {
    "session_ended": ("session_ended", "Помощь уже завершена"),
    "revoked": ("invite_revoked", "Приглашение отозвано"),
    "used": ("invite_used", "Приглашение уже использовано"),
    "declined": ("invite_declined", "На это приглашение уже ответили «Сейчас занят»"),
    "expired": ("invite_expired", "Срок действия приглашения истёк"),
}


def capabilities_of(role: str) -> frozenset[str]:
    return ROLE_CAPABILITIES[role]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def require_recording_consent(user: User) -> None:
    if user.recording_consent_at is None:
        raise Conflict("recording_consent_required", "Нужно согласие на запись разговора")


def start(
    owner: User,
    service_session_id: uuid.UUID,
    service_code: str,
    service_version: int,
) -> AssistSession:
    require_recording_consent(owner)
    moment = now()
    session = AssistSession(
        id=uuid.uuid4(),
        service_session_id=service_session_id,
        owner_id=owner.id,
        service_code=service_code,
        service_version=service_version,
        status="waiting",
        last_seq=0,
        created_at=moment,
        last_activity_at=moment,
        invites=[],
    )
    session.participants.append(
        AssistParticipant(
            id=uuid.uuid4(),
            user_id=owner.id,
            kind="human",
            role="owner",
            status="active",
            joined_via="owner",
            display_name=owner.display_name,
            badge_verified=False,
            requested_at=moment,
            joined_at=moment,
        )
    )
    return session


def participant_of(session: AssistSession, user_id: uuid.UUID) -> AssistParticipant | None:
    return next((item for item in session.participants if item.user_id == user_id), None)


def find_participant(session: AssistSession, participant_id: uuid.UUID) -> AssistParticipant:
    for participant in session.participants:
        if participant.id == participant_id:
            return participant
    raise NotFound("Участник не найден")


def active_helpers(session: AssistSession) -> list[AssistParticipant]:
    return [item for item in session.participants if item.role != "owner" and item.status == "active"]


def require_owner(session: AssistSession, user: User) -> None:
    if user.id != session.owner_id:
        raise Forbidden("Управлять помощью может только владелец")


def require_open(session: AssistSession) -> None:
    if session.status == "ended":
        raise Gone("session_ended", "Помощь уже завершена")


def require_helper_slot(session: AssistSession) -> None:
    if len(active_helpers(session)) >= MAX_ACTIVE_HELPERS:
        raise Conflict("helpers_limit_reached", "Подключено максимальное число помощников")


def touch(session: AssistSession) -> None:
    session.last_activity_at = now()


def activate(session: AssistSession, participant: AssistParticipant) -> None:
    moment = now()
    participant.status = "active"
    participant.joined_at = moment
    if session.status == "waiting":
        session.status = "active"
        session.started_at = moment


def create_invite(
    session: AssistSession,
    actor: User,
    kind: str = "link",
    target_user_id: uuid.UUID | None = None,
) -> tuple[AssistInvite, str]:
    require_owner(session, actor)
    require_open(session)

    token = secrets.token_urlsafe(24)
    moment = now()
    invite = AssistInvite(
        id=uuid.uuid4(),
        kind=kind,
        target_user_id=target_user_id,
        token_hash=hash_token(token),
        created_at=moment,
        expires_at=moment + INVITE_TTL,
    )
    session.invites.append(invite)
    touch(session)
    return invite, token


def invite_status(session: AssistSession, invite: AssistInvite) -> str:
    if session.status == "ended":
        return "session_ended"
    if invite.revoked_at is not None:
        return "revoked"
    if invite.used_at is not None:
        return "used"
    if invite.declined_at is not None:
        return "declined"
    if invite.expires_at <= now():
        return "expired"
    return "valid"


def open_invites(session: AssistSession) -> list[AssistInvite]:
    return [invite for invite in session.invites if invite_status(session, invite) == "valid"]


def check_invite(session: AssistSession, invite: AssistInvite) -> None:
    if invite not in session.invites:
        raise NotFound("Приглашение не найдено")
    status = invite_status(session, invite)
    if status != "valid":
        raise Gone(*INVITE_PROBLEMS[status])


def require_addressee(invite: AssistInvite, user: User) -> None:
    # приглашение, отправленное ботом конкретному человеку, не сработает у того, кому его переслали
    if invite.target_user_id is not None and invite.target_user_id != user.id:
        raise Forbidden("Это приглашение отправлено другому человеку")


def revoke_invite(session: AssistSession, actor: User, invite_id: uuid.UUID) -> None:
    require_owner(session, actor)
    require_open(session)

    invite = next((item for item in session.invites if item.id == invite_id), None)
    if invite is None:
        raise NotFound("Приглашение не найдено")
    if invite.used_at is not None:
        raise Conflict("invite_used", "Приглашение уже использовано")

    if invite.revoked_at is None:
        invite.revoked_at = now()
    touch(session)


def accept_invite(
    session: AssistSession,
    invite: AssistInvite,
    user: User,
    is_trusted: bool = False,
) -> AssistParticipant:
    require_open(session)
    check_invite(session, invite)

    if user.id == session.owner_id:
        raise Unprocessable("owner_cannot_join", "Нельзя подключиться помощником к своей услуге")
    require_addressee(invite, user)

    participant = participant_of(session, user.id)
    if participant is not None and participant.status in LIVE_STATUSES:
        raise Conflict("already_participant", "Вы уже подключены к этой помощи")
    require_helper_slot(session)
    require_recording_consent(user)

    if participant is None:
        participant = AssistParticipant(id=uuid.uuid4(), user_id=user.id, kind="human")
        session.participants.append(participant)

    role = "trusted_helper" if is_trusted else "invited_helper"
    moment = now()
    participant.role = role
    participant.status = "pending"
    participant.joined_via = "trusted_call" if invite.kind == "trusted_call" else "invite_link"
    participant.invite_id = invite.id
    participant.display_name = user.display_name
    participant.badge_label = BADGES[role]
    participant.badge_verified = False
    participant.requested_at = moment
    participant.joined_at = None
    participant.left_at = None

    invite.used_at = moment
    invite.used_by = user.id

    if is_trusted:
        activate(session, participant)
    touch(session)
    return participant


def decline_invite(session: AssistSession, invite: AssistInvite, user: User) -> None:
    require_open(session)
    check_invite(session, invite)

    if user.id == session.owner_id:
        raise Unprocessable("owner_cannot_join", "Нельзя ответить на своё же приглашение")
    require_addressee(invite, user)
    participant = participant_of(session, user.id)
    if participant is not None and participant.status in LIVE_STATUSES:
        raise Conflict("already_participant", "Вы уже подключены к этой помощи")

    invite.declined_at = now()
    invite.declined_by = user.id
    touch(session)


def add_operator(session: AssistSession, user: User) -> AssistParticipant:
    require_open(session)
    if user.staff is None:
        raise Forbidden("Брать обращения может только сотрудник МФЦ")
    if user.id == session.owner_id:
        raise Unprocessable("owner_cannot_join", "Нельзя подключиться помощником к своей услуге")

    participant = participant_of(session, user.id)
    if participant is not None and participant.status in LIVE_STATUSES:
        raise Conflict("already_participant", "Вы уже подключены к этой помощи")
    require_helper_slot(session)
    require_recording_consent(user)

    if participant is None:
        participant = AssistParticipant(id=uuid.uuid4(), user_id=user.id, kind="human")
        session.participants.append(participant)

    # сотрудник представляет организацию, поэтому имя показываем полностью
    participant.role = "government_operator"
    participant.joined_via = "operator_queue"
    participant.invite_id = None
    participant.display_name = user.full_name
    participant.badge_label = f"Сотрудник МФЦ · {user.staff.organization}"
    participant.badge_verified = user.staff.verified_at is not None
    participant.requested_at = now()
    participant.left_at = None
    activate(session, participant)
    touch(session)
    return participant


def approve(session: AssistSession, actor: User, participant_id: uuid.UUID) -> AssistParticipant:
    require_owner(session, actor)
    require_open(session)

    participant = find_participant(session, participant_id)
    if participant.status != "pending":
        raise Conflict("participant_not_pending", "Участник не ждёт подтверждения")
    require_helper_slot(session)

    activate(session, participant)
    touch(session)
    return participant


def reject(session: AssistSession, actor: User, participant_id: uuid.UUID) -> AssistParticipant:
    require_owner(session, actor)
    require_open(session)

    participant = find_participant(session, participant_id)
    if participant.status != "pending":
        raise Conflict("participant_not_pending", "Участник не ждёт подтверждения")

    participant.status = "rejected"
    participant.left_at = now()
    touch(session)
    return participant


def remove(session: AssistSession, actor: User, participant_id: uuid.UUID) -> AssistParticipant:
    require_owner(session, actor)
    require_open(session)

    participant = find_participant(session, participant_id)
    if participant.role == "owner":
        raise Unprocessable("owner_cannot_be_removed", "Владельца нельзя отключить")
    if participant.status != "active":
        raise Conflict("participant_not_active", "Участник не подключён")

    participant.status = "removed"
    participant.left_at = now()
    touch(session)
    return participant


def leave(session: AssistSession, user: User) -> AssistParticipant:
    require_open(session)

    participant = participant_of(session, user.id)
    if participant is None or participant.status not in LIVE_STATUSES:
        raise NotFound("Вы не участвуете в этой помощи")
    if participant.role == "owner":
        raise Unprocessable("owner_cannot_leave", "Владелец завершает помощь, а не выходит из неё")

    participant.status = "left"
    participant.left_at = now()
    touch(session)
    return participant


def end(session: AssistSession, reason: str) -> None:
    require_open(session)
    moment = now()

    for participant in session.participants:
        if participant.role != "owner" and participant.status in LIVE_STATUSES:
            participant.status = "left"
            participant.left_at = moment

    for invite in session.invites:
        if invite.used_at is None and invite.revoked_at is None:
            invite.revoked_at = moment

    session.status = "ended"
    session.end_reason = reason
    session.ended_at = moment
    session.last_activity_at = moment


def end_by_owner(session: AssistSession, actor: User) -> None:
    require_owner(session, actor)
    end(session, "owner_ended")
