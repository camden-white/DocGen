"""Draft compatibility, validation, and preservation of unfinished form input."""

import json
from pathlib import Path

import pytest

from docgen.drafts import MAX_DRAFT_BYTES, DraftError, load_draft, save_draft


def test_round_trip_preserves_incomplete_values_and_paragraphs(tmp_path: Path) -> None:
    path = tmp_path / "draft.json"
    values = {
        "name": "Anne-Marie O\u2019Neill",
        "money": "not finished",
        "notes": "One\n\nTwo",
    }
    assert save_draft(path, "worksheet", values, (*values, "optional")) == path
    assert load_draft(path, "worksheet", (*values, "optional")) == values | {
        "optional": ""
    }


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"version": 1, "document": "worksheet", "values": {}, "extra": True},
        {"version": 2, "document": "worksheet", "values": {}},
        {"version": True, "document": "worksheet", "values": {}},
        {"version": 1, "document": "another", "values": {}},
        {"version": 1, "document": "worksheet", "values": {"unknown": "value"}},
        {"version": 1, "document": "worksheet", "values": {"name": 42}},
        {"version": 1, "document": "worksheet", "values": []},
    ],
)
def test_rejects_incompatible_drafts(tmp_path: Path, payload: object) -> None:
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(DraftError):
        load_draft(path, "worksheet", ("name",))


def test_malformed_missing_and_oversized_files_have_actionable_errors(
    tmp_path: Path,
) -> None:
    path = tmp_path / "draft.json"
    with pytest.raises(DraftError, match="Could not read draft"):
        load_draft(path, "worksheet", ())
    path.write_text("not json")
    with pytest.raises(DraftError, match="Could not read draft"):
        load_draft(path, "worksheet", ())
    path.write_bytes(b" " * (MAX_DRAFT_BYTES + 1))
    with pytest.raises(DraftError, match="2 MiB"):
        load_draft(path, "worksheet", ())


def test_invalid_save_preserves_existing_draft(tmp_path: Path) -> None:
    path = tmp_path / "draft.json"
    save_draft(path, "worksheet", {"name": "Existing"}, ("name",))
    before = path.read_bytes()
    with pytest.raises(DraftError):
        save_draft(path, "worksheet", {"unknown": "New"}, ("name",))
    assert path.read_bytes() == before


def test_failed_replace_preserves_existing_draft_and_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "draft.json"
    path.write_text("existing")

    def refuse_replace(self: Path, target: Path) -> None:
        raise PermissionError("test replacement failure")

    monkeypatch.setattr(Path, "replace", refuse_replace)
    with pytest.raises(DraftError, match="Could not save draft"):
        save_draft(path, "worksheet", {"name": "New"}, ("name",))
    assert path.read_text() == "existing"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["draft.json"]
