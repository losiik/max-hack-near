import json
from pathlib import Path

import pytest

from max_assist.modules.catalog.schema import ServiceDefinition
from tests.helpers import login

DATA = Path(__file__).resolve().parents[1] / "migrations" / "data"


def demo() -> ServiceDefinition:
    raw = json.loads((DATA / "housing_compensation_v1.json").read_text("utf-8"))
    return ServiceDefinition.model_validate(raw)


def broken(elements: list[dict], second_step: list[dict] | None = None) -> dict:
    steps = [{"id": "one", "title": "Шаг", "elements": elements}]
    if second_step is not None:
        steps.append({"id": "two", "title": "Шаг 2", "elements": second_step})
    return {
        "code": "demo",
        "version": 1,
        "title": "Демо",
        "short_description": "Демо",
        "estimated_minutes": 1,
        "steps": steps,
    }


def test_demo_service_is_valid():
    definition = demo()

    assert definition.total_steps == 7
    assert definition.element("snils").privacy == "owner_only"
    assert definition.element("address").role_overrides == {"government_operator": "public"}
    assert definition.step_of("account_number").id == "payment"
    assert definition.step_index("family") == 3
    assert definition.next_step("family").id == "income"
    assert definition.previous_step("family").id == "address"
    assert definition.next_step("confirmation") is None
    assert definition.previous_step("category") is None


def test_unknown_step_and_element_are_reported():
    definition = demo()

    with pytest.raises(Exception, match="не найден"):
        definition.step("nope")
    with pytest.raises(Exception, match="не найден"):
        definition.element("nope")
    with pytest.raises(Exception, match="не найден"):
        definition.step_of("nope")


def test_duplicate_element_id_across_steps_is_rejected():
    raw = broken(
        [{"id": "name", "type": "text", "label": "Имя", "privacy": "public"}],
        [{"id": "name", "type": "text", "label": "Имя", "privacy": "masked"}],
    )

    with pytest.raises(ValueError, match="дублируется"):
        ServiceDefinition.model_validate(raw)


def test_input_without_privacy_is_rejected():
    raw = broken([{"id": "name", "type": "text", "label": "Имя"}])

    with pytest.raises(ValueError, match="приватность"):
        ServiceDefinition.model_validate(raw)


def test_sms_code_must_be_owner_only():
    raw = broken([{"id": "code", "type": "otp", "label": "Код", "privacy": "masked"}])

    with pytest.raises(ValueError, match="owner_only"):
        ServiceDefinition.model_validate(raw)


def test_action_without_policy_is_rejected():
    raw = broken([{"id": "send", "type": "action", "label": "Отправить"}])

    with pytest.raises(ValueError, match="политика действия"):
        ServiceDefinition.model_validate(raw)


def test_select_without_options_is_rejected():
    raw = broken([{"id": "kind", "type": "select", "label": "Вид", "privacy": "public"}])

    with pytest.raises(ValueError, match="вариантов выбора"):
        ServiceDefinition.model_validate(raw)


def test_visible_if_must_point_to_existing_public_element():
    unknown = broken(
        [
            {
                "id": "extra",
                "type": "text",
                "label": "Ещё",
                "privacy": "public",
                "visible_if": {"element": "nope", "equals": "yes"},
            }
        ]
    )
    with pytest.raises(ValueError, match="неизвестный элемент"):
        ServiceDefinition.model_validate(unknown)

    private = broken(
        [
            {"id": "secret", "type": "text", "label": "Тайна", "privacy": "owner_only"},
            {
                "id": "extra",
                "type": "text",
                "label": "Ещё",
                "privacy": "public",
                "visible_if": {"element": "secret", "equals": "yes"},
            },
        ]
    )
    with pytest.raises(ValueError, match="public-элемент"):
        ServiceDefinition.model_validate(private)


async def test_service_list_and_definition(client):
    headers = await login(client)

    listed = await client.get("/api/v1/services", headers=headers)
    definition = await client.get("/api/v1/services/housing_compensation", headers=headers)

    assert [item["code"] for item in listed.json()] == ["housing_compensation"]
    assert listed.json()[0]["steps_count"] == 7
    assert definition.status_code == 200
    assert "operator_hint" not in json.dumps(definition.json(), ensure_ascii=False)


async def test_unknown_service_is_not_found(client):
    headers = await login(client)

    response = await client.get("/api/v1/services/unknown_service", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
