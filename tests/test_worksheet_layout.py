"""Real compiler regressions for column fitting and readable failure modes."""

import os
from pathlib import Path

import pytest
from pypdf import PdfReader
from pypdf.generic import DictionaryObject

from docgen.config import Settings, initialize_settings, load_settings
from docgen.documents.transaction_worksheet import TERMS_FIELDS, generate
from docgen.errors import PdfCompilationError
from docgen.pdf import check_dependencies

pytestmark = pytest.mark.integration


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    configured = load_settings(
        initialize_settings(tmp_path / "settings", migrate=False)
    )
    problems = check_dependencies(configured.logo_path)
    if problems:
        if os.environ.get("DOCGEN_REQUIRE_PDF_TESTS") == "1":
            pytest.fail("; ".join(problems))
        pytest.skip("; ".join(problems))
    return configured


@pytest.fixture
def values(settings: Settings) -> dict[str, str]:
    return {
        "agent_name": next(iter(settings.agents)),
        "property_street": "123 Example Street",
        "city_state_zip": "Example, OR 97000",
        "purchase_price": "525000",
        "client_type": "Buyer",
        "client_names": "Alex Example",
        "financing_type": "Cash",
    }


@pytest.mark.parametrize(
    ("inclusions", "exclusions"),
    [
        (
            (
                "Kitchen refrigerator, range, dishwasher, washer and dryer, garage "
                "shelving, window coverings, and all existing light fixtures."
            ),
            (
                "Garage freezer, dining room chandelier, and wall-mounted television "
                "in the primary bedroom."
            ),
        ),
        (
            "Kitchen refrigerator\nWasher and dryer\nGarage shelving",
            "Dining room chandelier\nBedroom television",
        ),
        ("asdf qwer zxcv hjkl " * 8, "qwerty asdf zxcv " * 3),
    ],
)
def test_combined_terms_use_available_column_space(
    tmp_path: Path,
    settings: Settings,
    values: dict[str, str],
    inclusions: str,
    exclusions: str,
) -> None:
    # Each case exceeded the old fixed 12 mm allowance for the combined block.
    values.update(inclusions=inclusions, exclusions=exclusions)
    output = generate(values, settings, tmp_path / "worksheet.pdf")
    reader = PdfReader(output)
    assert len(reader.pages) == 1
    text = " ".join(reader.pages[0].extract_text().split())
    for content in (inclusions, exclusions):
        assert " ".join(content.split()) in text

    sizes: list[float] = []

    def record_font(
        text: str,
        cm: list[float],
        tm: list[float],
        font: DictionaryObject | None,
        size: float,
    ) -> None:
        if text.strip():
            sizes.append(size)

    reader.pages[0].extract_text(visitor_text=record_font)
    assert sizes and min(sizes) >= 9


@pytest.mark.parametrize(
    ("field", "section"),
    [
        ("client_names", "Contacts and financing"),
    ],
)
def test_real_column_overflow_is_named_and_keeps_previous_pdf(
    tmp_path: Path,
    settings: Settings,
    values: dict[str, str],
    field: str,
    section: str,
) -> None:
    values[field] = "Long text that cannot fit on this worksheet. " * 80
    output = tmp_path / "worksheet.pdf"
    output.write_bytes(b"previous document")
    with pytest.raises(PdfCompilationError, match=section) as caught:
        generate(values, settings, output, overwrite=True)
    assert "Check Setup" not in str(caught.value)
    assert "DOCGEN_LAYOUT_ERROR:" in (caught.value.details or "")
    assert output.read_bytes() == b"previous document"


def test_unbroken_terms_wrap_without_clipping(
    tmp_path: Path, settings: Settings, values: dict[str, str]
) -> None:
    values["inclusions"] = "qzx123" * 60
    output = generate(values, settings, tmp_path / "worksheet.pdf")
    reader = PdfReader(output)
    assert len(reader.pages) == 1
    assert values["inclusions"] in "".join(reader.pages[0].extract_text().split())


@pytest.mark.parametrize("fields", [("concessions",), TERMS_FIELDS])
def test_long_terms_shrink_below_nine_points_without_losing_text(
    tmp_path: Path,
    settings: Settings,
    values: dict[str, str],
    fields: tuple[str, ...],
) -> None:
    repetitions = 800
    paragraph = "Additional terms apply. " * repetitions
    assert len(paragraph) > 10_000
    values.update({field: paragraph for field in fields})
    output = generate(values, settings, tmp_path / "long-terms.pdf")
    reader = PdfReader(output)
    assert len(reader.pages) == 1
    page = reader.pages[0]
    text = " ".join(page.extract_text().split())
    assert text.count("Additional terms apply.") == repetitions * len(fields)

    term_sizes: list[float] = []
    fixed_sizes: list[float] = []

    def record_font(
        text: str,
        cm: list[float],
        tm: list[float],
        font: DictionaryObject | None,
        size: float,
    ) -> None:
        if "Additional terms" in text:
            term_sizes.append(size)
        if "PURCHASE PRICE" in text or "Alex Example" in text or "CONCESSIONS" in text:
            fixed_sizes.append(size)

    page.extract_text(visitor_text=record_font)
    assert term_sizes and 0 < min(term_sizes) < 9
    assert fixed_sizes and min(fixed_sizes) >= 9
