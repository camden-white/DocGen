"""Build, archive, run, or clean the native application on the current platform."""

import argparse
import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "docgen"
# Only these generic resources may enter a desktop release. Never collect package data.
RESOURCES = {
    "assets": ("docgen.icns", "docgen.ico"),
    "templates": ("transaction_worksheet.tex",),
    "examples": ("config.example.toml", "logo.example.png"),
}


class _Arguments(argparse.Namespace):
    """Mutually exclusive build actions selected by argparse."""

    archive: bool
    run: bool
    clean: bool


def app_path() -> Path:
    """Return the native executable produced on this platform."""
    if sys.platform == "darwin":
        return ROOT / "dist" / "DocGen.app" / "Contents" / "MacOS" / "DocGen"
    name = "DocGen.exe" if sys.platform == "win32" else "DocGen"
    return ROOT / "dist" / "DocGen" / name


def build() -> None:
    """Freeze the application and explicitly selected public resources."""
    # Fail early if this interpreter cannot supply Tk to PyInstaller.
    import tkinter

    print(f"Building with Python {platform.python_version()}, Tk {tkinter.TkVersion}")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "DocGen",
        "--windowed",
        "--onedir",
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(ROOT / "build"),
        "--paths",
        str(ROOT / "src"),
        "--copy-metadata",
        "docgen",
    ]
    if sys.platform in {"darwin", "win32"}:
        extension = "icns" if sys.platform == "darwin" else "ico"
        command.extend(["--icon", str(PACKAGE / "assets" / f"docgen.{extension}")])
    for directory, names in RESOURCES.items():
        for name in names:
            source = PACKAGE / directory / name
            if not source.is_file():
                raise FileNotFoundError(f"Missing bundled resource: {source}")
            command.extend(["--add-data", f"{source}:docgen/{directory}"])
    command.append(str(ROOT / "scripts" / "desktop_entry.py"))
    subprocess.run(command, cwd=ROOT, check=True)


def archive() -> Path:
    """Archive the current platform's application while preserving macOS symlinks."""
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not app_path().is_file():
        raise FileNotFoundError("Build not found. Run make build first.")
    release_dir = ROOT / "release"
    release_dir.mkdir(exist_ok=True)
    system = {"darwin": "macOS", "win32": "Windows"}.get(sys.platform, "Linux")
    destination = release_dir / f"DocGen-v{version}-{system}-{platform.machine()}.zip"
    if sys.platform == "darwin":
        subprocess.run(
            [
                "ditto",
                "-c",
                "-k",
                "--sequesterRsrc",
                "--keepParent",
                str(ROOT / "dist" / "DocGen.app"),
                str(destination),
            ],
            check=True,
        )
    else:
        shutil.make_archive(
            str(destination.with_suffix("")), "zip", ROOT / "dist", "DocGen"
        )
    return destination


def main() -> None:
    """Run the requested local build operation."""
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--archive", action="store_true", help="archive an existing build"
    )
    action.add_argument("--run", action="store_true", help="run an existing build")
    action.add_argument(
        "--clean", action="store_true", help="remove generated build directories"
    )
    args = parser.parse_args(namespace=_Arguments())
    if args.clean:
        for name in ("build", "dist", "release"):
            path = ROOT / name
            if path.is_symlink():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)
    elif args.run:
        subprocess.run([str(app_path())], check=True)
    elif args.archive:
        print(archive())
    else:
        build()


if __name__ == "__main__":
    main()
