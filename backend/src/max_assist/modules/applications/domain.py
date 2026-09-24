import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from max_assist.modules.catalog.schema import Element, Rule, ServiceDefinition, Step

MESSAGES = {
    "required": "Заполните поле",
    "invalid_format": "Неверный формат",
    "out_of_range": "Значение вне допустимого диапазона",
    "must_be_checked": "Необходимо согласие",
}


@dataclass(slots=True)
class FieldError:
    element_id: str
    code: str
    details: str | None = None

    @property
    def message(self) -> str:
        return MESSAGES[self.code]

    def as_dict(self) -> dict[str, Any]:
        return {
            "element_id": self.element_id,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


def coerce(element: Element, raw: Any) -> Any:
    if raw is None or raw == "":
        return None

    if element.type == "number":
        number = float(raw)
        return int(number) if number.is_integer() else number

    if element.type == "checkbox":
        if isinstance(raw, bool):
            return raw
        raise ValueError("ожидается да или нет")

    if element.type == "date":
        date.fromisoformat(str(raw))
        return str(raw)

    if element.type in {"select", "radio"}:
        allowed = {option.value for option in element.options or []}
        if str(raw) not in allowed:
            raise ValueError("недопустимый вариант")
        return str(raw)

    return str(raw).strip() or None


class ApplicationForm:
    def __init__(self, definition: ServiceDefinition, values: dict[str, Any]) -> None:
        self.definition = definition
        self.values = dict(values)

    def is_visible(self, element: Element) -> bool:
        condition = element.visible_if
        if condition is None:
            return True

        current = self.values.get(condition.element)
        if condition.values is not None:
            return current in condition.values
        return current == condition.equals

    def is_stored(self, element: Element) -> bool:
        # код из SMS в заявлении не хранится, он проверяется при отправке
        return element.is_input and element.type != "otp"

    def visible_inputs(self, step: Step) -> list[Element]:
        return [element for element in step.elements if self.is_stored(element) and self.is_visible(element)]

    def apply(self, raw_values: dict[str, Any]) -> list[FieldError]:
        errors = []
        for element_id, raw in raw_values.items():
            element = self.definition.element(element_id)
            if not self.is_stored(element):
                raise ValueError(f"элемент {element_id} нельзя заполнять")
            try:
                self.values[element_id] = coerce(element, raw)
            except ValueError:
                errors.append(FieldError(element_id, "invalid_format", first_details(element)))
        return errors

    def validate_step(self, step: Step) -> list[FieldError]:
        errors = []
        for element in self.visible_inputs(step):
            value = self.values.get(element.id)
            if value is None:
                if element.required:
                    errors.append(FieldError(element.id, "required"))
                continue
            errors.extend(self._check_rules(element, value))
        return errors

    def validate_all(self) -> dict[str, list[FieldError]]:
        result = {}
        for step in self.definition.steps:
            errors = self.validate_step(step)
            if errors:
                result[step.id] = errors
        return result

    def state_of(self, element_id: str) -> str:
        return "filled" if self.values.get(element_id) is not None else "empty"

    def _check_rules(self, element: Element, value: Any) -> list[FieldError]:
        errors = []
        for rule in element.validation:
            error = self._check_rule(element, rule, value)
            if error is not None:
                errors.append(error)
        return errors

    def _check_rule(self, element: Element, rule: Rule, value: Any) -> FieldError | None:
        if rule.rule == "pattern":
            if rule.regex and not re.fullmatch(rule.regex, str(value)):
                return FieldError(element.id, "invalid_format", rule.details)

        elif rule.rule == "length":
            length = len(str(value))
            if (rule.min is not None and length < rule.min) or (rule.max is not None and length > rule.max):
                return FieldError(element.id, "invalid_format", rule.details)

        elif rule.rule == "range":
            if (rule.min is not None and value < rule.min) or (rule.max is not None and value > rule.max):
                return FieldError(element.id, "out_of_range", rule.details)

        elif rule.rule == "must_be_checked":
            if value is not True:
                return FieldError(element.id, "must_be_checked", rule.details)

        elif rule.rule == "date_past":
            if date.fromisoformat(str(value)) >= date.today():
                return FieldError(element.id, "out_of_range", rule.details or "Дата должна быть в прошлом")

        return None


def first_details(element: Element) -> str | None:
    for rule in element.validation:
        if rule.details:
            return rule.details
    return None


def split_by_privacy(
    definition: ServiceDefinition,
    values: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    public: dict[str, Any] = {}
    sensitive: dict[str, Any] = {}
    for element_id, value in values.items():
        if value is None:
            continue
        element = definition.element(element_id)
        target = public if element.privacy == "public" else sensitive
        target[element_id] = value
    return public, sensitive
