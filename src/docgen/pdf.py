"""Strict template rendering, dependency diagnostics, and atomic PDF generation."""

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Collection, Mapping
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .errors import PdfCompilationError

_PLACEHOLDER = re.compile(r"@@([a-z][a-z0-9_]*)@@")
_COMPILER_ERROR = re.compile(
    r"^(?:[^\n]*\.(?:tex|sty|cls|def|cfg):\d+:|!)\s*(?P<message>.+)$"
)
_LAYOUT_ERROR = re.compile(r"DOCGEN_LAYOUT_ERROR: ([A-Za-z][A-Za-z0-9 /,&()-]{0,79})")
_MAX_DIAGNOSTIC_LINES = 60
_MAX_DIAGNOSTIC_CHARACTERS = 12_000
_LATEX_ESCAPES = str.maketrans(
    {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\n": "\\par ",
    }
)
_REQUIRED_TEX_FILES = (
    "fontspec.sty",
    "graphicx.sty",
    "xcolor.sty",
    "etoolbox.sty",
    "geometry.sty",
    "texgyreheros-regular.otf",
    "texgyreheros-bold.otf",
)


def escape_latex(text: str, *, break_long_tokens: bool = False) -> str:
    """Escape plain text once, retaining explicit paragraph breaks."""
    if break_long_tokens:
        # Zero-width break opportunities prevent long URLs/identifiers spilling
        # beyond a terms column. Insert them only after escaping the original text.
        return "".join(
            r"\allowbreak{}".join(
                token[start : start + 12].translate(_LATEX_ESCAPES)
                for start in range(0, len(token), 12)
            )
            if len(token) > 24 and not token.isspace()
            else token.translate(_LATEX_ESCAPES)
            for token in re.split(r"(\s+)", text)
        )
    return text.translate(_LATEX_ESCAPES)


def render_latex(
    template: Path,
    data: Mapping[str, str],
    *,
    breakable_fields: Collection[str] = (),
) -> str:
    """Replace explicit field keys in the original template exactly once."""
    source = template.read_text(encoding="utf-8")
    placeholders = set(_PLACEHOLDER.findall(source))
    if "@@" in _PLACEHOLDER.sub("", source):
        raise PdfCompilationError("The template contains invalid placeholder names.")
    missing = placeholders - data.keys()
    if missing:
        raise PdfCompilationError(
            "Missing template values: " + ", ".join(sorted(missing))
        )
    return _PLACEHOLDER.sub(
        lambda match: escape_latex(
            data[match[1]], break_long_tokens=match[1] in breakable_fields
        ),
        source,
    )


def find_xelatex() -> Path:
    """Find XeLaTeX on PATH or the standard macOS TeX installation path."""
    discovered = shutil.which("xelatex")
    if discovered:
        return Path(discovered)
    macos = Path("/Library/TeX/texbin/xelatex")
    if macos.is_file() and os.access(macos, os.X_OK):
        return macos
    raise PdfCompilationError(
        "XeLaTeX was not found. Install MacTeX, MiKTeX, or TeX Live and run Check Setup."
    )


def check_dependencies(logo_path: Path | None = None) -> list[str]:
    """Return actionable setup problems without writing files or launching a GUI."""
    problems: list[str] = []
    try:
        xelatex = find_xelatex()
    except PdfCompilationError as error:
        problems.append(str(error))
    else:
        kpsewhich = xelatex.with_name(
            "kpsewhich.exe" if os.name == "nt" else "kpsewhich"
        )
        executable = (
            str(kpsewhich) if kpsewhich.is_file() else shutil.which("kpsewhich")
        )
        if executable is None:
            problems.append("kpsewhich was not found; repair your TeX installation.")
        else:
            for resource in _REQUIRED_TEX_FILES:
                try:
                    result = subprocess.run(
                        [executable, resource],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=10,
                    )
                    if result.returncode or not result.stdout.strip():
                        problems.append(f"Missing TeX resource: {resource}")
                except OSError, subprocess.SubprocessError:
                    problems.append(
                        "Unable to inspect TeX resources; repair your TeX installation."
                    )
                    break
    if logo_path is not None:
        try:
            with logo_path.open("rb") as stream:
                header = stream.read(8)
            if header != b"\x89PNG\r\n\x1a\n":
                problems.append("Choose a valid PNG logo in Settings.")
        except OSError:
            problems.append(
                "The configured logo cannot be read. Choose a PNG logo in Settings."
            )
    return problems


def _verify_pdf(path: Path, expected_pages: int | None) -> None:
    try:
        with path.open("rb") as stream:
            if stream.read(5) != b"%PDF-":
                raise PdfCompilationError("The compiler did not produce a PDF file.")
            stream.seek(0)
            reader = PdfReader(stream, strict=True)
            count = len(reader.pages)
            if count == 0 or (expected_pages is not None and count != expected_pages):
                raise PdfCompilationError(
                    "The document exceeds its page layout. Shorten the entered text and retry."
                )
    except (OSError, PdfReadError, ValueError) as error:
        raise PdfCompilationError("The generated PDF could not be verified.") from error


def _compilation_failure(log: str) -> PdfCompilationError:
    """Summarize the first TeX error and retain bounded diagnostic context.

    Layout labels are literal, narrowly matched template markers immediately
    preceding a DocGen package error. Compiler output is only displayed as text.
    """
    lines = log.splitlines()
    message = "PDF generation failed. See the compilation diagnostics for details."
    start = max(0, len(lines) - _MAX_DIAGNOSTIC_LINES)
    for index, line in enumerate(lines):
        error = _COMPILER_ERROR.fullmatch(line)
        if error is None:
            continue
        summary = error["message"][:500]
        message = f"PDF generation failed: {summary}"
        start = max(0, index - 3)
        if summary.startswith("Package docgen Error:"):
            for previous in reversed(lines[max(0, index - 5) : index]):
                marker = _LAYOUT_ERROR.fullmatch(previous)
                if marker is not None:
                    message = (
                        f"The {marker[1]} section exceeds the available page space "
                        "at the minimum readable font size. "
                        "Shorten long fields in that section and retry."
                    )
                    break
        break
    details = "\n".join(lines[start : start + _MAX_DIAGNOSTIC_LINES])[
        :_MAX_DIAGNOSTIC_CHARACTERS
    ]
    return PdfCompilationError(message, details=details)


def compile_pdf(
    latex_source: str,
    output_pdf: Path,
    *,
    logo_path: Path,
    overwrite: bool = False,
    timeout: float = 60,
    expected_pages: int | None = None,
) -> Path:
    """Compile with a time limit and publish a verified PDF atomically.

    With overwrite=False an existing destination is never replaced, including
    files created by another process during compilation. The destination's parent
    must already exist, as selected by the caller's file dialog or CLI.
    """
    if timeout <= 0:
        raise ValueError("Compilation timeout must be positive.")
    xelatex = find_xelatex()
    destination = output_pdf.expanduser().absolute()
    if destination.exists() and not overwrite:
        raise FileExistsError(f"A file already exists at {destination}.")
    try:
        with tempfile.TemporaryDirectory(prefix="docgen-") as folder:
            build_dir = Path(folder)
            shutil.copyfile(logo_path, build_dir / "logo.png")
            (build_dir / "document.tex").write_text(latex_source, encoding="utf-8")
            try:
                result = subprocess.run(
                    [
                        str(xelatex),
                        "-no-shell-escape",
                        "-interaction=nonstopmode",
                        "-halt-on-error",
                        "-file-line-error",
                        "document.tex",
                    ],
                    cwd=build_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired as error:
                raise PdfCompilationError(
                    f"PDF generation exceeded {timeout:g} seconds. Shorten the text and retry."
                ) from error
            log_path = build_dir / "document.log"
            log = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file()
                else result.stdout + "\n" + result.stderr
            )
            built_pdf = build_dir / "document.pdf"
            if result.returncode or not built_pdf.is_file():
                raise _compilation_failure(log)
            if "Missing character:" in log:
                raise PdfCompilationError(
                    "The document font cannot display some entered characters. "
                    "Replace unsupported characters or configure a suitable template font.",
                    details="\n".join(
                        line
                        for line in log.splitlines()
                        if "Missing character:" in line
                    ),
                )
            if "Overfull \\hbox" in log or "Overfull \\vbox" in log:
                raise PdfCompilationError(
                    "Some text exceeds the document layout. Shorten long fields and retry.",
                    details="\n".join(
                        line for line in log.splitlines() if "Overfull" in line
                    ),
                )
            _verify_pdf(built_pdf, expected_pages)
            staged: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    prefix=".docgen-",
                    suffix=".pdf",
                    dir=destination.parent,
                    delete=False,
                ) as stream:
                    staged = Path(stream.name)
                    with built_pdf.open("rb") as source:
                        shutil.copyfileobj(source, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                if overwrite:
                    os.replace(staged, destination)
                else:
                    # A hard link publishes the complete file without a check/write race.
                    os.link(staged, destination)
            finally:
                if staged is not None:
                    staged.unlink(missing_ok=True)
    except FileExistsError as error:
        raise PdfCompilationError(
            f"A file appeared at {destination} during generation. "
            "Choose another filename or explicitly confirm replacing it."
        ) from error
    except OSError as error:
        raise PdfCompilationError(
            f"Unable to save the PDF at {destination}. Check the folder and file permissions."
        ) from error
    return destination
