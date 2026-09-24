from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.deps import CurrentUser, DbSession
from max_assist.modules.applications import service
from max_assist.modules.applications.models import ServiceSession
from max_assist.modules.applications.schemas import (
    ConfirmationCodeOut,
    InboxMessageOut,
    NavigationRequest,
    ServiceSessionOut,
    StartSessionRequest,
    SubmitOut,
    SubmitRequest,
    UpdateFieldsRequest,
    session_out,
)
from max_assist.modules.applications.service import CODE_RESEND_DELAY, CODE_TTL

router = APIRouter(prefix="/service-sessions", tags=["applications"])


async def respond(session: AsyncSession, row: ServiceSession) -> ServiceSessionOut:
    definition = await service.definition_of(session, row)
    return session_out(row, definition, await service.active_assist_id(session, row))


@router.post("", response_model=ServiceSessionOut)
async def start_session(
    payload: StartSessionRequest,
    user: CurrentUser,
    session: DbSession,
    response: Response,
) -> ServiceSessionOut:
    row, created = await service.start_session(session, user, payload.service_code)
    response.status_code = 201 if created else 200
    return await respond(session, row)


@router.get("", response_model=list[ServiceSessionOut])
async def list_sessions(
    user: CurrentUser,
    session: DbSession,
    status: str | None = None,
) -> list[ServiceSessionOut]:
    rows = await service.list_sessions(session, user, status)
    return [await respond(session, row) for row in rows]


@router.get("/{session_id}", response_model=ServiceSessionOut)
async def get_session(session_id: UUID, user: CurrentUser, session: DbSession) -> ServiceSessionOut:
    row = await service.get_owned(session, user, session_id)
    return await respond(session, row)


@router.patch("/{session_id}/fields", response_model=ServiceSessionOut)
async def update_fields(
    session_id: UUID,
    payload: UpdateFieldsRequest,
    user: CurrentUser,
    session: DbSession,
) -> ServiceSessionOut:
    row = await service.update_fields(session, user, session_id, payload.values, payload.version)
    return await respond(session, row)


@router.post("/{session_id}/navigation", response_model=ServiceSessionOut)
async def navigate(
    session_id: UUID,
    payload: NavigationRequest,
    user: CurrentUser,
    session: DbSession,
) -> ServiceSessionOut:
    row = await service.navigate(session, user, session_id, payload.action, payload.step_id)
    return await respond(session, row)


@router.post("/{session_id}/confirmation-code", response_model=ConfirmationCodeOut)
async def issue_confirmation_code(
    session_id: UUID,
    user: CurrentUser,
    session: DbSession,
) -> ConfirmationCodeOut:
    row = await service.issue_confirmation_code(session, user, session_id)
    return ConfirmationCodeOut(
        expires_at=row.confirmation_expires_at,
        resend_available_at=row.confirmation_expires_at - CODE_TTL + CODE_RESEND_DELAY,
    )


@router.get("/{session_id}/demo-inbox", response_model=list[InboxMessageOut])
async def demo_inbox(session_id: UUID, user: CurrentUser, session: DbSession) -> list[InboxMessageOut]:
    rows = await service.list_inbox(session, user, session_id)
    return [InboxMessageOut.of(row) for row in rows]


@router.post("/{session_id}/submit", response_model=SubmitOut)
async def submit(
    session_id: UUID,
    payload: SubmitRequest,
    user: CurrentUser,
    session: DbSession,
) -> SubmitOut:
    row = await service.submit(session, user, session_id, payload.confirmation_code)
    return SubmitOut(
        status=row.status,
        application_number=row.application_number,
        submitted_at=row.submitted_at,
    )


@router.post("/{session_id}/cancel", response_model=ServiceSessionOut)
async def cancel(session_id: UUID, user: CurrentUser, session: DbSession) -> ServiceSessionOut:
    row = await service.cancel(session, user, session_id)
    return await respond(session, row)
