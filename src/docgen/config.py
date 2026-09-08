"""Explicit, validated loading and saving of per-user application settings."""

import os
import shutil
import sys
import tempfile
import tomllib
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import tomlkit
from platformdirs import user_config_path
from tomlkit.exceptions import ParseError

from .errors import ConfigurationError

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PACKAGE_DIR / "templates"
ASSET_DIR = PACKAGE_DIR / "assets"
ICON_PATH = ASSET_DIR / "docgen.ico"


@dataclass(frozen=True)
class Agent:
    """Contact information configured for one agent."""

    phone: str
    email: str


@dataclass(frozen=True)
class Settings:
    """Validated settings with absolute paths and immutable contact data."""

    config_path: Path
    output_dir: Path
    logo_path: Path
    company_name: str
    company_address: str
    agents: Mapping[str, Agent]
    financing: tuple[str, ...]


def default_config_path() -> Path:
    """Return the per-user config file, honoring ``DOCGEN_CONFIG_DIR``."""
    override = os.environ.get("DOCGEN_CONFIG_DIR")
    directory = (
        Path(override) if override else user_config_path("DocGen", appauthor=False)
    )
    return directory.expanduser().resolve() / "config.toml"


def _config_path(path: Path | None) -> Path:
    return default_config_path() if path is None else path.expanduser().resolve()


def _table(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ConfigurationError(f"Configuration '{name}' must be a TOML table.")
    table = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in table):
        raise ConfigurationError(f"Configuration '{name}' must be a TOML table.")
    return cast(dict[str, object], table)


def _string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Configuration '{name}' must be a nonempty string.")
    if "\x00" in value:
        raise ConfigurationError(
            f"Configuration '{name}' contains an invalid character."
        )
    return value.strip()


def _resolve_path(value: object, name: str, config_dir: Path) -> Path:
    path = Path(_string(value, name)).expanduser()
    return (path if path.is_absolute() else config_dir / path).resolve()


def _parse_settings(text: str, path: Path) -> Settings:
    try:
        data: dict[str, object] = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        # Location attributes were added in Python 3.14; older stubs omit them.
        line: object = getattr(error, "lineno", None)
        column: object = getattr(error, "colno", None)
        detail = (
            f" at line {line}, column {column}."
            if isinstance(line, int) and isinstance(column, int)
            else f": {error}"
        )
        raise ConfigurationError(f"Invalid TOML in {path}{detail}") from error

    paths = _table(data.get("paths"), "paths")
    company = _table(data.get("company"), "company")
    raw_agents = _table(data.get("agents"), "agents")
    if not raw_agents:
        raise ConfigurationError("Configure at least one agent in the 'agents' table.")

    agents: dict[str, Agent] = {}
    for name, entry in raw_agents.items():
        clean_name = _string(name, "agent name")
        if clean_name in agents:
            raise ConfigurationError(
                "Agent names must be unique after trimming whitespace."
            )
        agent = _table(entry, "agent")
        agents[clean_name] = Agent(
            phone=_string(agent.get("phone"), "agent.phone"),
            email=_string(agent.get("email"), "agent.email"),
        )

    raw_financing = data.get("financing")
    if not isinstance(raw_financing, list) or not raw_financing:
        raise ConfigurationError("Configuration 'financing' must be a nonempty array.")
    financing = tuple(
        _string(value, "financing option")
        for value in cast(list[object], raw_financing)
    )
    if len(financing) != len(set(financing)):
        raise ConfigurationError("Financing options must be unique.")

    output_dir = _resolve_path(paths.get("output_dir"), "paths.output_dir", path.parent)
    if output_dir.exists() and not output_dir.is_dir():
        raise ConfigurationError(
            "Configuration 'paths.output_dir' must name a directory."
        )
    logo_path = _resolve_path(
        paths.get("logo_path", "logo.png"), "paths.logo_path", path.parent
    )
    if not logo_path.is_file():
        raise ConfigurationError(f"The configured logo file was not found: {logo_path}")

    return Settings(
        config_path=path,
        output_dir=output_dir,
        logo_path=logo_path,
        company_name=_string(company.get("name"), "company.name"),
        company_address=_string(company.get("address"), "company.address"),
        agents=MappingProxyType(agents),
        financing=financing,
    )


def load_settings(path: Path | None = None) -> Settings:
    """Read and validate TOML; resolve relative paths beside the config file."""
    resolved_path = _config_path(path)
    try:
        text = resolved_path.read_text(encoding="utf-8")
        return _parse_settings(text, resolved_path)
    except FileNotFoundError as error:
        raise ConfigurationError(
            f"Configuration was not found: {resolved_path}. Open Settings to initialize it."
        ) from error
    except UnicodeError as error:
        raise ConfigurationError("Configuration must be a UTF-8 text file.") from error
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            f"Could not read configuration: {resolved_path}"
        ) from error


def _legacy_directories() -> tuple[Path, ...]:
    directories = [PACKAGE_DIR]
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        bundle = next(
            (parent for parent in executable.parents if parent.suffix == ".app"), None
        )
        directories.insert(0, bundle.parent if bundle else executable.parent)
    return tuple(directories)


def _copy_if_missing(
    source: Path, destination: Path, *, text: str | None = None
) -> bool:
    """Copy a new private file without replacing an existing destination."""
    try:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    try:
        with os.fdopen(descriptor, "wb") as target:
            if text is None:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, target)
            else:
                target.write(text.encode("utf-8"))
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return True


def _migration_text(source: Path) -> str:
    """Keep legacy path references stable while retaining TOML formatting."""
    try:
        document = cast(
            MutableMapping[str, object],
            tomlkit.parse(source.read_text(encoding="utf-8")),
        )
    except ParseError as error:
        raise ConfigurationError(
            f"Invalid TOML in legacy configuration: {source}"
        ) from error
    paths = document.get("paths")
    if isinstance(paths, MutableMapping):
        # TOML table keys are strings; values still require runtime validation.
        paths = cast(MutableMapping[str, object], paths)
        for key in ("output_dir", "logo_path"):
            value = paths.get(key)
            if isinstance(value, str) and value.strip():
                reference = Path(value.strip()).expanduser()
                if not reference.is_absolute():
                    paths[key] = str((source.parent / reference).resolve())
    return tomlkit.dumps(document)


def initialize_settings(
    config_dir: Path | None = None, *, migrate: bool = True
) -> Path:
    """Create settings/examples or copy legacy files, never replacing user files.

    Initialization is explicit so importing the package or loading settings never
    writes to the user's application directory. Legacy originals, comments, and
    unknown keys are preserved. Relative legacy paths become absolute references
    to their original directory; a default logo is copied beside the new config.
    """
    config_path = (
        default_config_path()
        if config_dir is None
        else config_dir.expanduser().resolve() / "config.toml"
    )
    examples = PACKAGE_DIR / "examples"
    legacy = (
        next(
            (
                directory
                for directory in _legacy_directories()
                if (directory / "config.toml").is_file()
            ),
            None,
        )
        if migrate
        else None
    )
    config_source = (
        legacy / "config.toml" if legacy else examples / "config.example.toml"
    )
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        migrated_text = (
            _migration_text(config_source)
            if legacy is not None and not config_path.exists()
            else None
        )
        _copy_if_missing(config_source, config_path, text=migrated_text)
        logo_source = (
            legacy / "logo.png"
            if legacy is not None and (legacy / "logo.png").is_file()
            else examples / "logo.example.png"
        )
        _copy_if_missing(logo_source, config_path.parent / "logo.png")
    except (OSError, UnicodeError, ValueError) as error:
        raise ConfigurationError(
            f"Could not initialize settings in {config_path.parent}."
        ) from error
    return config_path


def save_settings_text(text: str, path: Path | None = None) -> Settings:
    """Validate and atomically save UTF-8 TOML, preserving comments and unknown keys."""
    resolved_path = _config_path(path)
    temporary_path: Path | None = None
    try:
        settings = _parse_settings(text, resolved_path)
        resolved_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=resolved_path.parent,
            prefix=".docgen-",
            suffix=".toml",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(text)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, resolved_path)
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            f"Could not save configuration: {resolved_path}"
        ) from error
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return settings


def update_settings_paths(
    text: str, *, output_dir: Path | None = None, logo_path: Path | None = None
) -> str:
    """Update selected TOML paths without saving or discarding comments/other keys.

    Relative paths retain their supplied form and are interpreted beside the
    configuration file when subsequently validated by :func:`save_settings_text`.
    """
    try:
        document = cast(MutableMapping[str, object], tomlkit.parse(text))
    except ParseError as error:
        raise ConfigurationError(
            "Fix the invalid TOML before choosing paths."
        ) from error
    paths = document.get("paths")
    if paths is None:
        paths = tomlkit.table()
        document["paths"] = paths
    if not isinstance(paths, MutableMapping):
        raise ConfigurationError("Configuration 'paths' must be a TOML table.")
    paths = cast(MutableMapping[str, object], paths)
    for key, value in (("output_dir", output_dir), ("logo_path", logo_path)):
        if value is not None:
            paths[key] = str(value)
    return tomlkit.dumps(document)
