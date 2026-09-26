from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from max_assist.deps import Caller, CurrentAgent, CurrentUser, DbSession
from max_assist.modules.ai_assistant import service
from max_assist.modules.assist.schemas import AssistSessionOut, session_view

router = APIRouter(tags=["ai_assistant"])


class CalledOut(BaseModel):
    assist_session: AssistSessionOut


class ToolUseIn(BaseModel):
    name: Literal["highlight", "point", "call_operator"]
    element_id: str | None = Field(None, max_length=100)


class TurnIn(BaseModel):
    trigger: Literal["greeting", "question", "validation_failed", "confusion", "step_changed"]
    # вопроса человека тут нет: храним только то, что сказал агент
    reply_text: str = Field(max_length=1000)
    tools: list[ToolUseIn] = Field(default_factory=list, max_length=10)
    guard_result: Literal["passed", "rejected"]
    latency_ms: int = Field(ge=0, le=600_000)
    provider: str = Field(max_length=100)


class TurnOut(BaseModel):
    id: UUID


@router.post("/service-sessions/{service_session_id}/ai-agent", response_model=CalledOut, status_code=201)
async def call_to_application(service_session_id: UUID, user: CurrentUser, db: DbSession) -> CalledOut:
    assist = await service.call_to_application(db, user, service_session_id)
    return CalledOut(assist_session=await session_view(db, assist, user.id))


@router.post("/assist-sessions/{assist_id}/ai-agent", response_model=AssistSessionOut, status_code=201)
async def call_to_session(assist_id: UUID, user: CurrentUser, db: DbSession) -> AssistSessionOut:
    assist = await service.call_to_session(db, user, assist_id)
    return await session_view(db, assist, user.id)


@router.delete("/assist-sessions/{assist_id}/ai-agent", status_code=204)
async def release(assist_id: UUID, caller: Caller, db: DbSession) -> Response:
    await service.release(db, caller, assist_id)
    return Response(status_code=204)


@router.post("/ai-turns", response_model=TurnOut, status_code=201)
async def record_turn(payload: TurnIn, agent: CurrentAgent, db: DbSession) -> TurnOut:
    row = await service.record_turn(db, agent, payload.model_dump(mode="json"))
    return TurnOut(id=row.id)
