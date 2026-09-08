"""Archive privacy and completeness checks run without extracting untrusted members."""

import io
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

AUDIT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_artifacts.py"
REQUIRED = (
    "docgen/templates/transaction_worksheet.tex",
    "docgen/examples/config.example.toml",
    "docgen/examples/logo.example.png",
)


def audit(path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT), str(path)],
        text=True,
        capture_output=True,
        check=False,
    )


def write_zip(path: Path, names: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"public example")


@pytest.mark.parametrize("suffix", [".whl", ".zip"])
def test_public_zip_resources_are_accepted(tmp_path: Path, suffix: str) -> None:
    artifact = tmp_path / f"DocGen{suffix}"
    write_zip(
        artifact, tuple(f"DocGen.app/Contents/Resources/{name}" for name in REQUIRED)
    )
    result = audit(artifact)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "private_name",
    [
        "docgen/config.toml",
        "docgen/logo.png",
        "DocGen/.DS_Store",
        r"DocGen\config.toml",
        "../outside.txt",
        "/absolute.txt",
        "C:/outside.txt",
    ],
)
def test_private_and_unsafe_members_are_rejected(
    tmp_path: Path, private_name: str
) -> None:
    artifact = tmp_path / "docgen.whl"
    write_zip(artifact, (*REQUIRED, private_name))
    result = audit(artifact)
    assert result.returncode != 0
    assert "Forbidden archive members" in result.stderr


def test_missing_template_is_rejected(tmp_path: Path) -> None:
    artifact = tmp_path / "docgen.whl"
    write_zip(artifact, REQUIRED[1:])
    result = audit(artifact)
    assert result.returncode != 0
    assert "Missing public resources" in result.stderr


@pytest.mark.parametrize("include_private", [False, True])
def test_source_distribution_is_audited(tmp_path: Path, include_private: bool) -> None:
    artifact = tmp_path / "docgen.tar.gz"
    names = (*REQUIRED, "docgen/config.toml") if include_private else REQUIRED
    with tarfile.open(artifact, "w:gz") as archive:
        for name in names:
            member = tarfile.TarInfo(f"docgen-1.0/src/{name}")
            content = b"example"
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    result = audit(artifact)
    assert (result.returncode != 0) is include_private
