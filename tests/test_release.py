"""Exercise release guards and exact-tag publication against disposable local Git repos."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RELEASE_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "release.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=DocGen Test",
            "-c",
            "user.email=test@example.com",
            *args,
        ],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


@pytest.fixture
def release_repository(tmp_path: Path) -> Path:
    repo = tmp_path / "checkout"
    repo.mkdir()
    scripts = repo / "scripts"
    scripts.mkdir()
    shutil.copy2(RELEASE_SCRIPT, scripts / "release.py")
    (repo / "pyproject.toml").write_text('[project]\nversion = "1.2.3"\n')
    git(repo, "init", "--initial-branch=main")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Initial test release")
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    return repo


def release(
    repo: Path, *args: str, answer: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "release.py"), *args],
        cwd=repo,
        text=True,
        input=answer,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "tag", ["", "1.2.3", "v01.2.3", "v1.2.4", "v1.2.3rc1", "v1.2.3;echo bad"]
)
def test_invalid_tag_cannot_change_repository(
    release_repository: Path, tag: str
) -> None:
    result = release(release_repository, "publish", tag, answer="yes\n")
    assert result.returncode != 0
    assert git(release_repository, "status", "--porcelain") == ""
    assert git(release_repository, "ls-remote", "origin") == ""


def test_ci_tag_matches_project(release_repository: Path) -> None:
    assert release(release_repository, "verify-tag", "v1.2.3").returncode == 0
    assert release(release_repository, "verify-tag", "v2.0.0").returncode != 0


def test_dirty_checkout_blocks_publication(release_repository: Path) -> None:
    (release_repository / "uncommitted.txt").write_text("keep me")
    result = release(release_repository, "publish", "v1.2.3", answer="yes\n")
    assert "uncommitted changes" in result.stderr
    assert git(release_repository, "ls-remote", "origin") == ""


def test_lightweight_tag_is_rejected(release_repository: Path) -> None:
    git(release_repository, "tag", "v1.2.3")
    result = release(release_repository, "publish", "v1.2.3", answer="yes\n")
    assert "must be annotated" in result.stderr
    assert git(release_repository, "ls-remote", "origin") == ""


def test_tag_on_old_commit_is_rejected(release_repository: Path) -> None:
    git(release_repository, "tag", "-a", "v1.2.3", "-m", "Test release")
    git(release_repository, "commit", "--allow-empty", "-m", "Later change")
    result = release(release_repository, "publish", "v1.2.3", answer="yes\n")
    assert "current reviewed commit" in result.stderr
    assert git(release_repository, "ls-remote", "origin") == ""


@pytest.mark.parametrize("answer", ["", "\n", "no\n", "not sure\n"])
def test_publication_requires_explicit_yes(
    release_repository: Path, answer: str
) -> None:
    git(release_repository, "tag", "-a", "v1.2.3", "-m", "Test release")
    result = release(release_repository, "publish", "v1.2.3", answer=answer)
    assert result.returncode == 0
    assert "cancelled" in result.stdout
    assert git(release_repository, "ls-remote", "origin") == ""


def test_publication_pushes_only_requested_tag_to_local_test_remote(
    release_repository: Path,
) -> None:
    git(release_repository, "tag", "-a", "v1.2.3", "-m", "Test release")
    git(release_repository, "tag", "-a", "unrelated-tag", "-m", "Keep local")
    result = release(release_repository, "publish", "v1.2.3", answer="yes\n")
    assert result.returncode == 0, result.stderr
    refs = git(release_repository, "ls-remote", "origin").splitlines()
    assert {line.split()[1] for line in refs} == {
        "refs/tags/v1.2.3",
        "refs/tags/v1.2.3^{}",
    }
    assert git(release_repository, "status", "--porcelain") == ""
    repeated = release(release_repository, "publish", "v1.2.3", answer="yes\n")
    assert "already exists on origin" in repeated.stderr


def test_invalid_preparation_is_nonmutating(release_repository: Path) -> None:
    result = release(release_repository, "prepare", "invalid")
    assert result.returncode == 2
    assert git(release_repository, "status", "--porcelain") == ""
