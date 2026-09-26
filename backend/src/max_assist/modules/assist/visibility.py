from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from max_assist.modules.applications.domain import ApplicationForm
from max_assist.modules.assist.domain import capabilities_of
from max_assist.modules.catalog.schema import Element, Option, ServiceDefinition, Step


@dataclass
class ApplicationSnapshot:
    values: dict[str, Any]
    current_step_id: str
    completed_step_ids: list[str]
    errors: list[dict[str, Any]]
    status: str


class ValueView(BaseModel):
    state: Literal["filled", "empty", "hidden"]
    value: Any = None
    locked: bool = False


class ActionView(BaseModel):
    label: str
    available: bool
    reason: str | None = None


class SummaryRow(BaseModel):
    element_id: str
    step_id: str
    label: str
    view: ValueView


class ElementView(BaseModel):
    id: str
    type: str
    label: str | None
    hint: str | None
    placeholder: str | None
    unit: str | None
    text: str | None
    style: str | None
    required: bool
    privacy: str | None
    options: list[Option] | None
    view: ValueView | None
    rows: list[SummaryRow] | None
    action: ActionView | None
    operator_hint: str | None


class StepView(BaseModel):
    id: str
    index: int
    title: str
    status: Literal["completed", "current", "upcoming"]


class CurrentStepView(BaseModel):
    id: str
    index: int
    title: str
    description: str | None
    operator_hint: str | None
    elements: list[ElementView]


class ErrorView(BaseModel):
    element_id: str
    code: str
    message: str
    details: str | None


class ServiceView(BaseModel):
    code: str
    version: int
    title: str
    total_steps: int


class ProjectedState(BaseModel):
    service: ServiceView
    steps: list[StepView]
    current_step: CurrentStepView
    errors: list[ErrorView]
    service_session_status: str


def effective_privacy(element: Element, role: str) -> str | None:
    if element.privacy is None:
        return None
    return element.role_overrides.get(role, element.privacy)


def value_view(
    element: Element,
    values: dict[str, Any],
    role: str,
    capabilities: frozenset[str],
) -> ValueView:
    value = values.get(element.id)
    state = "filled" if value is not None else "empty"
    if "view_sensitive_values" in capabilities:
        return ValueView(state=state, value=value)

    privacy = effective_privacy(element, role)
    if privacy == "public":
        return ValueView(state=state, value=value)
    if privacy == "masked":
        return ValueView(state=state)
    return ValueView(state="hidden", locked=True)


def summary_rows(
    definition: ServiceDefinition,
    step: Step,
    form: ApplicationForm,
    role: str,
    capabilities: frozenset[str],
) -> list[SummaryRow]:
    rows = []
    for other in definition.steps:
        if other.id == step.id:
            break
        for element in other.elements:
            if form.is_stored(element) and form.is_visible(element):
                rows.append(
                    SummaryRow(
                        element_id=element.id,
                        step_id=other.id,
                        label=element.label or element.id,
                        view=value_view(element, form.values, role, capabilities),
                    )
                )
    return rows


def element_view(
    definition: ServiceDefinition,
    step: Step,
    element: Element,
    form: ApplicationForm,
    role: str,
    capabilities: frozenset[str],
) -> ElementView:
    view = None
    rows = None
    action = None

    if element.is_input:
        view = value_view(element, form.values, role, capabilities)
    elif element.type == "summary":
        rows = summary_rows(definition, step, form, role, capabilities)
    elif element.type == "action":
        available = element.action_policy != "owner_only" or "submit" in capabilities
        action = ActionView(
            label=element.label or "",
            available=available,
            reason=None if available else "owner_only",
        )

    sees_everything = "view_sensitive_values" in capabilities
    privacy = element.privacy if sees_everything else effective_privacy(element, role)
    return ElementView(
        id=element.id,
        type=element.type,
        label=element.label,
        hint=element.hint,
        placeholder=element.placeholder,
        unit=element.unit,
        text=element.text,
        style=element.style,
        required=element.required,
        privacy=privacy,
        options=element.options if sees_everything or privacy == "public" else None,
        view=view,
        rows=rows,
        action=action,
        operator_hint=element.operator_hint if "view_operator_hints" in capabilities else None,
    )


def step_views(definition: ServiceDefinition, snapshot: ApplicationSnapshot) -> list[StepView]:
    views = []
    for index, step in enumerate(definition.steps, start=1):
        if step.id == snapshot.current_step_id:
            status = "current"
        elif step.id in snapshot.completed_step_ids:
            status = "completed"
        else:
            status = "upcoming"
        views.append(StepView(id=step.id, index=index, title=step.title, status=status))
    return views


def project(definition: ServiceDefinition, snapshot: ApplicationSnapshot, role: str) -> ProjectedState:
    capabilities = capabilities_of(role)
    form = ApplicationForm(definition, snapshot.values)
    step = definition.step(snapshot.current_step_id)

    elements = [
        element_view(definition, step, element, form, role, capabilities)
        for element in step.elements
        if form.is_visible(element)
    ]
    visible_ids = {element.id for element in elements}
    shows_details = "view_validation_details" in capabilities

    return ProjectedState(
        service=ServiceView(
            code=definition.code,
            version=definition.version,
            title=definition.title,
            total_steps=definition.total_steps,
        ),
        steps=step_views(definition, snapshot),
        current_step=CurrentStepView(
            id=step.id,
            index=definition.step_index(step.id),
            title=step.title,
            description=step.description,
            operator_hint=step.operator_hint if "view_operator_hints" in capabilities else None,
            elements=elements,
        ),
        errors=[
            ErrorView(
                element_id=error["element_id"],
                code=error["code"],
                message=error["message"],
                details=error.get("details") if shows_details else None,
            )
            for error in snapshot.errors
            if error["element_id"] in visible_ids
        ],
        service_session_status=snapshot.status,
    )
