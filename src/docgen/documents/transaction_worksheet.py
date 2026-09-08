"""Transaction worksheet schema and generation, independent of the GUI."""

from collections.abc import Mapping
from math import sqrt
from pathlib import Path

from ..config import TEMPLATE_DIR, Settings
from ..models import DocumentSpec, FieldSpec, validate_data
from ..pdf import compile_pdf, render_latex

DISPLAY_NAME = "Transaction Worksheet"
TEMPLATE_PATH = TEMPLATE_DIR / "transaction_worksheet.tex"
TERMS_FIELDS = (
    "concessions",
    "contingencies",
    "home_warranty",
    "inclusions",
    "exclusions",
)


def _terms_font_ceiling(data: Mapping[str, str]) -> str:
    """Bound the first measurement of very large terms to TeX's box dimensions.

    This is a generous initial ceiling, not the final font size. The template
    measures real line wrapping and selects the largest size that fits the page.
    Explicit paragraph breaks contribute linearly to height, so they receive a
    separate bound. Ordinary forms retain the normal 12-point starting size.
    """
    characters = sum(len(data[key]) for key in TERMS_FIELDS)
    line_breaks = sum(data[key].count("\n") for key in TERMS_FIELDS)
    ceiling = min(
        12.0, 12 * sqrt(2000 / max(2000, characters)), 400 / max(1, line_breaks)
    )
    return f"{ceiling:.8f}"


def get_document(settings: Settings) -> DocumentSpec:
    """Build the document's field schema from the current business configuration."""
    return DocumentSpec(
        key="transaction_worksheet",
        display_name=DISPLAY_NAME,
        fields=(
            FieldSpec(
                "agent_name",
                "Agent Name",
                "Property",
                required=True,
                choices=tuple(settings.agents),
            ),
            FieldSpec("property_street", "Property Street", "Property", required=True),
            FieldSpec("city_state_zip", "City, State ZIP", "Property", required=True),
            FieldSpec(
                "purchase_price", "Purchase Price", "Property", "money", required=True
            ),
            FieldSpec("date_accepted", "Date Accepted", "Deadlines", "date"),
            FieldSpec("earnest_money", "Earnest Money", "Deadlines", "money"),
            FieldSpec(
                "earnest_money_due_date", "Earnest Money Due Date", "Deadlines", "date"
            ),
            FieldSpec(
                "inspection_deadline", "Inspection Deadline", "Deadlines", "date"
            ),
            FieldSpec("closing_date", "Closing Date", "Deadlines", "date"),
            FieldSpec("possession_date", "Possession Date", "Deadlines", "date"),
            FieldSpec("concessions", "Concessions", "Terms", "paragraph"),
            FieldSpec("contingencies", "Contingencies", "Terms", "paragraph"),
            FieldSpec("home_warranty", "Home Warranty", "Terms", "paragraph"),
            FieldSpec("inclusions", "Inclusions", "Terms", "paragraph"),
            FieldSpec("exclusions", "Exclusions", "Terms", "paragraph"),
            FieldSpec(
                "client_type",
                "Client Type",
                "Client",
                required=True,
                choices=("Buyer", "Seller"),
            ),
            FieldSpec("client_names", "Client Names", "Client", "name", required=True),
            FieldSpec("client_phone", "Client Phone", "Client", "phone"),
            FieldSpec("client_email", "Client Email", "Client", "email"),
            FieldSpec(
                "counterparty_names", "Counterparty Names", "Counterparty", "name"
            ),
            FieldSpec(
                "counterparty_agent_name",
                "Counterparty Agent Name",
                "Counterparty",
                "name",
            ),
            FieldSpec(
                "counterparty_agent_company",
                "Counterparty Agent Company",
                "Counterparty",
            ),
            FieldSpec(
                "counterparty_agent_phone",
                "Counterparty Agent Phone",
                "Counterparty",
                "phone",
            ),
            FieldSpec(
                "counterparty_agent_email",
                "Counterparty Agent Email",
                "Counterparty",
                "email",
            ),
            FieldSpec(
                "financing_type",
                "Financing Type",
                "Financing",
                required=True,
                choices=settings.financing,
            ),
            FieldSpec("lender_name", "Lender Name", "Financing", "name"),
            FieldSpec("lender_company", "Lender Company", "Financing"),
            FieldSpec("lender_phone", "Lender Phone", "Financing", "phone"),
            FieldSpec("lender_email", "Lender Email", "Financing", "email"),
            FieldSpec("escrow_contact_name", "Escrow Contact Name", "Escrow", "name"),
            FieldSpec("escrow_company", "Escrow Company", "Escrow"),
            FieldSpec("escrow_phone", "Escrow Phone", "Escrow", "phone"),
            FieldSpec("escrow_email", "Escrow Email", "Escrow", "email"),
        ),
    )


def prepare_data(values: Mapping[str, str], settings: Settings) -> dict[str, str]:
    """Validate fields and derive company, agent, and counterparty information."""
    data = validate_data(values, get_document(settings).fields)
    agent = settings.agents[data["agent_name"]]
    return data | {
        "brokerage_name": settings.company_name,
        "brokerage_address": settings.company_address,
        "agent_phone": agent.phone,
        "agent_email": agent.email,
        "counterparty_type": "Buyer" if data["client_type"] == "Seller" else "Seller",
        "terms_font_ceiling": _terms_font_ceiling(data),
    }


def generate(
    values: Mapping[str, str],
    settings: Settings,
    output_pdf: Path,
    *,
    overwrite: bool = False,
) -> Path:
    """Validate, render, and save one worksheet without opening any UI or viewer."""
    data = prepare_data(values, settings)
    return compile_pdf(
        render_latex(TEMPLATE_PATH, data, breakable_fields=TERMS_FIELDS),
        output_pdf,
        logo_path=settings.logo_path,
        overwrite=overwrite,
        expected_pages=1,
    )
