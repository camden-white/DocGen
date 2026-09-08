"""Versioned, portable document drafts containing entered form values."""

import json
import os
import tempfile
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import TypedDict, cast

from .errors import DocGenError

DRAFT_VERSION = 1
MAX_DRAFT_BYTES = 2 * 1024 * 1024


class DraftData(TypedDict):
    """Validated payload written to a portable draft file."""

    version: int
    document: str
    values: dict[str, str]


class DraftError(DocGenError):
    """A draft cannot be read, validated, or saved."""


def _validate_values(values: object, field_keys: Iterable[str]) -> dict[str, str]:
    """Validate structure without rejecting incomplete or invalid form input."""
    if not isinstance(values, dict):
        raise DraftError("Draft values must be an object containing text fields.")
    entries = cast(dict[object, object], values)
    allowed = set(field_keys)
    if any(not isinstance(key, str) or key not in allowed for key in entries):
        raise DraftError(
            "This draft contains fields that this document does not support."
        )
    if any(not isinstance(value, str) for value in entries.values()):
        raise DraftError("Every draft field must contain text.")
    validated = cast(dict[str, str], entries)
    return {key: validated.get(key, "") for key in allowed}


def load_draft(
    path: Path, document_key: str, field_keys: Iterable[str]
) -> dict[str, str]:
    """Read a compatible draft, preserving incomplete values for later editing."""
    try:
        with path.open("rb") as handle:
            payload = handle.read(MAX_DRAFT_BYTES + 1)
        if len(payload) > MAX_DRAFT_BYTES:
            raise DraftError("This draft is larger than the supported 2 MiB limit.")
        decoded: object = json.loads(payload)
    except (OSError, ValueError, UnicodeError) as error:
        raise DraftError(f"Could not read draft: {error}") from error
    if not isinstance(decoded, dict):
        raise DraftError("This file is not a DocGen draft.")
    data = cast(dict[object, object], decoded)
    if set(data) != {"version", "document", "values"}:
        raise DraftError("This file is not a DocGen draft.")
    if type(data["version"]) is not int or data["version"] != DRAFT_VERSION:
        raise DraftError(
            "This draft version is not supported by this version of DocGen."
        )
    if data["document"] != document_key:
        raise DraftError("This draft belongs to a different document type.")
    return _validate_values(data["values"], field_keys)


def save_draft(
    path: Path,
    document_key: str,
    values: Mapping[str, str],
    field_keys: Iterable[str],
) -> Path:
    """Atomically save a draft; drafts may intentionally contain unfinished input."""
    data: DraftData = {
        "version": DRAFT_VERSION,
        "document": document_key,
        "values": _validate_values(dict(values), field_keys),
    }
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    if len(payload.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise DraftError("This draft is larger than the supported 2 MiB limit.")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=".docgen-", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as error:
        raise DraftError(f"Could not save draft: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path
