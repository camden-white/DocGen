"""Document field definitions and validation shared by the GUI and generators."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .errors import ValidationError
from .utils import formatting

type FieldKind = Literal["text", "paragraph", "name", "money", "date", "phone", "email"]


@dataclass(frozen=True)
class FieldSpec:
    """Stable field key, user-facing label, and validation/display metadata."""

    key: str
    label: str
    section: str
    kind: FieldKind = "text"
    required: bool = False
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if re.fullmatch(r"[a-z][a-z0-9_]*", self.key) is None:
            raise ValueError(f"Invalid field key: {self.key}")
        if not self.label or not self.section:
            raise ValueError("Fields require a label and a section.")


@dataclass(frozen=True)
class DocumentSpec:
    """Explicit document identity and ordered form fields."""

    key: str
    display_name: str
    fields: tuple[FieldSpec, ...]

    def __post_init__(self) -> None:
        keys = [field.key for field in self.fields]
        if len(keys) != len(set(keys)):
            raise ValueError("Document field keys must be unique.")


def validate_data(
    values: Mapping[str, object], fields: tuple[FieldSpec, ...]
) -> dict[str, str]:
    """Validate the entire submission, collecting errors keyed by field identity."""
    normalized: dict[str, str] = {}
    errors: dict[str, str] = {}
    allowed = {field.key for field in fields}
    for key in values.keys() - allowed:
        errors[key] = "Unknown field."
    for field in fields:
        raw = values.get(field.key, "")
        if not isinstance(raw, str):
            errors[field.key] = "Expected text."
            continue
        if field.kind != "paragraph" and len(raw) > 10000:
            errors[field.key] = "This field is too long (maximum 10,000 characters)."
            continue
        if any(ord(character) < 32 and character not in "\t\n\r" for character in raw):
            errors[field.key] = "Remove unsupported control characters."
            continue
        try:
            # Choice labels come from validated configuration and retain their identity.
            value = raw.strip() if field.choices else formatting(raw, field.kind)
            if field.required and not value:
                raise ValueError("This field is required.")
            if value and field.choices and value not in field.choices:
                raise ValueError("Choose one of the listed options.")
            normalized[field.key] = value
        except ValueError as error:
            errors[field.key] = str(error)
    if errors:
        raise ValidationError(errors)
    return normalized
