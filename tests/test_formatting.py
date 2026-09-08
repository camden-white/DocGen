"""Regression checks for input that must never be silently changed in meaning."""

from datetime import date
from decimal import Decimal

import pytest

from docgen.utils import (
    format_date,
    format_email,
    format_money,
    format_name,
    format_phone,
    format_plain,
    formatting,
    parse_date,
    parse_usd,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("$1,234.56", "$1,234"),
        ("0", "$0"),
        (" 1234.5 ", "$1,234"),
        ("", ""),
        ("999,999,999.99", "$999,999,999"),
        ("0.99", "$0"),
        ("1234", "$1,234"),
    ],
)
def test_money_discards_cents_without_rounding(raw: str, expected: str) -> None:
    assert format_money(raw) == expected
    assert format_money(expected) == expected


def test_money_parser_preserves_cents_before_display_formatting() -> None:
    assert parse_usd("$1,234.56") == Decimal("1234.56")


@pytest.mark.parametrize(
    "raw", ["-100", "1,23", "NaN", "Infinity", "12.345", "1e3", "abc123", "²", "+5"]
)
def test_money_rejects_invalid_input(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_usd(raw)


def test_money_formatting_is_idempotent_at_supported_limit() -> None:
    formatted = format_money("999999999999999999.99")
    assert format_money(formatted) == formatted
    with pytest.raises(ValueError, match="less than"):
        format_money("1" * 24)


def test_names_and_paragraphs_preserve_meaning() -> None:
    assert (
        format_name("  Anne-Marie  O\u2019Neill & José Jr. ")
        == "Anne-Marie O\u2019Neill & José Jr."
    )
    assert (
        format_plain(" First line.\n\n  Second paragraph. ")
        == "First line.\n\n  Second paragraph."
    )


@pytest.mark.parametrize(
    "raw", ["5035550123", "(503) 555-0123", "+1 (503) 555-0123", "1-503-555-0123"]
)
def test_phone_preserves_country_prefixed_number(raw: str) -> None:
    assert format_phone(raw) == "(503) 555-0123"


@pytest.mark.parametrize(
    "raw",
    ["503", "503555012345", "5035550123 ext 7", "+44 7700 900123", "call5035550123"],
)
def test_phone_rejects_truncation(raw: str) -> None:
    with pytest.raises(ValueError):
        format_phone(raw)


def test_incomplete_country_prefixed_phone_is_rejected() -> None:
    with pytest.raises(ValueError, match="10 phone digits"):
        format_phone("+1 (503) 555-012")


def test_dates_are_real_and_unambiguous() -> None:
    assert parse_date("2028-02-29") == date(2028, 2, 29)
    assert format_date("9/6/2026") == "09/06/2026"
    assert format_date("2026-09-06") == "09/06/2026"


@pytest.mark.parametrize(
    "raw", ["02/31/2026", "02/29/2026", "9/6/26", "2026/09/06", "June 6 2026"]
)
def test_invalid_dates_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_date(raw)


def test_email_preserves_local_case_and_rejects_internal_whitespace() -> None:
    assert format_email(" Person+tag@EXAMPLE.COM ") == "Person+tag@example.com"
    with pytest.raises(ValueError):
        format_email("per son@example.com")


@pytest.mark.parametrize(
    "kind", ["money", "date", "phone", "email", "paragraph", "name", "text", None]
)
def test_blank_optional_fields_stay_blank(kind: str | None) -> None:
    assert formatting("   ", kind) == ""
