"""Application behavior plus opt-in native GUI integration checks."""

import json
import os
import platform
import threading
import time
import tkinter as tk
from collections.abc import Iterator
from concurrent.futures import Future
from contextlib import suppress
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import cast
from unittest.mock import MagicMock

import pytest

from docgen import main, settings_dialog, ui
from docgen.config import Settings, initialize_settings, load_settings
from docgen.documents.transaction_worksheet import get_document
from docgen.errors import PdfCompilationError, PdfOpenError
from docgen.utils import open_pdf


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return load_settings(initialize_settings(tmp_path, migrate=False))


def _valid_values(settings: Settings) -> dict[str, str]:
    return {
        "agent_name": next(iter(settings.agents)),
        "property_street": "123 Main Street",
        "city_state_zip": "Portland, OR 97201",
        "purchase_price": "1234.56",
        "client_type": "Buyer",
        "client_names": "Anne-Marie O\u2019Neill",
        "financing_type": settings.financing[0],
    }


def _application_stub(settings: Settings) -> ui.Application:
    application = object.__new__(ui.Application)
    application.settings = settings
    application.document = get_document(settings)
    application.form = MagicMock(spec=ui.DocumentForm)
    application.form.collect.return_value = _valid_values(settings)
    application.status = MagicMock(spec=tk.StringVar)
    application.root = MagicMock(spec=tk.Tk)
    application.executor = MagicMock()
    application.future = None
    application.open_after = MagicMock(spec=tk.BooleanVar)
    application.open_after.get.return_value = True
    application.controls = []
    application.open_check = MagicMock()
    application.progress = MagicMock()
    application.job_kind = "generate"
    application.saved_pdf = None
    return application


def _wait_for_job(application: ui.Application) -> None:
    """Process GUI events while callbacks update the application's worker state."""
    timeout = time.monotonic() + 4
    while application.future is not None and time.monotonic() < timeout:
        application.root.update()
        time.sleep(0.01)
    assert application.future is None


@pytest.mark.parametrize(
    ("street", "expected"),
    [
        ("", "Transaction Worksheet.pdf"),
        ("123 Main Street", "Transaction Worksheet - 123 Main Street.pdf"),
        ('../a:b/c*?"<>|', "Transaction Worksheet - abc.pdf"),
    ],
)
def test_pdf_names_are_portable(street: str, expected: str) -> None:
    assert ui.default_pdf_name({"property_street": street}) == expected
    assert len(ui.default_pdf_name({"property_street": "x" * 1000})) < 120


def test_complete_form_is_validated_before_file_dialog(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = _application_stub(settings)
    application.form = MagicMock(spec=ui.DocumentForm)
    application.form.collect.return_value = {"purchase_price": "$1,234.567"}
    choose_file = MagicMock()
    monkeypatch.setattr(filedialog, "asksaveasfilename", choose_file)
    application.generate_pdf()
    choose_file.assert_not_called()
    application.form.show_errors.assert_called_once()
    errors = application.form.show_errors.call_args.args[0]
    assert {"purchase_price", "agent_name", "client_type"} <= errors.keys()
    assert application.future is None


def test_declining_overwrite_never_submits_generation(
    settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "existing.pdf"
    destination.write_bytes(b"existing")
    application = _application_stub(settings)
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", MagicMock(return_value=str(destination))
    )
    monkeypatch.setattr(messagebox, "askyesno", MagicMock(return_value=False))
    application.generate_pdf()
    assert application.future is None
    assert destination.read_bytes() == b"existing"


@pytest.mark.parametrize("viewer_fails", [False, True])
def test_saved_pdf_is_reported_after_background_viewer_finishes(
    viewer_fails: bool,
    settings: Settings,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = _application_stub(settings)
    destination = tmp_path / "result.pdf"
    completed: Future[Path] = Future()
    completed.set_result(destination)
    application.future = completed
    viewer: Future[None] = Future()
    executor = MagicMock()
    executor.submit.return_value = viewer
    application.executor = executor
    warning = MagicMock()
    monkeypatch.setattr(messagebox, "showwarning", warning)
    application._poll()
    executor.submit.assert_called_once_with(open_pdf, destination)
    # _poll replaces the future; mypy retains the narrowing from before that call.
    assert cast(object, application.future) is viewer
    assert application.saved_pdf == destination
    assert application.job_kind == "open"
    cast(MagicMock, application.status).set.assert_called_with(
        f"PDF saved: {destination}. Opening viewer…"
    )
    cast(MagicMock, application.form).set_enabled.assert_called_with(False)
    warning.assert_not_called()
    if viewer_fails:
        viewer.set_exception(PdfOpenError("No viewer"))
    else:
        viewer.set_result(None)
    application._poll()
    assert application.future is None
    cast(MagicMock, application.status).set.assert_called_with(
        f"PDF saved: {destination}"
    )
    cast(MagicMock, application.form).set_enabled.assert_called_with(True)
    if viewer_fails:
        warning.assert_called_once()
        assert str(destination) in warning.call_args.args[1]
        assert "No viewer" in warning.call_args.args[1]
    else:
        warning.assert_not_called()


def test_compile_failure_restores_controls_and_exposes_diagnostics(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = _application_stub(settings)
    completed: Future[Path] = Future()
    completed.set_exception(
        PdfCompilationError("Could not compile", details="Useful compiler log")
    )
    application.future = completed
    show_error = MagicMock()
    details = MagicMock()
    monkeypatch.setattr(messagebox, "showerror", show_error)
    monkeypatch.setattr(application, "_show_details", details)
    application._poll()
    assert application.future is None
    cast(MagicMock, application.form).set_enabled.assert_called_with(True)
    show_error.assert_called_once()
    details.assert_called_once_with("Compilation diagnostics", "Useful compiler log")


def test_dependency_cli_reports_json_without_user_config(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from docgen import pdf

    monkeypatch.setattr(
        pdf, "check_dependencies", MagicMock(return_value=["Install XeLaTeX"])
    )
    assert main.main(["--check"]) == 1
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "errors": ["Install XeLaTeX"],
    }
    monkeypatch.setattr(pdf, "check_dependencies", MagicMock(return_value=[]))
    assert main.main(["--check"]) == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "errors": []}


@pytest.fixture
def gui_application(settings: Settings) -> Iterator[ui.Application]:
    if os.environ.get("DOCGEN_RUN_GUI") != "1":
        pytest.skip("Set DOCGEN_RUN_GUI=1 to run native Tk integration tests.")
    root = ui.window()
    root.withdraw()
    application = ui.Application(root, settings)
    try:
        yield application
    finally:
        application.executor.shutdown(wait=True, cancel_futures=True)
        with suppress(tk.TclError):
            root.destroy()


@pytest.mark.gui
def test_gui_textbox_supports_native_indices_and_complete_field_values(
    gui_application: ui.Application,
) -> None:
    form = gui_application._form()
    textbox = form.widgets["concessions"]
    assert isinstance(textbox, ui.Textbox)
    textbox.insert("1.0", "First line\nSecond line\n")
    assert textbox.get("1.0", "1.end") == "First line"
    assert textbox.get("2.0", "2.end") == "Second line"
    assert textbox.get_value() == "First line\nSecond line\n"
    assert form.collect()["concessions"] == textbox.get_value()
    form.validate_field(
        next(field for field in form.document.fields if field.key == "concessions")
    )
    assert textbox.get_value() == "First line\nSecond line"


@pytest.mark.gui
def test_gui_preserves_invalid_input_and_uses_integer_text_height(
    gui_application: ui.Application,
) -> None:
    application = gui_application
    form = application._form()
    values = _valid_values(application.settings) | {"purchase_price": "$1,234.567"}
    form.set_values(values)
    money_field = next(
        field for field in application.document.fields if field.key == "purchase_price"
    )
    form.validate_field(money_field)
    assert form.collect()["purchase_price"] == "$1,234.567"
    assert form.errors["purchase_price"].get()
    for widget in form.widgets.values():
        if isinstance(widget, ui.Textbox):
            assert int(widget.cget("height")) == 4
    assert (
        len(
            [
                child
                for child in application.root.winfo_children()
                if isinstance(child, tk.Tk)
            ]
        )
        == 0
    )


@pytest.mark.gui
def test_gui_compiles_in_worker_and_restores_editability(
    gui_application: ui.Application, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = gui_application
    form = application._form()
    form.set_values(_valid_values(application.settings))
    destination = tmp_path / "document.pdf"
    worker_started = threading.Event()
    worker_can_finish = threading.Event()
    thread_ids: list[int] = []

    def fake_generate(
        values: object, settings: Settings, output: Path, *, overwrite: bool = False
    ) -> Path:
        thread_ids.append(threading.get_ident())
        worker_started.set()
        if not worker_can_finish.wait(timeout=3):
            raise TimeoutError("Test did not release worker")
        output.write_bytes(b"generated")
        return output

    monkeypatch.setattr(ui, "generate", fake_generate)
    monkeypatch.setattr(
        filedialog, "asksaveasfilename", MagicMock(return_value=str(destination))
    )
    application.open_after.set(False)
    application.generate_pdf()
    try:
        assert worker_started.wait(timeout=2)
        assert len(thread_ids) == 1
        assert thread_ids[0] != threading.get_ident()
        assert str(application.generate_button.cget("state")) == "disabled"
        assert str(form.widgets["property_street"].cget("state")) == "disabled"
    finally:
        worker_can_finish.set()
    _wait_for_job(application)
    assert application.status.get() == f"PDF saved: {destination}"
    assert str(application.generate_button.cget("state")) == "normal"
    assert str(form.widgets["agent_name"].cget("state")) == "readonly"
    assert form.collect()["client_names"] == "Anne-Marie O\u2019Neill"


@pytest.mark.gui
def test_gui_closing_dirty_form_can_be_cancelled(
    gui_application: ui.Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = gui_application
    application._form().set_values({"client_names": "Unsaved name"})
    monkeypatch.setattr(messagebox, "askyesnocancel", MagicMock(return_value=None))
    application.close()
    assert application.root.winfo_exists()
    assert application._form().collect()["client_names"] == "Unsaved name"


@pytest.mark.gui
@pytest.mark.parametrize("viewer_fails", [False, True])
def test_gui_viewer_runs_in_worker_without_blocking_events(
    viewer_fails: bool,
    gui_application: ui.Application,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = gui_application
    destination = tmp_path / "document.pdf"
    completed: Future[Path] = Future()
    completed.set_result(destination)
    application.future = completed
    worker_started = threading.Event()
    worker_can_finish = threading.Event()
    thread_ids: list[int] = []
    warning = MagicMock()
    monkeypatch.setattr(messagebox, "showwarning", warning)

    def fake_open(path: Path) -> None:
        assert path == destination
        thread_ids.append(threading.get_ident())
        worker_started.set()
        if not worker_can_finish.wait(timeout=3):
            raise TimeoutError("Test did not release viewer worker")
        if viewer_fails:
            raise PdfOpenError("No PDF viewer is configured")

    monkeypatch.setattr(ui, "open_pdf", fake_open)
    application._poll()
    try:
        assert worker_started.wait(timeout=2)
        assert len(thread_ids) == 1
        assert thread_ids[0] != threading.get_ident()
        assert application.future is not None
        assert str(application.generate_button.cget("state")) == "disabled"
        event_processed = threading.Event()
        application.root.after_idle(event_processed.set)
        application.root.update()
        assert event_processed.is_set()
    finally:
        worker_can_finish.set()
    _wait_for_job(application)
    assert application.status.get() == f"PDF saved: {destination}"
    assert str(application.generate_button.cget("state")) == "normal"
    assert warning.call_count == int(viewer_fails)


@pytest.mark.gui
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS Quit command")
def test_gui_native_quit_protects_unsaved_document(
    gui_application: ui.Application, monkeypatch: pytest.MonkeyPatch
) -> None:
    application = gui_application
    application._form().set_values({"client_names": "Unsaved name"})
    confirm = MagicMock(return_value=None)
    monkeypatch.setattr(messagebox, "askyesnocancel", confirm)
    application.root.tk.call("::tk::mac::Quit")
    confirm.assert_called_once()
    assert application.root.winfo_exists()
    assert application._form().collect()["client_names"] == "Unsaved name"


def _descendants(widget: tk.Misc) -> Iterator[tk.Misc]:
    for child in widget.winfo_children():
        yield child
        yield from _descendants(child)


@pytest.mark.gui
@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS Quit command")
@pytest.mark.parametrize("discard_settings", [False, True])
def test_gui_native_quit_protects_settings_and_restores_document_guard(
    discard_settings: bool,
    gui_application: ui.Application,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application = gui_application
    application._form().set_values({"client_names": "Unsaved document"})
    previous_close = application.root.protocol("WM_DELETE_WINDOW")
    original = application.settings.config_path.read_text(encoding="utf-8")
    dialog = settings_dialog.edit_settings(
        application.root, application.settings.config_path, MagicMock()
    )
    settings_guard = application.root.protocol("WM_DELETE_WINDOW")
    editor = next(
        widget for widget in _descendants(dialog) if isinstance(widget, tk.Text)
    )
    editor.insert("end", "\n# Unsaved settings\n")
    confirm_settings = MagicMock(return_value=discard_settings)
    confirm_document = MagicMock(return_value=None)
    monkeypatch.setattr(messagebox, "askyesno", confirm_settings)
    monkeypatch.setattr(messagebox, "askyesnocancel", confirm_document)
    application.root.tk.call("::tk::mac::Quit")
    confirm_settings.assert_called_once()
    assert application.root.winfo_exists()
    assert application._form().collect()["client_names"] == "Unsaved document"
    assert application.settings.config_path.read_text(encoding="utf-8") == original
    if discard_settings:
        assert not dialog.winfo_exists()
        confirm_document.assert_called_once()
    else:
        assert dialog.winfo_exists()
        assert "Unsaved settings" in editor.get("1.0", "end-1c")
        confirm_document.assert_not_called()
        # Closing only the settings editor must restore the document guard too.
        confirm_settings.return_value = True
        dialog.tk.eval(dialog.protocol("WM_DELETE_WINDOW"))
        assert not dialog.winfo_exists()
    assert application.root.protocol("WM_DELETE_WINDOW") == previous_close
    assert not application.root.tk.call("info", "commands", settings_guard)
    confirm_document.reset_mock()
    application.root.tk.call("::tk::mac::Quit")
    confirm_document.assert_called_once()
    assert application.root.winfo_exists()


@pytest.mark.gui
def test_gui_focusing_offscreen_fields_scrolls_them_into_view(
    gui_application: ui.Application,
) -> None:
    application = gui_application
    application.root.geometry("900x600")
    application.root.deiconify()
    application.root.update()
    form = application._form()
    form.canvas.yview_moveto(0)
    application.root.update_idletasks()
    first = next(iter(form.widgets.values()))
    last = next(reversed(form.widgets.values()))
    assert last.winfo_rooty() > form.canvas.winfo_rooty() + form.canvas.winfo_height()

    for widget in (last, first):
        widget.event_generate("<FocusIn>")
        application.root.update_idletasks()
        top = widget.winfo_rooty() - form.canvas.winfo_rooty()
        assert top >= 0
        assert top + widget.winfo_height() <= form.canvas.winfo_height()
        visible_range = form.viewport.yview()
        widget.event_generate("<FocusIn>")
        application.root.update_idletasks()
        assert form.viewport.yview() == visible_range
