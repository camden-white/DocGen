"""Desktop startup and headless configuration/dependency commands."""

import argparse
import json
import logging
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from . import __version__
from .config import (
    PACKAGE_DIR,
    Settings,
    default_config_path,
    initialize_settings,
    load_settings,
)
from .errors import ConfigurationError


class _Arguments(argparse.Namespace):
    """Command-line attributes populated and validated by the argument parser."""

    config: Path | None
    init_config: bool
    check: bool
    smoke_test: bool


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate transaction worksheets as PDF documents."
    )
    parser.add_argument("--version", action="version", version=f"DocGen {__version__}")
    parser.add_argument("--config", type=Path, help="Use this TOML configuration file.")
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument(
        "--init-config",
        action="store_true",
        help="Initialize per-user settings and exit.",
    )
    commands.add_argument(
        "--check",
        action="store_true",
        help="Print JSON PDF dependency diagnostics and exit.",
    )
    commands.add_argument(
        "--smoke-test",
        action="store_true",
        help="Create and close a GUI window for installation checks.",
    )
    return parser


def _initialize(path: Path | None) -> Path:
    if path is not None and path.name != "config.toml":
        raise ConfigurationError(
            "To initialize a custom location, use --config /your/directory/config.toml."
        )
    return initialize_settings(path.parent if path is not None else None)


def main(argv: list[str] | None = None) -> int:
    """Run DocGen and return a process exit status; CLI checks are headless."""
    args = _parser().parse_args(argv, namespace=_Arguments())
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    if args.init_config:
        try:
            path = _initialize(args.config)
        except (ConfigurationError, OSError) as error:
            print(str(error), file=sys.stderr)
            return 1
        print(path)
        return 0
    if args.check:
        from .pdf import check_dependencies

        errors = check_dependencies(PACKAGE_DIR / "examples" / "logo.example.png")
        if args.config is not None:
            try:
                settings = load_settings(args.config)
            except ConfigurationError as error:
                errors.append(str(error))
            else:
                errors.extend(check_dependencies(settings.logo_path))
        errors = list(dict.fromkeys(errors))
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
        return int(bool(errors))

    # Import Tk only when a graphical launch was requested.
    import tkinter as tk
    from tkinter import messagebox

    from .settings_dialog import edit_settings
    from .ui import Application, window

    try:
        root = window()
    except tk.TclError as error:
        print(f"Could not open the graphical application: {error}", file=sys.stderr)
        return 1
    if args.smoke_test:
        with TemporaryDirectory(prefix="docgen-smoke-") as directory:
            config_path = initialize_settings(Path(directory), migrate=False)
            smoke_application = Application(root, load_settings(config_path))
            root.after(100, smoke_application.close)
            root.mainloop()
        return 0

    application: Application | None = None

    def start(settings: Settings) -> None:
        nonlocal application
        application = Application(root, settings)

    path = args.config.expanduser().resolve() if args.config else default_config_path()
    try:
        start(load_settings(path))
    except ConfigurationError as error:
        initial_error = str(error)
        if not path.exists():
            try:
                path = _initialize(path)
                initial_error = "Welcome to DocGen. Review the example company and agent information, then save your settings."
            except (ConfigurationError, OSError) as init_error:
                messagebox.showerror(
                    "Could not initialize settings", str(init_error), parent=root
                )
                root.destroy()
                return 1
        edit_settings(
            root, path, start, initial_error=initial_error, on_cancel=root.destroy
        )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
