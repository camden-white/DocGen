"""Package paths and constants"""

import sys
import tomllib
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent  # src/docgen/
PROJECT_DIR = PACKAGE_DIR.parent.parent
DOCUMENT_DIR = PACKAGE_DIR / "documents"
TEMPLATE_DIR = PACKAGE_DIR / "templates"
ASSET_DIR = PACKAGE_DIR / "assets"

FROZEN = getattr(sys, "frozen", False)

if FROZEN:
    executable = Path(sys.executable).resolve()

    app_bundle = next(
        (parent for parent in executable.parents if parent.suffix == ".app"),
        None,
    )

    APP_DIR = app_bundle.parent if app_bundle else executable.parent
else:
    APP_DIR = PACKAGE_DIR

CONFIG_PATH = APP_DIR / "config.toml"
LOGO_PATH = APP_DIR / "logo.png"
ICON_PATH = ASSET_DIR / "docgen.ico"

with CONFIG_PATH.open("rb") as file:
    config = tomllib.load(file)

# <========== config.toml ==========> #

OUTPUT_DIR = (
    Path(config["paths"]["output_dir"]).expanduser()
    if FROZEN
    else PROJECT_DIR / "output"
)

COMPANY_NAME: str = config["company"]["name"]
COMPANY_ADDRESS: str = config["company"]["address"]

AGENTS: dict[str, dict[str, str]] = config["agents"]
FINANCING: tuple[str, ...] = tuple(config["financing"])

# <=================================> #
