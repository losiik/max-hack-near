import hashlib
import logging
import secrets
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.errors import Conflict, Forbidden, NotFound, Unprocessable
from max_assist.modules.applications.crypto import decrypt_values, encrypt_values
from max_assist.modules.applications.domain import ApplicationForm, FieldError, split_by_privacy
from max_assist.modules.applications.models import ServiceSession, ServiceSessionInbox
from max_assist.modules.catalog import service as catalog_service
from max_assist.modules.catalog.schema import ServiceDefinition
from max_assist.modules.identity.models import User
from max_assist.utils import now

CODE_TTL = timedelta(minutes=5)
CODE_RESEND_DELAY = timedelta(seconds=30)
MAX_CODE_ATTEMPTS = 5

logger = logging.getLogger("max_assist.applications")

listeners: list[Callable[[str, ServiceSession, dict[str, Any]], Awaitable[None]]] = []
active_assist_lookup: Callable[[AsyncSession, UUID], Awaitable[UUID | None]] | None = None


async def active_assist_id(session: AsyncSession, row: ServiceSession) -> UUID | None:
    if active_assist_lookup is None:
        return None
    return await active_assist_lookup(session, row.id)


async def notify(event: str, row: ServiceSession, **details: Any) -> None:
    for listener in listeners:
        try:
            await listener(event, row, details)
        except Exception:
            logger.exception("listener failed on %s", event)


def read_values(row: ServiceSession) -> dict[str, Any]:
    return {**row.public_data, **decrypt_values(row.sensitive_data_enc)}


def write_values(row: ServiceSession, definition: ServiceDefinition, values: dict[str, Any]) -> None:
    public, sensitive = split_by_privacy(definition, values)
    row.public_data = public
    row.sensitive_data_enc = encrypt_values(sensitive)


async def definition_of(session: AsyncSession, row: ServiceSession) -> ServiceDefinition:
    return await catalog_service.load_definition(session, row.service_code, row.service_version)


async def get_by_id(session: AsyncSession, session_id: UUID) -> ServiceSession:
    row = await session.get(ServiceSession, session_id)
    if row is None:
        raise NotFound("Заявление не найдено")
    return row


async def get_owned(session: AsyncSession, user: User, session_id: UUID) -> ServiceSession:
    row = await get_by_id(session, session_id)
    if row.owner_id != user.id:
        raise Forbidden("Заявление принадлежит другому пользователю")
    return row


def require_draft(row: ServiceSession) -> None:
    if row.status != "draft":
        raise Conflict("service_session_closed", "Заявление больше нельзя изменять")


async def count_drafts(session: AsyncSession, user: User) -> int:
    query = select(func.count()).where(
        ServiceSession.owner_id == user.id,
        ServiceSession.status == "draft",
    )
    return await session.scalar(query) or 0


async def reset_user_data(session: AsyncSession, user: User) -> int:
    for row in await list_sessions(session, user, None):
        await notify("cancelled", row)
    result = await session.execute(delete(ServiceSession).where(ServiceSession.owner_id == user.id))
    await session.commit()
    return result.rowcount or 0


async def list_sessions(session: AsyncSession, user: User, status: str | None) -> list[ServiceSession]:
    query = select(ServiceSession).where(ServiceSession.owner_id == user.id)
    if status:
        query = query.where(ServiceSession.status == status)
    return list(await session.scalars(query.order_by(ServiceSession.updated_at.desc())))


async def start_session(session: AsyncSession, user: User, service_code: str) -> tuple[ServiceSession, bool]:
    definition = await catalog_service.load_definition(session, service_code)

    existing = await session.scalar(
        select(ServiceSession).where(
            ServiceSession.owner_id == user.id,
            ServiceSession.service_code == definition.code,
            ServiceSession.status == "draft",
        )
    )
    if existing is not None:
        return existing, False

    row = ServiceSession(
        owner_id=user.id,
        service_code=definition.code,
        service_version=definition.version,
        current_step_id=definition.steps[0].id,
        completed_step_ids=[],
        public_data={},
        last_errors={},
    )
    session.add(row)
    await session.commit()
    return row, True


async def update_fields(
    session: AsyncSession,
    user: User,
    session_id: UUID,
    raw_values: dict[str, Any],
    version: int | None,
) -> ServiceSession:
    row = await get_owned(session, user, session_id)
    require_draft(row)

    if version is not None and version != row.version:
        raise Conflict("version_conflict", "Заявление изменилось, обновите данные", {"version": row.version})

    definition = await definition_of(session, row)
    form = ApplicationForm(definition, read_values(row))

    try:
        type_errors = form.apply(raw_values)
    except ValueError as exc:
        raise Unprocessable("validation_error", str(exc)) from exc

    step = definition.step(row.current_step_id)
    touched = set(raw_values)
    step_errors = {
        error.element_id: error for error in form.validate_step(step) if error.element_id in touched
    }
    for error in type_errors:
        step_errors[error.element_id] = error

    visible = {element.id for element in form.visible_inputs(step)}
    kept = [
        error
        for error in row.last_errors.get(step.id, [])
        if error["element_id"] in visible
        and error["element_id"] not in touched
        and error["element_id"] not in step_errors
    ]
    row.last_errors = {
        **row.last_errors,
        step.id: kept + [error.as_dict() for error in step_errors.values()],
    }

    write_values(row, definition, form.values)
    row.version += 1
    row.updated_at = now()
    await session.commit()
    await notify("fields_updated", row, element_ids=list(raw_values))
    return row


async def navigate(
    session: AsyncSession,
    user: User,
    session_id: UUID,
    action: str,
    step_id: str | None,
) -> ServiceSession:
    row = await get_owned(session, user, session_id)
    require_draft(row)

    definition = await definition_of(session, row)
    form = ApplicationForm(definition, read_values(row))
    current = definition.step(row.current_step_id)

    if action == "next":
        errors = form.validate_step(current)
        if errors:
            row.last_errors = {**row.last_errors, current.id: [error.as_dict() for error in errors]}
            await session.commit()
            await notify("validation_failed", row, step_id=current.id)
            raise Unprocessable(
                "step_invalid",
                "Проверьте заполнение шага",
                {"step_id": current.id, "errors": [error.as_dict() for error in errors]},
            )

        target = definition.next_step(current.id)
        if target is None:
            raise Unprocessable("last_step", "Это последний шаг")

        row.last_errors = {**row.last_errors, current.id: []}
        if current.id not in row.completed_step_ids:
            row.completed_step_ids = [*row.completed_step_ids, current.id]

    elif action == "back":
        target = definition.previous_step(current.id)
        if target is None:
            raise Unprocessable("first_step", "Это первый шаг")

    elif action == "goto":
        if step_id is None:
            raise Unprocessable("validation_error", "Не указан шаг")
        target = definition.step(step_id)
        if target.id not in row.completed_step_ids and target.id != current.id:
            raise Unprocessable("step_locked", "Шаг ещё не пройден")

    else:
        raise Unprocessable("validation_error", "Неизвестное действие")

    row.current_step_id = target.id
    row.version += 1
    row.updated_at = now()
    await session.commit()
    await notify("step_changed", row, from_step_id=current.id)
    return row


def confirmation_step_id(definition: ServiceDefinition) -> str:
    for step in definition.steps:
        if any(element.type == "otp" for element in step.elements):
            return step.id
    raise NotFound("В услуге нет шага подтверждения")


async def issue_confirmation_code(
    session: AsyncSession,
    user: User,
    session_id: UUID,
) -> ServiceSession:
    row = await get_owned(session, user, session_id)
    require_draft(row)

    definition = await definition_of(session, row)
    if row.current_step_id != confirmation_step_id(definition):
        raise Unprocessable("wrong_step", "Код запрашивается на шаге подтверждения")

    if row.confirmation_expires_at is not None:
        issued_at = row.confirmation_expires_at - CODE_TTL
        if now() - issued_at < CODE_RESEND_DELAY:
            raise Unprocessable("code_resend_too_soon", "Код можно запросить чуть позже")

    code = f"{secrets.randbelow(10000):04d}"
    row.confirmation_code_hash = hashlib.sha256(code.encode()).hexdigest()
    row.confirmation_expires_at = now() + CODE_TTL
    row.confirmation_attempts = 0
    row.updated_at = now()

    session.add(
        ServiceSessionInbox(
            service_session_id=row.id,
            text=f"Госуслуги (демо): код подтверждения {code}. Никому не сообщайте этот код.",
        )
    )
    await session.commit()
    return row


async def list_inbox(session: AsyncSession, user: User, session_id: UUID) -> list[ServiceSessionInbox]:
    row = await get_owned(session, user, session_id)
    query = (
        select(ServiceSessionInbox)
        .where(ServiceSessionInbox.service_session_id == row.id)
        .order_by(ServiceSessionInbox.created_at.desc())
    )
    return list(await session.scalars(query))


async def submit(session: AsyncSession, user: User, session_id: UUID, code: str) -> ServiceSession:
    row = await get_owned(session, user, session_id)
    require_draft(row)

    definition = await definition_of(session, row)
    form = ApplicationForm(definition, read_values(row))

    errors_by_step = form.validate_all()
    if errors_by_step:
        row.last_errors = {
            step_id: [error.as_dict() for error in errors] for step_id, errors in errors_by_step.items()
        }
        await session.commit()
        step_id = next(iter(errors_by_step))
        await notify("validation_failed", row, step_id=step_id)
        raise Unprocessable(
            "step_invalid",
            "В заявлении есть незаполненные поля",
            {
                "step_id": step_id,
                "errors": [error.as_dict() for error in errors_by_step[step_id]],
            },
        )

    try:
        check_confirmation_code(row, code)
    except Unprocessable:
        await session.commit()
        raise

    row.status = "submitted"
    row.submitted_at = now()
    row.updated_at = now()
    row.application_number = await next_application_number(session)
    row.confirmation_code_hash = None
    row.confirmation_expires_at = None
    row.version += 1
    await session.commit()
    await notify("submitted", row)
    return row


def check_confirmation_code(row: ServiceSession, code: str) -> None:
    if row.confirmation_code_hash is None or row.confirmation_expires_at is None:
        raise Unprocessable("confirmation_code_invalid", "Запросите код подтверждения")

    if row.confirmation_expires_at < now():
        raise Unprocessable("confirmation_code_expired", "Срок действия кода истёк, запросите новый")

    if row.confirmation_attempts >= MAX_CODE_ATTEMPTS:
        raise Unprocessable("confirmation_attempts_exceeded", "Слишком много попыток, запросите новый код")

    if hashlib.sha256(code.encode()).hexdigest() != row.confirmation_code_hash:
        row.confirmation_attempts += 1
        raise Unprocessable(
            "confirmation_code_invalid",
            "Неверный код",
            {"attempts_left": MAX_CODE_ATTEMPTS - row.confirmation_attempts},
        )


async def next_application_number(session: AsyncSession) -> str:
    number = await session.scalar(text("select nextval('application_number_seq')"))
    return f"ЖКУ-{now().year}-{number:06d}"


async def cancel(session: AsyncSession, user: User, session_id: UUID) -> ServiceSession:
    row = await get_owned(session, user, session_id)
    require_draft(row)
    row.status = "cancelled"
    row.updated_at = now()
    row.version += 1
    await session.commit()
    await notify("cancelled", row)
    return row


def current_step_errors(row: ServiceSession) -> list[FieldError]:
    return [
        FieldError(error["element_id"], error["code"], error.get("details"))
        for error in row.last_errors.get(row.current_step_id, [])
    ]
