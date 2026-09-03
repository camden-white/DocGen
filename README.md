# DocGen

![macOS](https://img.shields.io/badge/macOS-000000?logo=apple&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-FCC624?logo=linux&logoColor=black)
![Windows](https://img.shields.io/badge/Windows-0078D4?logo=windows)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/GUI-Tkinter-3776AB?logo=python&logoColor=white)
![XeLaTeX](https://img.shields.io/badge/Typesetting-XeLaTeX-008080?logo=latex&logoColor=white)
![uv](https://img.shields.io/badge/Package%20Manager-uv-DE5FE9?logo=uv&logoColor=white)
![GNU Make](https://img.shields.io/badge/Build-GNU%20Make-A42E2B?logo=gnu&logoColor=white)
[![License](https://img.shields.io/badge/License-Apache%202.0-white?logo=apache&logoColor=white)](LICENSE)
![Status](https://img.shields.io/badge/Status-Active%20Development-2DA44E?logo=github&logoColor=white)
<!-- ![Ruff](https://img.shields.io/badge/Lint-Ruff-D7FF64?logo=ruff&logoColor=black)
![mypy](https://img.shields.io/badge/Types-mypy-2A6DB2)
![pytest](https://img.shields.io/badge/Tests-pytest-0A9EDC?logo=pytest&logoColor=white) -->

A simple application for generating PDF documents from LaTeX templates.

DocGen uses a lightweight **Tkinter** interface to receive user input, use that data to generate a LaTeX file from a template, and generate a finished PDF. It was originally developed for **Paramount Real Estate Services**, but the underlying system is general enough to be adapted for other businesses, organizations, or individuals.

## Features

- Simple desktop GUI built with Tkinter
- Generate PDFs from predefined templates
- Reuse common business information such as:
  - Company information
  - Agent names
  - Phone numbers
  - Email addresses
- Dropdown menus for predefined values
- Automatically opens generated PDFs
- Cross-platform support for Windows, macOS, and Linux
- Templates and business configuration can be customized without changing the core application
- No web server or internet connection required

## How It Works

DocGen follows a simple workflow:

1. Select the document to generate.
2. Enter the required information through the Tkinter interface.
3. Select predefined values such as an agent from dropdown menus.
4. DocGen fills the corresponding PDF template with entered data and implied data like phone numbers and emails of employees.
5. A completed PDF is generated and opened automatically.

The application separates document-generation logic from company-specific configuration so that the same system can be adapted for different users.

## Installation

Clone the repository
```bash
git clone https://github.com/<username>/docgen.git
cd docgen
```

Install the project dependencies and initialize the local configuration
```bash
make init
```
This creates any required local files that are intentionally excluded from version control such as config.toml

## Configuration

DocGen may require business-specific information such as company names, addresses, agents, phone numbers, and email addresses.

Sensitive or private configuration should **not** be committed to Git.

Instead, the repository can include a generic example configuration:

```text
config.example.toml
```

while the real local configuration is ignored:

```text
config.toml
```

For example:

```python
COMPANY_NAME = "Example Company"

AGENTS = {
    "Jane Doe": {
        "phone": "(555) 123-4567",
        "email": "jane@example.com",
    },
}
```

Running:

```bash
make init
```

can copy the example configuration when a local configuration does not already exist.

## Running DocGen

Start the application with:

```bash
make run
```

or directly with Python:

```bash
uv run python docgen
```

The Tkinter interface will open and prompt for the information required by the selected document.

## Project Structure

A typical project layout might look like:

```text
DocGen/
├── src/
│   └── docgen/
│       ├── main.py
│       ├── ui.py
│       ├── utils.py
│       ├── config.py
│       ├── config.toml
│       ├── logo.png
│       ├── assets/
│       │   ├── docgen.ico
│       │   └── docgen.icns
│       ├── documents/
│       │   ├── doc_alpha.py
│       │   └── doc_beta.py
│       └── examples/
│           ├── config.example.toml
│           └── logo.example.png
├── templates/
│   ├── doc_alpha.tex
│   └── doc_beta.tex
├── output/
├── Makefile
├── pyproject.toml
├── uv.lock
└── README.md
```

## Adding a New Document

To add another document type:

1. Add the LaTeX template to the templates directory.
2. Define the fields that need to be populated using the format `@@FOOBAR@@` for fields named "Foo Bar."
3. Add these to FIELDS at the top of your python document file.
4. Adjust other document-specific settings in the python document file such as `DISPLAY_NAME`, `FORMATS`, `DROPDOWNS`, or implied data in `generate()`.

## Customizing DocGen

Although DocGen was created for Paramount Real Estate Services, very little of the core application needs to be specific to real estate.

It can be adapted for tasks such as:

- Real estate forms
- Business letters
- Contracts
- Client documents
- Invoices
- Reports
- Applications
- Internal company forms
- Repetitive administrative paperwork

## Security

Do not commit confidential company or client information to the repository.

Files containing private configuration should be included in `.gitignore`, for example:

```gitignore
config.toml
logo.png
output/
```

Only generic example data should be stored in publicly accessible source code.

Generated documents may also contain sensitive client information, so the output directory should generally remain outside version control.

## Development

Useful development commands can be exposed through the Makefile:

```bash
make init
make build
make run
```

Development workflow:

```bash
uv version --bump patch
git add .
git commit -m "Release vx.y.z"
git tag vx.y.z
git push
git push --tags
```

## Requirements

- Python 3.14
- Tkinter
- A supported PDF generation/editing library
- macOS or Windows

Tkinter is included with many standard Python installations, although availability depends on how Python was installed.

## Roadmap

### Phase 1: Workable Application
- [x] Proof of concept terminal program to generate a PDF
- [x] Tkinter GUI to generate a PDF
- [x] Windows application
- [x] macOS application

### Phase 2: Replace File Management with UI
- [ ] GUI for editing config.toml
- [ ] Move config.toml and logo.png to Applicaiton Support so that translocated app can still run and files are not seen
- [ ] UI for adding and editing templates with LaTeX (each template has a "generate" and "edit" button)

### Phase 3: Version Updates and Improvements
- [ ] Perfect snap-formatting (dates, emails, etc.)
- [ ] Make config.toml -> config.py -> document.py -> template.tex variable pipeline non-dependent on precise naming conventions so that new data can be easily added
- [ ] Allow config.toml to add arbitrary data that is processed by config.py and allowed in future templates

## License

This project is licensed under the Apache License 2.0. See the [LICENSE](LICENSE) file for details.
