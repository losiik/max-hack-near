from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from max_assist.errors import NotFound

Privacy = Literal["public", "masked", "owner_only"]
ElementType = Literal[
    "text",
    "number",
    "date",
    "select",
    "radio",
    "checkbox",
    "otp",
    "info",
    "summary",
    "action",
]

INPUT_TYPES = {"text", "number", "date", "select", "radio", "checkbox", "otp"}


class Option(BaseModel):
    value: str
    label: str


class Rule(BaseModel):
    rule: Literal["pattern", "length", "range", "must_be_checked", "date_past"]
    regex: str | None = None
    min: float | None = None
    max: float | None = None
    details: str | None = None


class VisibleIf(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    element: str
    equals: Any = None
    values: list[Any] | None = Field(default=None, alias="in")


class Element(BaseModel):
    id: str
    type: ElementType
    label: str | None = None
    hint: str | None = None
    placeholder: str | None = None
    unit: str | None = None
    text: str | None = None
    style: str | None = None
    required: bool = False
    privacy: Privacy | None = None
    role_overrides: dict[str, Privacy] = Field(default_factory=dict)
    options: list[Option] | None = None
    validation: list[Rule] = Field(default_factory=list)
    visible_if: VisibleIf | None = None
    action_policy: Literal["owner_only"] | None = None
    operator_hint: str | None = None

    @property
    def is_input(self) -> bool:
        return self.type in INPUT_TYPES


class Step(BaseModel):
    id: str
    title: str
    description: str | None = None
    operator_hint: str | None = None
    elements: list[Element]


class ServiceDefinition(BaseModel):
    code: str
    version: int
    title: str
    short_description: str
    estimated_minutes: int
    disclaimer: str | None = None
    steps: list[Step]

    @model_validator(mode="after")
    def check_elements(self) -> "ServiceDefinition":
        elements: dict[str, Element] = {}
        for step in self.steps:
            for element in step.elements:
                if element.id in elements:
                    raise ValueError(f"дублируется id элемента: {element.id}")
                elements[element.id] = element

        for element in elements.values():
            if element.is_input and element.privacy is None:
                raise ValueError(f"не указана приватность: {element.id}")
            if element.type == "otp" and element.privacy != "owner_only":
                raise ValueError(f"код подтверждения должен быть owner_only: {element.id}")
            if element.type == "action" and element.action_policy is None:
                raise ValueError(f"не указана политика действия: {element.id}")
            if element.type in {"select", "radio"} and not element.options:
                raise ValueError(f"нет вариантов выбора: {element.id}")
            if element.visible_if is not None:
                target = elements.get(element.visible_if.element)
                if target is None:
                    raise ValueError(f"условие показа ссылается на неизвестный элемент: {element.id}")
                if target.privacy != "public":
                    raise ValueError(f"условие показа должно ссылаться на public-элемент: {element.id}")

        return self

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    def step(self, step_id: str) -> Step:
        for step in self.steps:
            if step.id == step_id:
                return step
        raise NotFound(f"Шаг {step_id} не найден")

    def step_index(self, step_id: str) -> int:
        return next(index for index, step in enumerate(self.steps, start=1) if step.id == step_id)

    def next_step(self, step_id: str) -> Step | None:
        index = self.step_index(step_id)
        return self.steps[index] if index < self.total_steps else None

    def previous_step(self, step_id: str) -> Step | None:
        index = self.step_index(step_id)
        return self.steps[index - 2] if index > 1 else None

    def element(self, element_id: str) -> Element:
        for step in self.steps:
            for element in step.elements:
                if element.id == element_id:
                    return element
        raise NotFound(f"Элемент {element_id} не найден")

    def step_of(self, element_id: str) -> Step:
        for step in self.steps:
            if any(element.id == element_id for element in step.elements):
                return step
        raise NotFound(f"Элемент {element_id} не найден")

    def public_dict(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude={"steps": {"__all__": {"elements": {"__all__": {"operator_hint"}}}}},
        )
