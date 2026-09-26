from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from max_assist.deps import Caller, CurrentUser, DbSession
from max_assist.modules.applications import service as applications_service
from max_assist.modules.assist.models import AssistSession
from max_assist.modules.assist.schemas import AssistSessionOut, session_view
from max_assist.modules.identity.models import User
from max_assist.modules.support_desk import queries, service
from max_assist.modules.support_desk.models import OperatorRequest
from max_assist.security import AgentPass
from max_assist.utils import now

router = APIRouter(tags=["support_desk"])

Topic = Literal["dont_understand", "form_error", "other"]


class OperatorRequestIn(BaseModel):
    topic: Topic
    # резюме передаёт только цифровой сотрудник
    summary: str | None = Field(None, max_length=500)


class OperatorRequestOut(BaseModel):
    id: UUID
    status: str
    topic: str
    position: int | None


class RequestedSessionOut(BaseModel):
    assist_session: AssistSessionOut
    request: OperatorRequestOut


class QueueStepOut(BaseModel):
    index: int
    total: int
    title: str


class QueueContextOut(BaseModel):
    owner_display_name: str
    service_title: str
    step: QueueStepOut | None
    error_codes: list[str]
    ai_summary: str | None


class QueueItemOut(BaseModel):
    id: UUID
    status: str
    source: str
    topic: str
    created_at: datetime
    waiting_sec: int
    context: QueueContextOut


class ClaimOut(BaseModel):
    assist_session_id: UUID
    participant_id: UUID


async def request_view(db: AsyncSession, assist_id: UUID) -> OperatorRequestOut:
    return OperatorRequestOut(**await queries.current(db, assist_id))


async def queue_item(db: AsyncSession, request: OperatorRequest) -> QueueItemOut:
    assist = await db.get(AssistSession, request.assist_session_id)
    owner = await db.get(User, assist.owner_id)
    step = None
    error_codes: list[str] = []
    title = assist.service_code
    if assist.service_session_id is not None:
        application = await applications_service.get_by_id(db, assist.service_session_id)
        definition = await applications_service.definition_of(db, application)
        current = definition.step(application.current_step_id)
        title = definition.title
        step = QueueStepOut(
            index=definition.step_index(current.id),
            total=definition.total_steps,
            title=current.title,
        )
        # сотруднику нужны только коды ошибок, значения полей сюда не попадают
        error_codes = [item["code"] for item in application.last_errors.get(current.id, [])]

    return QueueItemOut(
        id=request.id,
        status=request.status,
        source=request.source,
        topic=request.topic,
        created_at=request.created_at,
        waiting_sec=int((now() - request.created_at).total_seconds()),
        context=QueueContextOut(
            owner_display_name=owner.display_name,
            service_title=title,
            step=step,
            error_codes=error_codes,
            ai_summary=request.context.get("ai_summary"),
        ),
    )


@router.post(
    "/assist-sessions/{assist_id}/operator-requests", response_model=OperatorRequestOut, status_code=201
)
async def request_operator(
    assist_id: UUID,
    payload: OperatorRequestIn,
    caller: Caller,
    db: DbSession,
) -> OperatorRequestOut:
    if isinstance(caller, AgentPass):
        await service.request_by_agent(db, caller, assist_id, payload.topic, payload.summary)
    else:
        await service.request_operator(db, caller, assist_id, payload.topic)
    return await request_view(db, assist_id)


@router.post(
    "/service-sessions/{service_session_id}/operator-requests",
    response_model=RequestedSessionOut,
    status_code=201,
)
async def request_operator_for_application(
    service_session_id: UUID,
    payload: OperatorRequestIn,
    user: CurrentUser,
    db: DbSession,
) -> RequestedSessionOut:
    assist, _ = await service.request_from_application(db, user, service_session_id, payload.topic)
    return RequestedSessionOut(
        assist_session=await session_view(db, assist, user.id),
        request=await request_view(db, assist.id),
    )


@router.delete("/assist-sessions/{assist_id}/operator-requests/current", status_code=204)
async def cancel_request(assist_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.cancel(db, user, assist_id)
    return Response(status_code=204)


@router.get("/operator/requests", response_model=list[QueueItemOut])
async def operator_queue(user: CurrentUser, db: DbSession) -> list[QueueItemOut]:
    service.require_staff(user)
    return [await queue_item(db, request) for request in await queries.queue(db)]


@router.post("/operator/requests/{request_id}/claim", response_model=ClaimOut)
async def claim(request_id: UUID, user: CurrentUser, db: DbSession) -> ClaimOut:
    assist, participant_id = await service.claim(db, user, request_id)
    return ClaimOut(assist_session_id=assist.id, participant_id=participant_id)


@router.post("/operator/requests/{request_id}/complete", status_code=204)
async def complete(request_id: UUID, user: CurrentUser, db: DbSession) -> Response:
    await service.complete(db, user, request_id)
    return Response(status_code=204)
