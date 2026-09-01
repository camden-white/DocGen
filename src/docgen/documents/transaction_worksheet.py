"""Generate the transaction worksheet with XeLaTeX."""

from tkinter import ttk

from docgen.config import COMPANY_NAME, COMPANY_ADDRESS, TEMPLATE_DIR, OUTPUT_DIR, AGENTS
from docgen.utils import open_pdf, render_latex, compile_pdf
from docgen.ui import window

TEMPLATE_PATH = TEMPLATE_DIR / "transaction_worksheet.tex"
OUTPUT_PATH = OUTPUT_DIR / "TransactionWorksheet.pdf"

FIELDS: tuple[str, ...] = (
    "Agent Name",
    "Property Street",
    "City, State ZIP",
    "Purchase Price",
    "Date Accepted",
    "Earnest Money",
    "Earnest Money Due Date",
    "Inspection Deadline",
    "Closing Date",
    "Possession Date",
    "Concessions",
    "Contingencies",
    "Home Warranty",
    "Inclusions",
    "Exclusions",
    "Client Type",
    "Client Names",
    "Client Phone",
    "Client Email",
    "Counterparty Names",
    "Counterparty Agent Name",
    "Counterparty Agent Company",
    "Counterparty Agent Phone",
    "Counterparty Agent Email",
    "Lender Name",
    "Lender Company",
    "Lender Phone",
    "Lender Email",
    "Loan Type",
    "Escrow Contact Name",
    "Escrow Company",
    "Escrow Phone",
    "Escrow Email",
)

FORMATS: dict[str, str] = {
    "Client Names" : "name",
    "Counterparty Names" : "name",
    "Counterparty Agent Name" : "name",
    "Lender Name" : "name",
    "Escrow Contact Name" : "name",
    "Purchase Price": "money",
    "Earnest Money": "money",
    "Date Accepted": "date",
    "Earnest Money Due Date": "date",
    "Inspection Deadline": "date",
    "Closing Date": "date",
    "Possession Date": "date",
    "Client Phone": "phone",
    "Counterparty Agent Phone": "phone",
    "Lender Phone": "phone",
    "Escrow Phone": "phone",
    "Client Email": "email",
    "Counterparty Agent Email": "email",
    "Lender Email": "email",
    "Escrow Email": "email",
}

DROPDOWNS: dict[str, tuple[str, ...]] = {
    "Agent Name": tuple(AGENTS.keys()),
    "Client Type": ("Buyer", "Seller"),
}

def main() -> None:

    root, entries = window(
        title="Transaction Worksheet",
        fields=FIELDS,
        formats=FORMATS,
        dropdowns=DROPDOWNS,
    )

    def generate() -> None:
        entered_data: dict[str, str] = {key: value.get() for key, value in entries.items()}

        agent_name = entered_data["Agent Name"]
        counterparty_type = "Buyer" if entered_data["Client Type"] == "Seller" else "Seller"

        implied_data: dict[str, str] = {
            "Brokerage Name": COMPANY_NAME,
            "Brokerage Address": COMPANY_ADDRESS,
            "Agent Phone": AGENTS[agent_name]["phone"],
            "Agent Email": AGENTS[agent_name]["email"],
            "Counterparty Type": counterparty_type,
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
