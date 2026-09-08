"""Prepare version files or publish one existing, reviewed annotated release tag."""

import argparse
import re
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASE_TAG = re.compile(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")


class ReleaseError(Exception):
    """A release precondition was not satisfied."""


def run(*args: str) -> str:
    """Run a checked command in the checkout and return its standard output."""
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        check=True,
        capture_output=True,
    ).stdout.strip()


def version() -> str:
    """Read the authoritative project version without importing the application."""
    value = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not isinstance(value, str):
        raise ReleaseError("Project version must be a string.")
    return value


def require_clean() -> None:
    """Require all working-tree changes to be committed before release operations."""
    if run("git", "status", "--porcelain"):
        raise ReleaseError(
            "Working tree has uncommitted changes; review and commit them first."
        )


def validate_tag(tag: str) -> None:
    """Require a stable release tag matching the current project version."""
    if RELEASE_TAG.fullmatch(tag) is None:
        raise ReleaseError("TAG must be a stable version such as v1.2.3.")
    if tag != f"v{version()}":
        raise ReleaseError(f"Tag {tag} does not match project version {version()}.")


def prepare(bump: str) -> None:
    """Update version metadata and its lock entry, leaving review and commit to the author."""
    require_clean()
    upcoming = run("uv", "version", "--bump", bump, "--dry-run", "--short")
    tag = f"v{upcoming}"
    if run("git", "tag", "--list", tag):
        raise ReleaseError(f"Tag {tag} already exists.")
    remote = run("git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}")
    if remote:
        raise ReleaseError(f"Tag {tag} already exists on origin.")
    print(run("uv", "version", "--bump", bump, "--no-sync"))
    print(
        f"Prepared {tag}. Review pyproject.toml and uv.lock, run make check, then commit.\n"
        f"Create an annotated tag on that reviewed commit:\n"
        f'  git tag -a {tag} -m "DocGen {tag}"\n'
        f"Publish only when ready: make publish TAG={tag}"
    )


def publish(tag: str) -> None:
    """Confirm and push exactly one annotated tag at HEAD, never branches or other tags."""
    validate_tag(tag)
    require_clean()
    reference = f"refs/tags/{tag}"
    if run("git", "cat-file", "-t", reference) != "tag":
        raise ReleaseError("Release tag must be annotated (git tag -a).")
    if run("git", "rev-parse", f"{reference}^{{commit}}") != run(
        "git", "rev-parse", "HEAD"
    ):
        raise ReleaseError("Release tag must point to the current reviewed commit.")
    if run("git", "ls-remote", "--tags", "origin", reference):
        raise ReleaseError(f"Tag {tag} already exists on origin.")
    remote_url = run("git", "remote", "get-url", "--push", "origin")
    try:
        answer = input(
            f"Push only {tag} to {remote_url} and trigger release builds? [y/N] "
        )
    except EOFError:
        answer = ""
    if answer.strip().lower() not in {"y", "yes"}:
        print("Publication cancelled.")
        return
    subprocess.run(
        ["git", "push", "origin", f"{reference}:{reference}"], cwd=ROOT, check=True
    )


class _Arguments(argparse.Namespace):
    """Release arguments; argparse fills the chosen subcommand's values."""

    command: str
    bump: str = ""
    tag: str = ""


def main() -> None:
    """Validate arguments before performing any release action."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    preparation = commands.add_parser("prepare", help="edit version files only")
    preparation.add_argument("bump", choices=("patch", "minor", "major"))
    publication = commands.add_parser("publish", help="push one existing annotated tag")
    publication.add_argument("tag")
    verification = commands.add_parser(
        "verify-tag", help="verify a CI tag against project metadata"
    )
    verification.add_argument("tag")
    args = parser.parse_args(namespace=_Arguments())
    try:
        if args.command == "prepare":
            prepare(args.bump)
        elif args.command == "publish":
            publish(args.tag)
        else:
            validate_tag(args.tag)
    except (ReleaseError, subprocess.CalledProcessError) as exc:
        detail = (
            exc.stderr.strip()
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr
            else str(exc)
        )
        parser.exit(1, f"Release stopped: {detail}\n")


if __name__ == "__main__":
    main()
