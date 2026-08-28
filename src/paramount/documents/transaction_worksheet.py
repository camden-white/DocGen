"""Generate the transaction worksheet with XeLaTeX."""

from pathlib import Path
from tkinter import ttk
import argparse

from paramount.config import TEMPLATE_DIR, OUTPUT_DIR, AGENTS
from paramount.utils import open_pdf, render_latex, compile_pdf
from paramount.ui import window

TEMPLATE_PATH = TEMPLATE_DIR / "transaction_worksheet.tex"
OUTPUT_PATH = OUTPUT_DIR / "TransactionWorksheet.pdf"

FIELDS = (
    ("Agent Name", "name"),
    ("Property Street", "name"),
    ("City, State ZIP", "name"),
    ("Purchase Price", "money"),
    ("Date Accepted", "date"),
    ("Earnest Money", "money"),
    ("Earnest Money Due Date", "date"),
    ("Inspection Deadline", "date"),
    ("Closing Date", "date"),
    ("Possession Date", "date"),
    ("Concessions", "money"),
    ("Contingencies", "paragraph"),
    ("Home Warranty", "paragraph"),
    ("Inclusions & Exclusions", "paragraph"),
    ("Buyer Names", "name"),
    ("Seller Names", "name"),
    ("Buyer's Agent Name", "name"),
    ("Buyer's Agent Company", "name"),
    ("Buyer's Agent Phone", "phone"),
    ("Buyer's Agent Email", "email"),
    ("Lender Name", "name"),
    ("Lender Company", "name"),
    ("Lender Phone", "phone"),
    ("Lender Email", "email"),
    ("Loan Type", "name"),
    ("Escrow Contact Name", "name"),
    ("Escrow Company", "name"),
    ("Escrow Phone", "phone"),
    ("Escrow Email", "email"),
)

DROPDOWNS = {
    "Agent Name": tuple(AGENTS.keys())
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--logo",
        type=Path,
        help="Optional explicit path to logo.png.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_PATH,
        help=f"Output PDF path (default: {OUTPUT_PATH}).",
    )
    return parser.parse_args()

def main() -> None:

    root, entries = window(
        title="Transaction Worksheet",
        fields=FIELDS,
        dropdowns=DROPDOWNS,
    )

    def generate() -> None:
        entered_data: dict[str, str] = {key: value.get() for key, value in entries.items()}

        agent_name = entered_data["Agent Name"]

        implied_data: dict[str, str] = {
            "Agent Phone": AGENTS[agent_name]["phone"],
            "Agent Email": AGENTS[agent_name]["email"],
        }

        data = implied_data | entered_data

        compile_pdf(
            render_latex(template=TEMPLATE_PATH, data=data), 
            OUTPUT_PATH
        )

        open_pdf(OUTPUT_PATH)

    submit=ttk.Button(
        root,
        text="Generate PDF",
        command=generate,
    )

    submit.pack(pady=20)

    root.mainloop()


if __name__ == "__main__":
    main()
