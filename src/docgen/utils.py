"""Pure input formatting and platform file-opening helpers; no Tk dependencies."""

import os
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from .errors import PdfOpenError

_USD_AMOUNT = re.compile(r"\$?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]{1,2})?")
_PHONE = re.compile(r"[+()0-9 .-]+")


def collapse_spaces(string: str) -> str:
    """Collapse whitespace in a single-line field without removing punctuation."""
    return " ".join(string.split())


def parse_usd(string: str) -> Decimal:
    """Parse a nonnegative US dollar amount with at most two decimal places."""
    text = string.strip()
    if len(text) > 64 or _USD_AMOUNT.fullmatch(text) is None:
        raise ValueError("Enter an amount such as 1234 or $1,234.")
    amount = Decimal(text.removeprefix("$").replace(",", ""))
    if amount >= Decimal("1e18"):
        raise ValueError("The amount must be less than 1,000,000,000,000,000,000.")
    return amount


def format_money(string: str) -> str:
    """Display whole dollars, discarding any cents without rounding."""
    if not string.strip():
        return ""
    dollars = parse_usd(string).to_integral_value(rounding=ROUND_DOWN)
    return f"${dollars:,.0f}"


def parse_date(string: str) -> date:
    """Accept explicit YYYY-MM-DD or US M/D/YYYY dates; reject impossible dates."""
    text = string.strip()
    try:
        if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            return date.fromisoformat(text)
        if re.fullmatch(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}", text):
            month, day, year = map(int, text.split("/"))
            return date(year, month, day)
    except ValueError:
        pass
    raise ValueError("Enter a real date as M/D/YYYY or YYYY-MM-DD.")


def format_date(string: str) -> str:
    """Normalize valid dates to MM/DD/YYYY."""
    if not string.strip():
        return ""
    parsed = parse_date(string)
    return f"{parsed.month:02d}/{parsed.day:02d}/{parsed.year:04d}"


def format_phone(string: str) -> str:
    """Format ten-digit North American numbers, optionally prefixed with +1/1."""
    text = string.strip()
    if not text:
        return ""
    if _PHONE.fullmatch(text) is None or ("+" in text and not text.startswith("+1")):
        raise ValueError("Enter a 10-digit phone number, optionally prefixed with +1.")
    digits = "".join(character for character in text if character in "0123456789")
    if text.startswith("+") and len(digits) != 11:
        raise ValueError("A +1 country code must be followed by all 10 phone digits.")
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10 or text.count("+") > 1:
        raise ValueError("Enter a 10-digit phone number, optionally prefixed with +1.")
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def format_email(string: str) -> str:
    """Validate a simple mailbox address while preserving its local-part case."""
    text = string.strip()
    if not text:
        return ""
    if re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", text) is None:
        raise ValueError("Enter an email address such as name@example.com.")
    local, domain = text.rsplit("@", 1)
    return f"{local}@{domain.lower()}"


def format_name(string: str) -> str:
    """Preserve names, including apostrophes, hyphens, initials, and accents."""
    return collapse_spaces(string)


def format_plain(string: str) -> str:
    """Trim outer whitespace while preserving paragraph breaks and indentation."""
    return string.replace("\r\n", "\n").replace("\r", "\n").strip()


def formatting(string: str, format_type: str | None = None) -> str:
    """Normalize a field or raise ValueError without changing the original input."""
    formatters: dict[str | None, Callable[[str], str]] = {
        "name": format_name,
        "phone": format_phone,
        "email": format_email,
        "money": format_money,
        "date": format_date,
        "paragraph": format_plain,
        "text": collapse_spaces,
        None: collapse_spaces,
    }
    try:
        formatter = formatters[format_type]
    except KeyError as error:
        raise ValueError(f"Unrecognized format type {format_type!r}.") from error
    return formatter(string)


def open_pdf(pdf_path: Path) -> None:
    """Ask the OS to open an existing PDF, separately from PDF generation."""
    path = pdf_path.expanduser().absolute()
    try:
        if not path.is_file():
            raise FileNotFoundError(path)
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform in {"darwin", "linux"}:
            command = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run(
                [command, str(path)], check=True, timeout=15, capture_output=True
            )
        else:
            raise OSError("Opening files is not supported on this platform.")
    except (OSError, subprocess.SubprocessError) as error:
        raise PdfOpenError(
            f"The PDF is saved at {path}, but could not be opened."
        ) from error
