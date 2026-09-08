"""Generate and inspect a sample PDF using an installed wheel, outside the checkout."""

from pathlib import Path

from pypdf import PdfReader

from docgen.config import load_settings
from docgen.documents.transaction_worksheet import generate
from docgen.errors import PdfCompilationError


def main() -> None:
    """Check that installed templates, configuration, PDF compilation, and fonts work."""
    settings = load_settings()
    destination = Path.cwd() / "sample-worksheet.pdf"
    values = {
        "agent_name": next(iter(settings.agents)),
        "property_street": "123 Example Street",
        "city_state_zip": "Portland, OR 97201",
        "purchase_price": "$1,234.56",
        "client_type": "Buyer",
        "client_names": "Anne-Marie O\u2019Neill",
        "financing_type": settings.financing[0],
        "closing_date": "09/30/2026",
        "concessions": "First paragraph: 5% & costs.\n\nSecond paragraph: $100.",
    }
    try:
        output = generate(values, settings, destination)
    except PdfCompilationError as error:
        if error.details:
            print(error.details, flush=True)
        raise
    reader = PdfReader(output, strict=True)
    if len(reader.pages) != 1:
        raise RuntimeError("The installed worksheet must produce one PDF page.")
    text = reader.pages[0].extract_text()
    if "$1,234" not in text or "1,234.56" in text or "Example Street" not in text:
        raise RuntimeError("The generated PDF is missing expected sample values.")
    print("Installed worksheet compiled and validated as one page.")


if __name__ == "__main__":
    main()
