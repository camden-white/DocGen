.DEFAULT_GOAL := help
.DELETE_ON_ERROR:

.PHONY: help init install upgrade version lint lint-fix format-check format type test \
	check fix run smoke diagnostics package package-check build run-build clean-build \
	prepare-release publish

RUN := uv run --locked

help:
	@echo "init            initialize user configuration without overwriting existing files"
	@echo "install         install the locked development environment"
	@echo "upgrade         deliberately update dependencies and run checks"
	@echo "check           check lockfile, lint, format, types, and unit tests"
	@echo "test            run tests without a graphical display or XeLaTeX"
	@echo "fix             apply Ruff's safe fixes and format"
	@echo "run             open DocGen"
	@echo "smoke           briefly open and verify the application UI"
	@echo "diagnostics     check XeLaTeX and bundled template dependencies"
	@echo "package-check   build and audit distributions; test a clean wheel install"
	@echo "build           create the native desktop application"
	@echo "run-build       run the native application"
	@echo "clean-build     remove generated build, dist, and release directories"
	@echo "prepare-release BUMP=patch|minor|major (edit version files only)"
	@echo "publish TAG=vX.Y.Z (push that existing annotated tag after confirmation)"

install:
	uv sync --locked

init: install
	$(RUN) docgen --init-config

# Updating the lock is an explicit maintenance action, separate from normal checks.
upgrade:
	uv lock --upgrade
	uv sync --locked
	$(MAKE) check

version:
	uv version --short

lint:
	$(RUN) ruff check .

lint-fix:
	$(RUN) ruff check --fix .

format-check:
	$(RUN) ruff format --check .

format:
	$(RUN) ruff format .

type:
	$(RUN) ty check
	$(RUN) pyright
	$(RUN) mypy

test:
	$(RUN) pytest -m "not integration and not gui"

check:
	@status=0; \
	uv lock --check || status=1; \
	$(MAKE) lint || status=1; \
	$(MAKE) format-check || status=1; \
	$(MAKE) type || status=1; \
	$(MAKE) test || status=1; \
	exit $$status

fix:
	$(MAKE) lint-fix
	$(MAKE) format

run:
	$(RUN) docgen

smoke:
	$(RUN) docgen --smoke-test

diagnostics:
	$(RUN) docgen --check

package:
	uv lock --check
	uv build --out-dir dist/packages

package-check:
	$(RUN) python scripts/check_package.py

build:
	$(RUN) python scripts/build_app.py

run-build:
	$(RUN) python scripts/build_app.py --run

clean-build:
	$(RUN) python scripts/build_app.py --clean

prepare-release: check
	$(RUN) python scripts/release.py prepare "$(BUMP)"

publish: check package-check
	$(RUN) python scripts/release.py publish "$(TAG)"
