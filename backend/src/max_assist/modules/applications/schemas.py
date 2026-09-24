from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

from max_assist.modules.applications.models import ServiceSession, ServiceSessionInbox
from max_assist.modules.applications.service import current_step_errors, read_values
from max_assist.modules.catalog.schema import ServiceDefinition


class StartSessionRequest(BaseModel):
    service_code: str


class UpdateFieldsRequest(BaseModel):
    values: dict[str, Any]
    version: int | None = None


class NavigationRequest(BaseModel):
    action: Literal["next", "back", "goto"]
    step_id: str | None = None


class SubmitRequest(BaseModel):
    confirmation_code: str


class FieldErrorOut(BaseModel):
    element_id: str
    code: str
    message: str
    details: str | None = None


class StepRefOut(BaseModel):
    id: str
    index: int
    title: str
    status: Literal["completed", "current", "upcoming"]


class ServiceRefOut(BaseModel):
    code: str
    version: int
    title: str


class CurrentStepOut(BaseModel):
    id: str
    index: int
    title: str


class ServiceSessionOut(BaseModel):
    id: UUID
    service: ServiceRefOut
    status: str
    current_step: CurrentStepOut
    total_steps: int
    steps: list[StepRefOut]
    values: dict[str, Any]
    errors: list[FieldErrorOut]
    active_assist_session_id: UUID | None = None
    application_number: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None


class ConfirmationCodeOut(BaseModel):
    expires_at: datetime
    resend_available_at: datetime


class SubmitOut(BaseModel):
    status: str
    application_number: str
    submitted_at: datetime


class InboxMessageOut(BaseModel):
    id: UUID
    text: str
    created_at: datetime

    @classmethod
    def of(cls, row: ServiceSessionInbox) -> "InboxMessageOut":
        return cls(id=row.id, text=row.text, created_at=row.created_at)


def session_out(row: ServiceSession, definition: ServiceDefinition) -> ServiceSessionOut:
    steps = []
    for index, step in enumerate(definition.steps, start=1):
        if step.id == row.current_step_id:
            status = "current"
        elif step.id in row.completed_step_ids:
            status = "completed"
        else:
            status = "upcoming"
        steps.append(StepRefOut(id=step.id, index=index, title=step.title, status=status))

    current = definition.step(row.current_step_id)
    return ServiceSessionOut(
        id=row.id,
        service=ServiceRefOut(code=definition.code, version=definition.version, title=definition.title),
        status=row.status,
        current_step=CurrentStepOut(
            id=current.id,
            index=definition.step_index(current.id),
            title=current.title,
        ),
        total_steps=definition.total_steps,
        steps=steps,
        values=read_values(row),
        errors=[FieldErrorOut(**error.as_dict()) for error in current_step_errors(row)],
        application_number=row.application_number,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        submitted_at=row.submitted_at,
    )
