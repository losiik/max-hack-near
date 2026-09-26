import json
from pathlib import Path

from max_assist.modules.assist.visibility import ApplicationSnapshot, project
from max_assist.modules.catalog.schema import ServiceDefinition

DATA = Path(__file__).resolve().parents[1] / "migrations" / "data"

VALUES = {
    "benefit_category": "pensioner",
    "benefit_reason": "certificate",
    "region": "spb",
    "address": "Невский проспект, 1",
    "ownership_type": "owner",
    "living_area": 54.5,
    "full_name": "Петрова Людмила Ивановна",
    "birth_date": "1956-03-12",
    "snils": "123-456-789 00",
    "family_size": 2,
    "income_type": "pension",
    "monthly_income": 18400,
    "payment_method": "bank",
    "bank_bik": "044030653",
    "account_number": "40817810099910004312",
}


def definition() -> ServiceDefinition:
    return ServiceDefinition.model_validate(
        json.loads((DATA / "housing_compensation_v1.json").read_text("utf-8"))
    )


def state(step_id, role, values=None, errors=None):
    service = definition()
    ids = [step.id for step in service.steps]
    snapshot = ApplicationSnapshot(
        values=VALUES if values is None else values,
        current_step_id=step_id,
        completed_step_ids=ids[: ids.index(step_id)],
        errors=errors or [],
        status="draft",
    )
    return project(service, snapshot, role)


def element(projected, element_id):
    return next(item for item in projected.current_step.elements if item.id == element_id)


def test_owner_sees_every_value():
    snils = element(state("family", "owner"), "snils")

    assert snils.view.model_dump() == {"state": "filled", "value": "123-456-789 00", "locked": False}
    assert snils.privacy == "owner_only"


def test_helper_sees_public_values_and_only_state_of_the_rest():
    family = state("family", "invited_helper")

    assert element(family, "family_size").view.value == 2
    assert element(family, "full_name").view.model_dump() == {
        "state": "filled",
        "value": None,
        "locked": False,
    }
    assert element(family, "snils").view.model_dump() == {"state": "hidden", "value": None, "locked": True}
    assert element(family, "has_disabled_members").view.state == "empty"


def test_helper_does_not_receive_private_select_options():
    service = definition()
    region = next(item for step in service.steps for item in step.elements if item.id == "region")
    region.privacy = "owner_only"
    steps = [step.id for step in service.steps]
    snapshot = ApplicationSnapshot(
        values=VALUES,
        current_step_id="address",
        completed_step_ids=steps[: steps.index("address")],
        errors=[],
        status="draft",
    )

    projected = project(service, snapshot, "invited_helper")

    assert element(projected, "region").options is None


def test_owner_only_field_does_not_reveal_whether_it_is_filled():
    empty = state("family", "trusted_helper", values={})
    filled = state("family", "trusted_helper")

    assert element(empty, "full_name").view.state == "empty"
    assert element(empty, "snils").view == element(filled, "snils").view


def test_operator_sees_address_and_helper_does_not():
    operator = element(state("address", "government_operator"), "address")
    helper = element(state("address", "invited_helper"), "address")

    assert (operator.privacy, operator.view.value) == ("public", "Невский проспект, 1")
    assert (helper.privacy, helper.view.value) == ("masked", None)


def test_fields_hidden_by_condition_are_left_out_for_everyone():
    for role in ("owner", "invited_helper"):
        ids = [item.id for item in state("payment", role).current_step.elements]
        assert "bank_bik" in ids
        assert "post_office_index" not in ids


def test_only_owner_can_submit():
    owner = element(state("confirmation", "owner"), "submit_application").action
    helper = element(state("confirmation", "invited_helper"), "submit_application").action
    code = element(state("confirmation", "invited_helper"), "confirmation_code").view

    assert (owner.available, owner.reason) == (True, None)
    assert (helper.available, helper.reason) == (False, "owner_only")
    assert code.locked is True


def test_review_summary_keeps_secrets():
    helper_summary = element(state("review", "invited_helper"), "review_summary")
    owner_summary = element(state("review", "owner"), "review_summary")
    helper_rows = {row.element_id: row.view for row in helper_summary.rows}
    owner_rows = {row.element_id: row.view for row in owner_summary.rows}

    assert list(helper_rows)[:2] == ["benefit_category", "benefit_reason"]
    assert helper_rows["benefit_category"].value == "pensioner"
    assert helper_rows["full_name"].model_dump() == {"state": "filled", "value": None, "locked": False}
    assert helper_rows["account_number"].locked is True
    assert "post_office_index" not in helper_rows
    assert "consent_personal_data" not in helper_rows
    assert owner_rows["account_number"].value == "40817810099910004312"


def test_error_details_depend_on_role_and_foreign_errors_are_dropped():
    errors = [
        {
            "element_id": "snils",
            "code": "invalid_format",
            "message": "Неверный формат",
            "details": "Формат: 123-456-789 00",
        },
        {"element_id": "monthly_income", "code": "required", "message": "Заполните поле", "details": None},
    ]

    helper = state("family", "invited_helper", errors=errors).errors
    operator = state("family", "government_operator", errors=errors).errors
    owner = state("family", "owner", errors=errors).errors

    assert [(item.element_id, item.message, item.details) for item in helper] == [
        ("snils", "Неверный формат", None)
    ]
    assert operator[0].details == "Формат: 123-456-789 00"
    assert owner[0].details == "Формат: 123-456-789 00"


def test_operator_hints_only_for_staff():
    assert element(state("category", "invited_helper"), "benefit_category").operator_hint is None
    assert element(state("category", "owner"), "benefit_category").operator_hint is None
    assert element(state("category", "government_operator"), "benefit_category").operator_hint.startswith(
        "Если заявитель"
    )
    assert element(state("category", "ai_agent"), "benefit_category").operator_hint is not None


def test_steps_texts_and_service_are_described():
    projected = state("income", "invited_helper")

    assert [step.status for step in projected.steps] == ["completed"] * 3 + ["current"] + ["upcoming"] * 3
    assert (projected.current_step.index, projected.current_step.title) == (4, "Доходы")
    assert projected.service.total_steps == 7
    assert element(projected, "income_info").text.startswith("Для пенсионеров")
    assert element(projected, "income_type").options[0].value == "pension"
