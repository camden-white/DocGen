"""Renderer and compiler boundaries, including failures and atomic publication."""

import os
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest
from pypdf import PdfReader, PdfWriter

from docgen import pdf
from docgen.config import initialize_settings, load_settings
from docgen.documents.transaction_worksheet import generate
from docgen.errors import PdfCompilationError


def test_escaping_is_single_pass_and_preserves_paragraphs() -> None:
    assert pdf.escape_latex(r"C:\Docs & 50% {$5}_#~^") == (
        r"C:\textbackslash{}Docs \& 50\% \{\$5\}\_\#\textasciitilde{}\textasciicircum{}"
    )
    assert pdf.escape_latex("First\nSecond") == r"First\par Second"


def test_substitution_never_reprocesses_entered_text(tmp_path: Path) -> None:
    template = tmp_path / "template.tex"
    template.write_text("@@address_1@@|@@address_2@@", encoding="utf-8")
    assert (
        pdf.render_latex(template, {"address_1": "@@address_2@@", "address_2": "Other"})
        == "@@address\\_2@@|Other"
    )
    with pytest.raises(PdfCompilationError, match="address_2"):
        pdf.render_latex(template, {"address_1": "Only one"})
    template.write_text("@@INVALID-KEY@@", encoding="utf-8")
    with pytest.raises(PdfCompilationError, match="invalid placeholder"):
        pdf.render_latex(template, {})
    template.write_text("@@unfinished", encoding="utf-8")
    with pytest.raises(PdfCompilationError, match="invalid placeholder"):
        pdf.render_latex(template, {})


@pytest.fixture
def fake_compiler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"logo")
    monkeypatch.setattr(pdf, "find_xelatex", lambda: Path("xelatex"))

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        assert "-no-shell-escape" in command
        assert kwargs["timeout"] == 60
        folder = Path(kwargs["cwd"])
        assert (folder / "logo.png").read_bytes() == b"logo"
        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.write(folder / "document.pdf")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    return logo


def test_verified_output_is_published_without_leaving_staged_files(
    tmp_path: Path, fake_compiler: Path
) -> None:
    destination = tmp_path / "finished.pdf"
    assert (
        pdf.compile_pdf(
            "source", destination, logo_path=fake_compiler, expected_pages=1
        )
        == destination
    )
    assert len(PdfReader(destination).pages) == 1
    assert not list(tmp_path.glob(".docgen-*"))


def test_existing_output_requires_explicit_overwrite(
    tmp_path: Path, fake_compiler: Path
) -> None:
    destination = tmp_path / "finished.pdf"
    destination.write_bytes(b"previous document")
    with pytest.raises(FileExistsError):
        pdf.compile_pdf("source", destination, logo_path=fake_compiler)
    assert destination.read_bytes() == b"previous document"
    pdf.compile_pdf("source", destination, logo_path=fake_compiler, overwrite=True)
    assert destination.read_bytes().startswith(b"%PDF-")


def test_failed_compiler_retains_previous_output_and_stderr(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "finished.pdf"
    destination.write_bytes(b"original")

    def failed_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, "", "fixture failure")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(PdfCompilationError) as caught:
        pdf.compile_pdf("source", destination, logo_path=fake_compiler, overwrite=True)
    assert destination.read_bytes() == b"original"
    assert "fixture failure" in (caught.value.details or "")


def test_layout_failure_names_the_section_and_preserves_previous_output(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "finished.pdf"
    destination.write_bytes(b"original")
    log = "\n".join(
        [
            "LaTeX Font Info: Irrelevant setup detail.",
            "DOCGEN_LAYOUT_ERROR: Property and Terms",
            "",
            "./document.tex:301: Package docgen Error: Text exceeds available space.",
            "Shorten the entered text and generate again.",
            *("Memory statistics." for _ in range(100)),
        ]
    )

    def failed_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        (Path(kwargs["cwd"]) / "document.log").write_text(log, encoding="utf-8")
        return subprocess.CompletedProcess(command, 1, "", "")

    monkeypatch.setattr(subprocess, "run", failed_run)
    with pytest.raises(PdfCompilationError, match="Property and Terms") as caught:
        pdf.compile_pdf("source", destination, logo_path=fake_compiler, overwrite=True)
    assert "Shorten long fields" in str(caught.value)
    assert "Check Setup" not in str(caught.value)
    assert "./document.tex:301:" in (caught.value.details or "")
    assert len((caught.value.details or "").splitlines()) <= 60
    assert destination.read_bytes() == b"original"
    assert not list(tmp_path.glob(".docgen-*"))


@pytest.mark.parametrize(
    "compiler_error",
    [
        "./document.tex:18: Undefined control sequence.",
        "! Undefined control sequence.",
    ],
)
def test_compiler_failure_reports_first_error_without_layout_marker(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
    compiler_error: str,
) -> None:
    log = "\n".join(
        [
            "LaTeX Font Info: Font setup.",
            compiler_error,
            "l.18 \\unexpectedCommand",
            "! Secondary compiler error.",
            *("More diagnostics." for _ in range(100)),
        ]
    )

    def failed_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, log, "")

    monkeypatch.setattr(subprocess, "run", failed_run)
    destination = tmp_path / "finished.pdf"
    with pytest.raises(
        PdfCompilationError, match="Undefined control sequence"
    ) as caught:
        pdf.compile_pdf("source", destination, logo_path=fake_compiler)
    assert "Secondary compiler error" not in str(caught.value)
    assert compiler_error in (caught.value.details or "")
    assert not destination.exists()


@pytest.mark.parametrize(
    "marker",
    [
        "Entered text: DOCGEN_LAYOUT_ERROR: Property and Terms",
        r"DOCGEN_LAYOUT_ERROR: \input{untrusted}",
        "DOCGEN_LAYOUT_ERROR: " + "a" * 81,
    ],
)
def test_layout_labels_must_match_standalone_template_markers(marker: str) -> None:
    error = pdf._compilation_failure(
        marker
        + "\n./document.tex:301: Package docgen Error: Text exceeds available space."
    )
    assert str(error) == (
        "PDF generation failed: Package docgen Error: Text exceeds available space."
    )


def test_compiler_diagnostics_are_bounded_for_very_long_lines() -> None:
    error = pdf._compilation_failure("! Compiler error.\n" + "x" * 20_000)
    assert "Compiler error" in str(error)
    assert len(error.details or "") <= 12_000


def test_timeout_is_actionable(
    tmp_path: Path, fake_compiler: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def timeout(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired("xelatex", 60)

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(PdfCompilationError, match="exceeded 60 seconds"):
        pdf.compile_pdf("source", tmp_path / "out.pdf", logo_path=fake_compiler)
    assert not (tmp_path / "out.pdf").exists()


def test_atomic_replace_failure_keeps_previous_file(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "out.pdf"
    destination.write_bytes(b"previous")

    def fail(*args: Any) -> None:
        raise PermissionError("fixture failure")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(PdfCompilationError, match="Unable to save"):
        pdf.compile_pdf("source", destination, logo_path=fake_compiler, overwrite=True)
    assert destination.read_bytes() == b"previous"
    assert not list(tmp_path.glob(".docgen-*"))


@pytest.mark.integration
def test_real_worksheet_pdf_preserves_representative_text(tmp_path: Path) -> None:
    settings = load_settings(initialize_settings(tmp_path, migrate=False))
    problems = pdf.check_dependencies(settings.logo_path)
    if problems:
        if os.environ.get("DOCGEN_REQUIRE_PDF_TESTS") == "1":
            pytest.fail("; ".join(problems))
        pytest.skip("; ".join(problems))
    values = {
        "agent_name": next(iter(settings.agents)),
        "property_street": "123 Example Street",
        "city_state_zip": "Example, OR 97000",
        "purchase_price": "1234.56",
        "client_type": "Buyer",
        "client_names": "Anne-Marie O\u2019Neill",
        "client_phone": "+1 (503) 555-0123",
        "client_email": "Anne@example.com",
        "financing_type": "Cash",
        "concessions": "Credit of $500 & repairs.\nReceipt required.",
    }
    output = generate(values, settings, tmp_path / "worksheet.pdf")
    reader = PdfReader(output)
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "$1,234" in text
    assert "$1,234.56" not in text
    assert "Anne-Marie" in text
    assert "(503) 555-0123" in text
    assert "Credit of $500 & repairs." in text
    assert "Receipt required." in text
    assert "@@" not in text


@pytest.mark.parametrize(
    ("warning", "message"),
    [
        ("Overfull \\hbox (12pt too wide)", "exceeds the document layout"),
        ("Missing character: unsupported glyph", "cannot display"),
    ],
)
def test_successful_compiler_with_incomplete_layout_is_not_published(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
    warning: str,
    message: str,
) -> None:
    original_run = subprocess.run

    def warned_run(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        result = cast(subprocess.CompletedProcess[str], original_run(command, **kwargs))
        (Path(kwargs["cwd"]) / "document.log").write_text(warning)
        return result

    monkeypatch.setattr(subprocess, "run", warned_run)
    destination = tmp_path / "result.pdf"
    with pytest.raises(PdfCompilationError, match=message):
        pdf.compile_pdf("source", destination, logo_path=fake_compiler)
    assert not destination.exists()


def test_file_created_during_compilation_is_preserved(
    tmp_path: Path,
    fake_compiler: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "result.pdf"
    original_run = subprocess.run

    def competing_writer(
        command: list[str], **kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        result = cast(subprocess.CompletedProcess[str], original_run(command, **kwargs))
        destination.write_bytes(b"another process's document")
        return result

    monkeypatch.setattr(subprocess, "run", competing_writer)
    with pytest.raises(PdfCompilationError):
        pdf.compile_pdf("source", destination, logo_path=fake_compiler)
    assert destination.read_bytes() == b"another process's document"
    assert not list(tmp_path.glob(".docgen-*"))
