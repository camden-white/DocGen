# DocGen

![Release](https://img.shields.io/github/v/release/camden-white/DocGen?logo=github&color=6F42C1)
![Status](https://img.shields.io/badge/Status-Active%20Development-2DA44E?logo=github&logoColor=white)
[![License](https://img.shields.io/badge/License-Apache%202.0-white?logo=apache&logoColor=white)](LICENSE)

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Tkinter](https://img.shields.io/badge/Tkinter-3776AB?logo=python&logoColor=white)
![XeLaTeX](https://img.shields.io/badge/XeLaTeX-008080?logo=latex&logoColor=white)
![Config](https://img.shields.io/badge/TOML-9C4121?logo=toml&logoColor=white)
![uv](https://img.shields.io/badge/uv-DE5FE9?logo=uv&logoColor=white)
![ty](https://img.shields.io/badge/ty-261230?logo=ty&logoColor=white)
![Ruff](https://img.shields.io/badge/ruff-D7FF64?logo=ruff&logoColor=black)
![GNU Make](https://img.shields.io/badge/GNU%20Make-A42E2B?logo=gnu&logoColor=white)

DocGen is a local desktop application that turns a transaction worksheet form into a PDF using Tkinter and XeLaTeX. Company settings remain separate from the application, and document generation runs in the background so the form stays responsive.

## Using the application

1. Open DocGen and review the first-run company settings. Existing configuration can be updated through **Settings**.
2. Complete the grouped form. Required fields are marked; invalid values receive inline explanations and remain available for correction.
3. Choose **Generate PDF**, select a destination, and confirm before replacing an existing file.
4. The application opens the saved PDF. If the viewer cannot open it, the saved file remains available at the reported location.

Use **Save Draft** and **Open Draft** to continue unfinished forms later. The shortcuts are Command-S / Command-O on macOS and Control-S / Control-O elsewhere. Drafts preserve incomplete input, including values that still need correction. Closing a changed form prompts before discarding work.

Money fields display whole US dollars with comma separators; any cents are discarded without rounding (for example, `$1,234.99` becomes `$1,234`). Negative amounts and malformed input remain invalid. Dates must be real calendar dates. Names retain punctuation and paragraph fields retain paragraph breaks.

Concessions, Contingencies, Home Warranty, and Inclusions & Exclusions share the space available in the terms column. Long terms automatically shrink below 9 points as needed to keep the worksheet on one page, without clipping or truncating the text. Terms have no fixed character limit, and long unbroken tokens receive invisible wrapping opportunities. Very long entries can produce very small print. Headings retain their size; other field rows and contact information keep their 9-point minimum. Compilation still has a timeout and remains subject to TeX and system resource limits; draft files retain their 2 MiB size limit.

PDFs, drafts, and company settings can contain private information. Drafts are plain JSON, not encrypted. Keep them in an appropriate local folder; no service or account is needed to generate documents.

## Requirements

- Python **3.14** for source installations; development and CI select **3.14.7**.
- A Python installation with working **Tkinter** and a graphical desktop.
- **XeLaTeX**, installed separately even for packaged desktop applications.
- LaTeX packages used by the template: `geometry`, `fontspec`, `graphicx`, `xcolor`, and `etoolbox`.
- TeX Gyre Heros fonts (`texgyreheros-regular.otf` and `texgyreheros-bold.otf`); no Microsoft Office installation is required.

[MacTeX](https://www.tug.org/mactex/), [TeX Live](https://www.tug.org/texlive/), and [MiKTeX](https://miktex.org/) provide XeLaTeX. On Windows, finish installing required packages before starting DocGen; interactive package-install prompts cannot be answered from the PDF worker.

Desktop release builds target Windows and macOS. Linux is exercised in CI from source with a virtual display. The release workflow does not sign or notarize the desktop applications; distributing signed builds requires platform signing credentials and an additional signing/notarization step.

## Install from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), Git, and the requirements above, then run:

```sh
git clone https://github.com/camden-white/DocGen.git
cd DocGen
uv sync --locked
uv run --locked docgen
```

The equivalent Make commands are `make install` and `make run`. The first launch initializes settings and opens them for review. Make is optional; each command is an ordinary uv invocation, so Windows users can use PowerShell directly.

If the selected Python lacks Tkinter, install a Tk-capable interpreter and explicitly select it with `uv sync --locked --python /path/to/python3.14`. On a Homebrew installation of macOS Python, install the matching `python-tk@3.14` formula and select that Homebrew interpreter. Verify the environment using:

```sh
uv run --locked python -c "import tkinter; print(tkinter.TkVersion)"
uv run --locked docgen --smoke-test
uv run --locked docgen --check
```

`--smoke-test` opens and closes the application for installation testing. `--check` prints JSON dependency diagnostics and returns a nonzero status when PDF dependencies are missing. Neither command needs real company information. To also check a specific configuration and logo, use `docgen --config /path/to/config.toml --check`.

## Configuration and migration

Settings live in the platform's per-user configuration directory:

| Platform | Default directory |
| --- | --- |
| macOS | `~/Library/Application Support/DocGen` |
| Windows | `%LOCALAPPDATA%\DocGen` |
| Linux | `~/.config/DocGen` (honoring `XDG_CONFIG_HOME`) |

The directory contains `config.toml` and `logo.png`. The application never needs to write inside its installed package or application bundle. Set `DOCGEN_CONFIG_DIR` to override the directory, or use `docgen --config /path/to/config.toml` to select one configuration explicitly. Initialization of a custom directory requires the filename `config.toml`.

`docgen --init-config` (or `make init`) initializes settings without opening the application. It copies legacy configuration and logos from the old package or release location when available; otherwise it copies the bundled generic examples. Existing destination files and legacy originals are preserved. After using this command, open **Settings** to review the initialized configuration before generating documents. Relative paths in configuration resolve beside the configuration file; `~` expands to the user's home directory. The output-directory setting applies in both source and packaged runs.

Example TOML:

```toml
financing = ["Conventional", "FHA", "VA", "USDA", "Cash"]

[paths]
output_dir = "~/Documents"
logo_path = "logo.png"

[company]
name = "Example Company"
address = "123 Example Street, Portland, OR 97201"

[agents."Jane Doe"]
phone = "(503) 555-0123"
email = "jane@example.com"
```

Settings are validated before saving. The Settings editor preserves the TOML text, comments, and additional keys. At least one agent and one financing option are required. An existing logo file is required.

## Development

The project uses a `src` layout, uv for environments and locking, `uv_build` for Python packaging, Ruff for lint/format checks, ty, strict Pyright, and strict mypy for type checking, pytest for behavior tests, and PyInstaller for desktop bundles. `pyproject.toml` is the source of package metadata and `uv.lock` records exact dependency versions.

`make type` runs ty, Pyright, and mypy against application code, scripts, and tests. Mypy targets Python 3.14 and runs from the locked development environment; use `uv run --locked mypy` rather than a global installation to avoid interpreter or dependency mismatches. Pyright provides Pylance-compatible diagnostics and uses the strict settings in `pyproject.toml` for application code, scripts, and tests. In VS Code, select the project's `.venv` interpreter so Pylance sees the locked dependencies. Pyright's Python wrapper uses an available Node.js installation or provisions its own runtime. JSON/TOML data is treated as unvalidated `object` until checked; narrow casts describe validated data and Tk APIs with incomplete upstream stubs. Tests may exercise private helpers, but retain all strict type checks.

| Command | Purpose |
| --- | --- |
| `make install` | Install the locked development environment |
| `make check` | Verify the lock, lint, formatting, types, and unit tests |
| `make fix` | Apply Ruff's safe fixes and formatting |
| `make test` | Run tests without requiring a desktop or XeLaTeX |
| `make smoke` | Verify that the application opens and closes |
| `make diagnostics` | Report PDF dependency availability |
| `make package-check` | Audit wheel/sdist contents and test a clean wheel installation |
| `make build` | Build the native application for the current platform |
| `make run-build` | Run the native application |
| `make upgrade` | Deliberately refresh dependencies, sync, and run checks |

Ordinary environment commands use `--locked`, so they fail if project metadata and the lockfile disagree. Distribution builds first run `uv lock --check`, since `uv build` does not accept `--locked`. After intentionally changing dependencies, run `uv lock`, inspect the diff, then `uv sync --locked` and `make check`. CI pins uv to **0.12.10**. Ruff rules extend the defaults with import sorting, modernization, simplification, and Ruff-specific checks. Broad unsafe automatic fixes are intentionally excluded.

Tests with external requirements are opt-in locally:

```sh
# A graphical session is required.
DOCGEN_RUN_GUI=1 uv run --locked pytest -m gui

# Fail, rather than skip, if PDF dependencies are unavailable.
DOCGEN_REQUIRE_PDF_TESTS=1 uv run --locked pytest -m integration

# Verify actual installed resources, GUI, and sample PDF compilation.
uv run --locked python scripts/check_package.py --gui --pdf
```

The environment-variable syntax above is for POSIX shells; in PowerShell use `$env:DOCGEN_RUN_GUI = "1"` or `$env:DOCGEN_REQUIRE_PDF_TESTS = "1"` before the corresponding command. Linux CI installs TeX and Tk, uses Xvfb, and requires integration dependencies. CI checks include a clean wheel installation from outside the checkout, not only the editable development environment.

### Architecture and adding documents

```text
src/docgen/
├── main.py                  # CLI and startup; no GUI import for headless commands
├── config.py                # typed settings, validation, migration, atomic save
├── models.py                # FieldSpec, DocumentSpec, complete-form validation
├── ui.py                    # one Tk root, forms, worker coordination, dialogs
├── settings_dialog.py       # configuration editor
├── drafts.py                # versioned JSON drafts
├── utils.py                 # plain-text parsing and formatting
├── pdf.py                   # LaTeX escaping, rendering, compilation, verification
├── documents/               # explicit document catalog and pure generators
├── templates/               # packaged LaTeX templates
├── examples/                # generic configuration and logo
└── assets/                  # application icons
scripts/                     # builds, artifact audits, release commands
tests/                      # unit, integration, GUI, and release regression tests
```

A field's stable key is independent of its display label. For example:

```python
from docgen.models import FieldSpec

purchase_price = FieldSpec(
    key="purchase_price",
    label="Purchase Price",
    section="Property",
    kind="money",
    required=True,
)
```

Reference it in LaTeX as `@@purchase_price@@`. Rendering escapes plain text and substitutes placeholders in a single pass. Never insert unescaped user text or perform another replacement pass on a rendered template.

To add a document, define `get_document(settings) -> DocumentSpec`, a generator accepting plain values, settings, and an output path, and a template with matching explicit keys. Register the document in `documents/__init__.py` and add its template to the public resource allowlist in `scripts/build_app.py`. The current UI opens the transaction worksheet directly; supporting another document also requires adding document selection and generator dispatch in `ui.py`. Include validation, rendering, and representative real-PDF tests. Keep generators independent of Tkinter and PDF viewers.

### Packaging and release

`make build` and the release workflow both call `scripts/build_app.py`. Its explicit resource allowlist includes only generic examples, templates, and icons; package metadata is copied so version reporting works in frozen builds. PyInstaller's generated spec stays under `build/`; the maintained build script is the authoritative configuration.

`make package` writes the wheel and source archive to `dist/packages`. `make package-check` uses temporary artifacts and a fresh virtual environment, installs dependencies with hashes exported from the lock, and verifies public archive contents. Private `config.toml`, `logo.png`, and `.DS_Store` files are excluded independently of Git ignore rules and rejected by the artifact audit. Add new public resources to the audits as needed.

Prepare and publish are separate operations:

```sh
# Begin with reviewed, committed changes and a clean working tree.
make prepare-release BUMP=patch

# Review version files and rerun checks before committing.
git diff -- pyproject.toml uv.lock
make check
git add pyproject.toml uv.lock
git commit -m "Bump version to X.Y.Z"
git tag -a vX.Y.Z -m "DocGen vX.Y.Z"

# Validate and explicitly confirm publication of this exact tag.
make publish TAG=vX.Y.Z
```

Replace `X.Y.Z` with the version produced by preparation. `prepare-release` only edits version metadata and the lock; it does not commit, tag, or push. `publish` requires a clean checkout, a matching annotated tag at HEAD, and an explicit yes. It pushes only that tag to `origin`, without publishing other tags or branches.

A tag starts the release workflow. Checks must pass before Windows and macOS build independently. Each build verifies its installed wheel, GUI, frozen executable, and archive contents. Only after both succeed does one final job publish the two archives together. GitHub Actions are pinned to verified commit SHAs; Dependabot proposes dependency and action updates. Release signing and notarization are not configured.

## License

Licensed under [Apache License 2.0](LICENSE).
