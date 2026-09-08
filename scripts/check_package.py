"""Build audited distributions and verify a clean, locked wheel installation."""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class _Arguments(argparse.Namespace):
    """Optional installation checks selected by argparse."""

    gui: bool
    pdf: bool


def main() -> None:
    """Run the installed package from outside the repository and editable environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gui", action="store_true", help="also open and close the installed GUI"
    )
    parser.add_argument(
        "--pdf", action="store_true", help="also compile template diagnostics"
    )
    args = parser.parse_args(namespace=_Arguments())
    with tempfile.TemporaryDirectory(prefix="docgen-package-") as directory:
        temporary = Path(directory)
        artifacts = temporary / "artifacts"
        subprocess.run(["uv", "lock", "--check"], cwd=ROOT, check=True)
        subprocess.run(
            [
                "uv",
                "build",
                "--out-dir",
                str(artifacts),
            ],
            cwd=ROOT,
            check=True,
        )
        for artifact in sorted(artifacts.iterdir()):
            if artifact.suffix == ".whl" or artifact.name.endswith(".tar.gz"):
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "check_artifacts.py"),
                        str(artifact),
                    ],
                    cwd=temporary,
                    check=True,
                )
        wheels = list(artifacts.glob("*.whl"))
        if len(wheels) != 1 or len(list(artifacts.glob("*.tar.gz"))) != 1:
            raise RuntimeError(
                "Expected exactly one wheel and one source distribution."
            )
        dependencies = temporary / "dependencies.txt"
        subprocess.run(
            [
                "uv",
                "export",
                "--locked",
                "--no-dev",
                "--no-emit-project",
                "--format",
                "requirements-txt",
                "--output-file",
                str(dependencies),
            ],
            cwd=ROOT,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        environment = temporary / "environment"
        subprocess.run(
            [
                "uv",
                "venv",
                "--python",
                sys.executable,
                str(environment),
            ],
            cwd=temporary,
            check=True,
        )
        bin_dir = environment / ("Scripts" if sys.platform == "win32" else "bin")
        python = bin_dir / ("python.exe" if sys.platform == "win32" else "python")
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--require-hashes",
                "--requirements",
                str(dependencies),
            ],
            cwd=temporary,
            check=True,
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(python),
                "--no-deps",
                str(wheels[0]),
            ],
            cwd=temporary,
            check=True,
        )
        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        clean_env["DOCGEN_CONFIG_DIR"] = str(temporary / "settings")
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "from pathlib import Path; import docgen, sys; "
                    "assert Path(docgen.__file__).is_relative_to(Path(sys.prefix)); "
                    "assert 'tkinter' not in sys.modules; "
                    "print('Installed package import:', docgen.__file__)"
                ),
            ],
            cwd=temporary,
            env=clean_env,
            check=True,
        )
        executable = bin_dir / ("docgen.exe" if sys.platform == "win32" else "docgen")
        commands = [[str(executable), "--help"], [str(executable), "--init-config"]]
        if args.gui:
            commands.append([str(executable), "--smoke-test"])
        if args.pdf:
            commands.append([str(executable), "--check"])
        for command in commands:
            subprocess.run(
                command, cwd=temporary, env=clean_env, check=True, timeout=120
            )
        if args.pdf:
            smoke = temporary / "installed_wheel_smoke.py"
            shutil.copy2(ROOT / "scripts" / "installed_wheel_smoke.py", smoke)
            subprocess.run(
                [str(python), "-I", str(smoke)],
                cwd=temporary,
                env=clean_env,
                check=True,
                timeout=120,
            )
        print("Clean wheel installation verified.")


if __name__ == "__main__":
    main()
