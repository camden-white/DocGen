"""Configuration parsing, migration, and persistence must not lose user data."""

import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from docgen import config
from docgen.errors import ConfigurationError

EXAMPLE = """\
financing = ["Conventional", "Cash"]

[paths]
output_dir = "output"

[company]
name = "Example Company"
address = "123 Example Street"

[agents."Anne-Marie O'Neill"]
phone = "+1 (503) 555-0123"
email = "anne@example.com"
"""


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Keep every configuration read/write isolated from the user's home."""
    path = tmp_path / "settings" / "config.toml"
    path.parent.mkdir()
    path.write_text(EXAMPLE, encoding="utf-8")
    (path.parent / "logo.png").write_bytes(b"test logo")
    return path


@pytest.fixture
def legacy_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    package = tmp_path / "package"
    examples = package / "examples"
    examples.mkdir(parents=True)
    (examples / "config.example.toml").write_text(EXAMPLE, encoding="utf-8")
    (examples / "logo.example.png").write_bytes(b"example logo")
    monkeypatch.setattr(config, "PACKAGE_DIR", package)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    return package


def test_import_does_not_read_or_initialize_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_directory = tmp_path / "not-created"
    monkeypatch.setenv("DOCGEN_CONFIG_DIR", str(missing_directory))
    subprocess.run(
        [sys.executable, "-c", "import docgen.config"],
        check=True,
        capture_output=True,
        timeout=20,
    )
    assert not missing_directory.exists()


def test_default_config_path_honors_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOCGEN_CONFIG_DIR", str(tmp_path / "custom"))
    assert config.default_config_path() == tmp_path / "custom" / "config.toml"


def test_default_config_path_uses_platform_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DOCGEN_CONFIG_DIR", raising=False)

    def platform_directory(appname: str, *, appauthor: bool) -> Path:
        assert appname == "DocGen"
        assert appauthor is False
        return tmp_path / "user-config"

    monkeypatch.setattr(config, "user_config_path", platform_directory)
    assert config.default_config_path() == tmp_path / "user-config" / "config.toml"


def test_relative_paths_resolve_beside_configuration(
    config_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = config.load_settings(config_path)
    assert settings.config_path == config_path
    assert settings.output_dir == config_path.parent / "output"
    assert settings.logo_path == config_path.parent / "logo.png"
    assert settings.agents["Anne-Marie O'Neill"].phone == "+1 (503) 555-0123"
    assert settings.financing == ("Conventional", "Cash")
    assert not settings.output_dir.exists()


def test_custom_logo_path_is_supported(config_path: Path) -> None:
    logo = config_path.parent / "branding" / "company.png"
    logo.parent.mkdir()
    logo.write_bytes(b"custom logo")
    text = EXAMPLE.replace(
        'output_dir = "output"',
        'output_dir = "output"\nlogo_path = "branding/company.png"',
    )
    config_path.write_text(text, encoding="utf-8")
    assert config.load_settings(config_path).logo_path == logo


def test_settings_agent_mapping_is_immutable(config_path: Path) -> None:
    settings = config.load_settings(config_path)
    assert not hasattr(settings.agents, "__setitem__")


def test_missing_config_gives_actionable_error_without_initializing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "missing" / "config.toml"
    with pytest.raises(ConfigurationError, match="Open Settings"):
        config.load_settings(path)
    assert not path.parent.exists()


def test_parser_error_without_location_attributes_remains_readable(
    config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(tomllib.TOMLDecodeError) as parsed:
        tomllib.loads('value = "unfinished')
    error = parsed.value
    monkeypatch.delattr(error, "lineno", raising=False)
    monkeypatch.delattr(error, "colno", raising=False)

    def fail_loads(text: str) -> dict[str, object]:
        raise error

    monkeypatch.setattr(tomllib, "loads", fail_loads)
    with pytest.raises(ConfigurationError, match="Unterminated string"):
        config.load_settings(config_path)


def test_malformed_toml_reports_location_without_contents(config_path: Path) -> None:
    config_path.write_text('private_token = "DO_NOT_DISPLAY', encoding="utf-8")
    with pytest.raises(ConfigurationError, match=r"Invalid TOML.*line") as caught:
        config.load_settings(config_path)
    assert "DO_NOT_DISPLAY" not in str(caught.value)


@pytest.mark.parametrize(
    ("old", "new", "error"),
    [
        ('financing = ["Conventional", "Cash"]', 'financing = "Cash"', "financing"),
        ('financing = ["Conventional", "Cash"]', "financing = []", "financing"),
        (
            'financing = ["Conventional", "Cash"]',
            'financing = ["Cash", "Cash"]',
            "unique",
        ),
        (
            'financing = ["Conventional", "Cash"]',
            "financing = [true]",
            "financing option",
        ),
        ('output_dir = "output"', "output_dir = 42", "paths.output_dir"),
        ('name = "Example Company"', 'name = " "', "company.name"),
        ('address = "123 Example Street"', "address = false", "company.address"),
        ('phone = "+1 (503) 555-0123"', "phone = 5035550123", "agent.phone"),
        ('email = "anne@example.com"', 'email = ""', "agent.email"),
        ('[agents."Anne-Marie O\'Neill"]', "[staff]", "agents"),
    ],
)
def test_wrong_structure_is_rejected(
    config_path: Path, old: str, new: str, error: str
) -> None:
    config_path.write_text(EXAMPLE.replace(old, new), encoding="utf-8")
    with pytest.raises(ConfigurationError, match=error):
        config.load_settings(config_path)


def test_output_path_must_not_be_a_file(config_path: Path) -> None:
    (config_path.parent / "output").write_text("not a directory", encoding="utf-8")
    with pytest.raises(ConfigurationError, match="directory"):
        config.load_settings(config_path)


def test_missing_logo_is_reported(config_path: Path) -> None:
    (config_path.parent / "logo.png").unlink()
    with pytest.raises(ConfigurationError, match="logo file was not found"):
        config.load_settings(config_path)


def test_initialization_uses_examples_without_migration(
    tmp_path: Path, legacy_package: Path
) -> None:
    (legacy_package / "config.toml").write_text("legacy = true", encoding="utf-8")
    result = config.initialize_settings(tmp_path / "new", migrate=False)
    assert result.read_text(encoding="utf-8") == EXAMPLE
    assert result.with_name("logo.png").read_bytes() == b"example logo"
    assert config.load_settings(result).company_name == "Example Company"


def test_migration_preserves_original_files(
    tmp_path: Path, legacy_package: Path
) -> None:
    original = "# Keep this comment\ncustom_key = 123\n" + EXAMPLE.replace(
        "Example Company", "Legacy Company"
    )
    original_config = legacy_package / "config.toml"
    original_logo = legacy_package / "logo.png"
    original_config.write_text(original, encoding="utf-8")
    original_logo.write_bytes(b"legacy logo")
    result = config.initialize_settings(tmp_path / "new")
    migrated_text = result.read_text(encoding="utf-8")
    assert migrated_text.startswith("# Keep this comment\ncustom_key = 123\n")
    assert config.load_settings(result).output_dir == legacy_package / "output"
    assert config.load_settings(result).company_name == "Legacy Company"
    assert result.with_name("logo.png").read_bytes() == b"legacy logo"
    assert original_config.read_text(encoding="utf-8") == original
    assert original_logo.read_bytes() == b"legacy logo"


def test_initialization_never_overwrites_existing_files(
    config_path: Path, legacy_package: Path
) -> None:
    (legacy_package / "config.toml").write_text("legacy = true", encoding="utf-8")
    (legacy_package / "logo.png").write_bytes(b"legacy logo")
    config.initialize_settings(config_path.parent)
    assert config_path.read_text(encoding="utf-8") == EXAMPLE
    assert config_path.with_name("logo.png").read_bytes() == b"test logo"


def test_frozen_macos_migration_uses_directory_beside_bundle(
    tmp_path: Path, legacy_package: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    distribution = tmp_path / "distribution"
    executable = distribution / "DocGen.app" / "Contents" / "MacOS" / "DocGen"
    executable.parent.mkdir(parents=True)
    executable.touch()
    (distribution / "config.toml").write_text(EXAMPLE, encoding="utf-8")
    (distribution / "logo.png").write_bytes(b"external logo")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    result = config.initialize_settings(tmp_path / "new")
    assert config.load_settings(result).output_dir == distribution / "output"
    assert result.with_name("logo.png").read_bytes() == b"external logo"


@pytest.mark.parametrize(
    "paths_text",
    [
        '[paths]\noutput_dir = "output"\nlogo_path = "branding/custom.png"',
        'paths = { output_dir = "output", logo_path = "branding/custom.png" }',
        'paths.output_dir = "output"\npaths.logo_path = "branding/custom.png"',
    ],
)
def test_migration_preserves_references_with_varied_toml_layouts(
    tmp_path: Path, legacy_package: Path, paths_text: str
) -> None:
    original = EXAMPLE.replace('[paths]\noutput_dir = "output"', paths_text)
    logo = legacy_package / "branding" / "custom.png"
    logo.parent.mkdir()
    logo.write_bytes(b"custom legacy logo")
    (legacy_package / "config.toml").write_text(original, encoding="utf-8")
    migrated = config.initialize_settings(tmp_path / "new")
    settings = config.load_settings(migrated)
    assert settings.logo_path == logo
    assert settings.output_dir == legacy_package / "output"
    assert (legacy_package / "config.toml").read_text(encoding="utf-8") == original


def test_partial_migration_recovers_legacy_logo_on_retry(
    tmp_path: Path, legacy_package: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (legacy_package / "config.toml").write_text(EXAMPLE, encoding="utf-8")
    (legacy_package / "logo.png").write_bytes(b"legacy logo")
    with monkeypatch.context() as patch:

        def fail_copy(*args: object, **kwargs: object) -> None:
            raise OSError("test interrupted copy")

        patch.setattr(shutil, "copyfileobj", fail_copy)
        with pytest.raises(ConfigurationError, match="Could not initialize"):
            config.initialize_settings(tmp_path / "new")
    config_path = tmp_path / "new" / "config.toml"
    saved_config = config_path.read_bytes()
    assert not config_path.with_name("logo.png").exists()
    config.initialize_settings(config_path.parent)
    assert config_path.read_bytes() == saved_config
    assert config_path.with_name("logo.png").read_bytes() == b"legacy logo"


def test_migration_leaves_absolute_paths_and_unrelated_keys_unchanged(
    tmp_path: Path, legacy_package: Path
) -> None:
    original = EXAMPLE.replace(
        'output_dir = "output"',
        'output_dir = "~/Documents" # Output folder\nother_key = true',
    )
    (legacy_package / "config.toml").write_text(original, encoding="utf-8")
    migrated = config.initialize_settings(tmp_path / "new")
    assert migrated.read_text(encoding="utf-8") == original
    assert (
        tomllib.loads(migrated.read_text(encoding="utf-8"))["paths"]["other_key"]
        is True
    )


def test_invalid_save_preserves_existing_configuration(config_path: Path) -> None:
    before = config_path.read_bytes()
    with pytest.raises(ConfigurationError):
        config.save_settings_text("[broken", config_path)
    assert config_path.read_bytes() == before
    assert not list(config_path.parent.glob(".docgen-*.toml"))


def test_save_preserves_comments_and_unknown_keys(config_path: Path) -> None:
    updated = "# My configuration\ncustom_setting = 123\n" + EXAMPLE.replace(
        "Example Company", "New Company"
    )
    settings = config.save_settings_text(updated, config_path)
    assert settings.company_name == "New Company"
    assert config_path.read_text(encoding="utf-8") == updated
    assert not list(config_path.parent.glob(".docgen-*.toml"))


def test_failed_atomic_replace_preserves_original_and_cleans_temporary_file(
    config_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_replace(source: Path, destination: Path) -> None:
        assert source.parent == destination.parent
        raise PermissionError("test write failure")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(ConfigurationError, match="Could not save"):
        config.save_settings_text(
            EXAMPLE.replace("Example Company", "New Company"), config_path
        )
    assert config_path.read_text(encoding="utf-8") == EXAMPLE
    assert not list(config_path.parent.glob(".docgen-*.toml"))


def test_path_update_preserves_comments_and_other_values() -> None:
    original = EXAMPLE.replace(
        'output_dir = "output"',
        'output_dir = "output" # Where PDFs go\ncustom_key = 42',
    )
    updated = config.update_settings_paths(
        original, output_dir=Path("new output"), logo_path=Path("new logo.png")
    )
    parsed = tomllib.loads(updated)
    assert parsed["paths"] == {
        "output_dir": "new output",
        "logo_path": "new logo.png",
        "custom_key": 42,
    }
    assert "# Where PDFs go" in updated
    assert parsed["company"] == tomllib.loads(original)["company"]


def test_path_update_can_add_missing_paths_table() -> None:
    updated = config.update_settings_paths(
        "# Keep me\nother = true\n", logo_path=Path("logo.png")
    )
    assert updated.startswith("# Keep me\nother = true\n")
    assert tomllib.loads(updated)["paths"]["logo_path"] == "logo.png"


@pytest.mark.parametrize("text", ["[broken", 'paths = "invalid"'])
def test_path_update_rejects_invalid_toml_structure(text: str) -> None:
    with pytest.raises(ConfigurationError):
        config.update_settings_paths(text, logo_path=Path("logo.png"))
