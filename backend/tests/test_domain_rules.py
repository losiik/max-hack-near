import json
from datetime import date, timedelta
from pathlib import Path

from max_assist.modules.applications.crypto import decrypt_values, encrypt_values
from max_assist.modules.applications.domain import ApplicationForm
from max_assist.modules.catalog.schema import ServiceDefinition
from tests.helpers import ALL_VALUES

DATA = Path(__file__).resolve().parents[1] / "migrations" / "data"


def form(values: dict | None = None) -> ApplicationForm:
    raw = json.loads((DATA / "housing_compensation_v1.json").read_text("utf-8"))
    return ApplicationForm(ServiceDefinition.model_validate(raw), values or {})


def codes(errors) -> dict[str, str]:
    return {error.element_id: error.code for error in errors}


def test_future_birth_date_is_rejected():
    subject = form()
    subject.apply({"birth_date": str(date.today() + timedelta(days=1))})

    assert codes(subject.validate_step(subject.definition.step("family")))["birth_date"] == "out_of_range"


def test_consent_must_be_checked():
    subject = form()
    subject.apply({"consent_personal_data": False})

    assert codes(subject.validate_step(subject.definition.step("review"))) == {
        "consent_personal_data": "must_be_checked"
    }


def test_too_short_address_is_rejected():
    subject = form()
    subject.apply({"region": "spb", "address": "Невский", "ownership_type": "owner", "living_area": 40})

    assert codes(subject.validate_step(subject.definition.step("address")))["address"] == "invalid_format"


def test_values_of_wrong_type_are_reported_not_stored():
    subject = form()

    errors = subject.apply({"has_disabled_members": "да", "birth_date": "31-12-2020", "family_size": "два"})

    assert codes(errors) == {
        "has_disabled_members": "invalid_format",
        "birth_date": "invalid_format",
        "family_size": "invalid_format",
    }
    assert subject.values == {}


def test_empty_string_clears_value():
    subject = form()
    subject.apply({"family_size": 3})
    subject.apply({"family_size": ""})

    assert subject.state_of("family_size") == "empty"


def test_conditional_field_follows_its_source():
    subject = form()
    income = subject.definition.element("monthly_income")

    subject.apply({"income_type": "none"})
    assert subject.is_visible(income) is False
    assert subject.validate_step(subject.definition.step("income")) == []

    subject.apply({"income_type": "salary"})
    assert subject.is_visible(income) is True
    assert codes(subject.validate_step(subject.definition.step("income")))["monthly_income"] == "required"


def test_filled_application_has_no_errors_and_ignores_sms_code():
    subject = form()
    subject.apply(ALL_VALUES)

    assert subject.validate_all() == {}


def test_incomplete_application_reports_every_step():
    subject = form()

    assert set(subject.validate_all()) == {"category", "address", "family", "income", "payment", "review"}


def test_encryption_round_trip():
    values = {"snils": "123-456-789 00", "full_name": "Петрова Людмила Ивановна"}

    blob = encrypt_values(values)

    assert b"123-456-789" not in blob
    assert decrypt_values(blob) == values
    assert encrypt_values({}) is None
    assert decrypt_values(None) == {}
