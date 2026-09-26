from typing import Any

HUMAN_ROLES = {"trusted_helper", "invited_helper", "government_operator"}

STATES = {"filled": "заполнено", "empty": "не заполнено", "hidden": "скрыто от вас"}


class FormState:
    # то, что агент знает о форме: только проекция роли ai_agent, личных значений в ней нет
    def __init__(self) -> None:
        self.service_title = ""
        self.total_steps = 0
        self.step: dict[str, Any] = {"id": "", "index": 0, "title": "", "elements": []}
        self.errors: list[dict[str, Any]] = []
        self.owner_name = ""

    def load(self, snapshot: dict[str, Any]) -> None:
        self.service_title = snapshot["service"]["title"]
        self.total_steps = snapshot["service"]["total_steps"]
        self.owner_name = snapshot["session"]["owner"]["display_name"]
        self.step = snapshot["current_step"]
        self.errors = snapshot["errors"]

    def apply(self, event: str, payload: dict[str, Any]) -> None:
        if event in ("navigation.step_changed", "form.field_updated"):
            self.step = payload["current_step"]
            self.errors = payload["errors"]
        elif event == "form.validation_failed" and payload["step_id"] == self.step["id"]:
            self.errors = payload["errors"]

    def element_ids(self) -> set[str]:
        return {item["id"] for item in self.step["elements"]}

    def label(self, element_id: str | None) -> str:
        for item in self.step["elements"]:
            if item["id"] == element_id:
                return item.get("label") or element_id
        return element_id or ""

    def public_texts(self) -> list[str]:
        texts = [self.step.get("description") or ""]
        for item in self.step["elements"]:
            texts += [item.get(key) or "" for key in ("label", "hint", "placeholder", "text")]
            texts += [option["label"] for option in item.get("options") or []]
        return texts

    def describe(self) -> str:
        lines = [
            f"Услуга: «{self.service_title}».",
            # в имени для показа есть инициал фамилии, а обращаться лучше просто по имени
            f"Человека зовут {self.owner_name.split()[0]}" if self.owner_name else "",
            f"Сейчас шаг {self.step['index']} из {self.total_steps}: «{self.step['title']}».",
        ]
        if self.step.get("description"):
            lines.append(self.step["description"])
        if self.step.get("operator_hint"):
            lines.append(f"Подсказка специалиста к шагу: {self.step['operator_hint']}")

        lines.append("Поля на экране:")
        for item in self.step["elements"]:
            lines.append(describe_element(item))

        if self.errors:
            lines.append("Ошибки, которые видит человек:")
            for error in self.errors:
                lines.append(f"- «{self.label(error['element_id'])}»: {error['message']}")
        return "\n".join(line for line in lines if line)


def describe_element(item: dict[str, Any]) -> str:
    if item["type"] == "action":
        return f"- кнопка «{item.get('label')}» — нажимает только сам человек"
    if item["type"] == "summary":
        return "- сводка всех ответов перед отправкой"
    if item.get("view") is None:
        return f"- надпись: {item.get('text') or item.get('label') or ''}".rstrip()

    view = item["view"]
    parts = [f"- `{item['id']}` «{item.get('label')}»", STATES[view["state"]]]
    if item.get("options"):
        choices = "; ".join(option["label"] for option in item["options"])
        parts.append(f"варианты: {choices}")
        chosen = next((o["label"] for o in item["options"] if o["value"] == view.get("value")), None)
        if chosen:
            parts.append(f"выбрано: {chosen}")
    elif view.get("value") is not None:
        parts.append(f"значение: {view['value']}")
    if item.get("hint"):
        parts.append(f"подсказка на экране: {item['hint']}")
    if item.get("placeholder"):
        parts.append(f"формат: {item['placeholder']}")
    if item.get("operator_hint"):
        parts.append(f"для специалиста: {item['operator_hint']}")
    return ", ".join(parts)
