"""Package utilities"""

import platform
import shutil
import subprocess
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from docgen.config import LOGO_PATH


def collapse_spaces(string: str) -> str:
    """Turn all whitespaces into single spaces"""
    return (" ").join(string.split())


def letterize(string: str, spaces: bool = False) -> str:
    """Remove all non-letters with or without spaces"""
    letters = [
        letter for letter in string if letter.isalpha() or spaces and letter.isspace()
    ]
    formatted = "".join(letters)
    return formatted


def latex_placeholder(string: str, delimiter: str = "@@") -> str:
    """Turn string into corresponding LaTeX template placeholder"""
    formatted = delimiter + letterize(string).upper() + delimiter
    return formatted


def format_email(string: str) -> str:
    """Remove spaces and lower-case"""
    formatted = string.lower().replace(" ", "")
    return formatted


def digitize(string: str) -> str:
    """Remove all non-digits"""
    digits = [d for d in string if d.isdigit()]
    return "".join(digits)


def format_phone(string: str) -> str:
    """Turn string into digits of the form (123) 456-7890"""
    digits = digitize(string)
    formatted = ""
    if digits:
        formatted = f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    return formatted


def format_money(string: str) -> str:
    """Format string into digits of the form $1,234.56"""
    digits = digitize(string)
    formatted = ""
    if digits:
        formatted = r"$" + f"{int(digits):,}"
    return formatted


def format_date(string: str) -> str:
    """Remove non-digits and non-slashes"""
    clean_string = string.replace("-", "/").replace(" ", "")
    components = clean_string.split("/")
    numeric_components = [digitize(c) for c in components]
    formatted = "/".join(numeric_components)
    return formatted


def format_name(string: str) -> str:
    """Remove non-letters and turn whitespaces into single spaces"""
    formatted = collapse_spaces(letterize(string, spaces=True))
    return formatted


def format_plain(string: str) -> str:
    """Plain paragraph formatting"""
    formatted = collapse_spaces(string)
    return formatted


def snap(event: tk.Event[ttk.Entry], format_type: str | None) -> None:
    """Snap an event to it's proper formatting"""

    entry = event.widget
    raw = entry.get().strip()

    if not raw:
        return

    if format_type is None:
        formatted = format_plain(raw)
    elif format_type == "name":
        formatted = format_name(raw)
    elif format_type == "phone":
        formatted = format_phone(raw)
    elif format_type == "email":
        formatted = format_email(raw)
    elif format_type == "money":
        formatted = format_money(raw)
    elif format_type == "date":
        formatted = format_date(raw)
    else:
        raise ValueError(f"Unrecognized format type for {entry}")

    entry.delete(0, tk.END)
    entry.insert(0, formatted)


def open_pdf(pdf_path: Path) -> None:
    """Open PDF according to the platform"""

    system: str = platform.system()

    if system == "Darwin":
        subprocess.run(["open", str(pdf_path)], check=True)

    elif system == "Windows":
        subprocess.run(
            ["cmd", "/c", "start", "", str(pdf_path)],
            check=True,
        )

    elif system == "Linux":
        subprocess.run(["xdg-open", str(pdf_path)], check=True)


def escape_latex(string: str) -> str:
    """Escape special characters that would be non-strings in LaTeX."""

    replacements = (
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("$", r"\$"),
        ("#", r"\#"),
        ("_", r"\_"),
        ("{", r"\{"),
        ("}", r"\}"),
        ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    )
    for source, replacement in replacements:
        string = string.replace(source, replacement)
    return string


def find_xelatex() -> Path:
    """Return a working XeLaTeX executable, including the macOS TeX Live path."""

    discovered = shutil.which("xelatex")
    if discovered:
        return Path(discovered)

    macos_texlive = Path("/Library/TeX/texbin/xelatex")
    if macos_texlive.is_file():
        return macos_texlive

    raise FileNotFoundError(
        "XeLaTeX was not found. Install a LaTeX distribution "
        "such as MiKTeX on Windows or MacTeX on macOS."
    )


def render_latex(template: Path, data: dict[str, str]) -> str:
    """Insert safe values into the LaTeX template."""

    with open(template, "r", encoding="utf-8") as file:
        latex_template = file.read()

    latex_template = latex_template.replace("../logo.png", LOGO_PATH.as_posix())

    for key, value in data.items():
        latex_template = latex_template.replace(
            latex_placeholder(key), escape_latex(value)
        )

    return latex_template


def compile_pdf(latex_source: str, output_pdf: Path) -> None:
    """Compile LaTeX in an isolated directory and copy out a verified PDF."""

    xelatex = find_xelatex()
    output_pdf = output_pdf.expanduser().resolve()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="transaction-worksheet-") as tmp:
        build_dir = Path(tmp)
        tex_path = build_dir / "document.tex"
        tex_path.write_text(latex_source, encoding="utf-8")

        command = [
            str(xelatex),
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            "document.tex",
        ]
        result = subprocess.run(
            command,
            cwd=build_dir,
            capture_output=True,
            text=True,
            check=False,
        )

        built_pdf = build_dir / "document.pdf"
        if result.returncode != 0 or not built_pdf.is_file():
            log_path = build_dir / "document.log"
            log_text = (
                log_path.read_text(encoding="utf-8", errors="replace")
                if log_path.is_file()
                else result.stdout
            )
            raise RuntimeError(
                "XeLaTeX compilation failed. Final log lines:\n\n"
                + "\n".join(log_text.splitlines()[-60:])
            )

        shutil.copy2(built_pdf, output_pdf)

    if not output_pdf.is_file() or output_pdf.stat().st_size == 0:
        raise RuntimeError(f"PDF verification failed: {output_pdf}")
