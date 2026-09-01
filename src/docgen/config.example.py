from pathlib import Path

OUTPUT_DIR = Path.home() / "Documents" # replace with desired path

PACKAGE_DIR = Path(__file__).resolve().parent # src/docgen/
DOCUMENT_DIR = PACKAGE_DIR / "documents"
IMAGE_DIR = PACKAGE_DIR / "images"
TEMPLATE_DIR = PACKAGE_DIR / "templates"

LOGO_PATH = IMAGE_DIR / "logo.png"

COMPANY_NAME = "Company Name Inc."
COMPANY_ADDRESS = "1234 Bussiness St NE, City, ST 12345"

AGENTS: dict[str, dict[str, str]] = {
    "Alice Aimes": {
        "phone": "(123) 456-7890",
        "email": "aliceaimes@example.com",
    },
    "Bob Brown": {
        "phone": "(234) 567-8901",
        "email": "bobbrown@example.com",
    },
    "Sam Smith": {
        "phone": "(345) 678-9012",
        "email": "samsmith@example.com",
    },
}
