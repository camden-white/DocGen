"""Schema validation is independent of widgets and reports all invalid fields."""

from pathlib import Path

import pytest

from docgen.config import initialize_settings, load_settings
from docgen.documents.transaction_worksheet import get_document, prepare_data
from docgen.errors import ValidationError
from docgen.models import DocumentSpec, FieldSpec, validate_data


def test_validation_collects_errors_without_mutating_submission() -> None:
    fields = (
        FieldSpec("amount", "Amount", "Details", "money", required=True),
        FieldSpec("date", "Date", "Details", "date"),
        FieldSpec(
            "role", "Role", "Details", required=True, choices=("Buyer", "Seller")
        ),
    )
    values = {"amount": "$12.50", "date": "2/31/2026", "role": "", "unknown": "x"}
    original = values.copy()
    with pytest.raises(ValidationError) as caught:
        validate_data(values, fields)
    assert set(caught.value.errors) == {"date", "role", "unknown"}
    assert values == original


def test_duplicate_or_unstable_field_keys_are_rejected() -> None:
    with pytest.raises(ValueError, match="key"):
        FieldSpec("Bad Key", "Label", "Section")
    field = FieldSpec("address_1", "Address", "Section")
    with pytest.raises(ValueError, match="unique"):
        DocumentSpec("test", "Test", (field, field))


def test_distinct_numbered_keys_and_optional_values() -> None:
    fields = (
        FieldSpec("address_1", "Address", "Details"),
        FieldSpec("address_2", "Address", "Details"),
    )
    assert validate_data({"address_1": "First"}, fields) == {
        "address_1": "First",
        "address_2": "",
    }


def test_paragraphs_accept_long_terms_while_single_line_fields_remain_bounded() -> None:
    content = "word " * 3000
    paragraph = FieldSpec("terms", "Terms", "Terms", "paragraph")
    assert validate_data({"terms": content}, (paragraph,)) == {"terms": content.strip()}
    single_line = FieldSpec("name", "Name", "Client", "name")
    with pytest.raises(ValidationError, match="10,000"):
        validate_data({"name": content}, (single_line,))


def test_implied_fields_follow_validated_agent_and_client(tmp_path: Path) -> None:
    settings = load_settings(initialize_settings(tmp_path, migrate=False))
    values = {
        "agent_name": next(iter(settings.agents)),
        "property_street": "123 Example Street",
        "city_state_zip": "Example, OR 97000",
        "purchase_price": "1234.56",
        "client_type": "Seller",
        "client_names": "Anne-Marie O\u2019Neill",
        "financing_type": "Cash",
    }
    data = prepare_data(values, settings)
    assert data["counterparty_type"] == "Buyer"
    assert data["purchase_price"] == "$1,234"
    assert data["client_names"] == "Anne-Marie O\u2019Neill"
    assert data["agent_phone"] == settings.agents[values["agent_name"]].phone
    assert len(get_document(settings).fields) == 33
    values["agent_name"] = ""
    with pytest.raises(ValidationError) as caught:
        prepare_data(values, settings)
    assert "agent_name" in caught.value.errors
