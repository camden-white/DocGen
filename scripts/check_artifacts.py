"""Audit wheel, sdist, or desktop ZIP contents without extracting them."""

import argparse
import tarfile
import zipfile
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

PRIVATE_NAMES = frozenset({"config.toml", "logo.png", ".DS_Store"})
PUBLIC_RESOURCES = (
    "docgen/templates/transaction_worksheet.tex",
    "docgen/examples/config.example.toml",
    "docgen/examples/logo.example.png",
)


class _Arguments(argparse.Namespace):
    """Archive paths populated by argparse before the audit runs."""

    archives: list[Path]


def audit_archive(path: Path) -> None:
    """Reject private files, unsafe paths, or missing application resources."""
    if path.suffix in {".whl", ".zip"}:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
    elif path.name.endswith(".tar.gz"):
        with tarfile.open(path, "r:gz") as archive:
            names = archive.getnames()
    else:
        raise ValueError(f"Unsupported artifact type: {path.name}")
    audit_members(names)


def audit_members(names: Sequence[str]) -> None:
    """Validate public artifact filenames and required generic resources."""
    forbidden: list[str] = []
    for name in names:
        path = PurePosixPath(name.replace("\\", "/"))
        if (
            path.name in PRIVATE_NAMES
            or path.is_absolute()
            or ".." in path.parts
            or any(part.endswith(":") for part in path.parts)
        ):
            forbidden.append(name)
    if forbidden:
        raise ValueError(f"Forbidden archive members: {', '.join(sorted(forbidden))}")
    missing = [
        required
        for required in PUBLIC_RESOURCES
        if not any(name == required or name.endswith(f"/{required}") for name in names)
    ]
    if missing:
        raise ValueError(f"Missing public resources: {', '.join(missing)}")


def main() -> None:
    """Audit each explicitly supplied archive."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args(namespace=_Arguments())
    for path in args.archives:
        audit_archive(path)
        print(f"Verified public contents: {path.name}")


if __name__ == "__main__":
    main()
