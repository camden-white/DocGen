.DEFAULT_GOAL := help

.DELETE_ON_ERROR:

.SILENT:

.PHONY: \
	help init install upgrade \
	version bump-patch bump-minor bump-major bump \
	lint lint-fix format-check format type type-fix \
	check fix run build run-build clean-build

PKG := src/docgen
TEMPLATES := $(PKG)/templates
EXAMPLES := $(PKG)/examples
APP := DocGen
ASSETS := $(PKG)/assets

RUN := uv run
RUFF := $(RUN) ruff
TY := $(RUN) ty

help:
	echo "init          initialize project"
	echo "install       install dependencies"
	echo "upgrade       upgrade dependencies"
	echo "version       show project version"
	echo "bump-patch    bump patch version"
	echo "bump-minor    bump minor version"
	echo "bump-major    bump major version"
	echo "type          check types"
	echo "type-fix      fix types"
	echo "lint          check linting"
	echo "lint-fix      fix linting"
	echo "format-check  check code formatting"
	echo "format        format code"
	echo "check         run all checks"
	echo "fix           run all fixes"
	echo "run           run application"
	echo "build         build application"
	echo "run-build     run built application"
	echo "clean-build   clean build artifacts"

# initialize project
init: $(PKG)/config.toml $(PKG)/logo.png install
	echo "Project initialized."
	$(MAKE) version

$(PKG)/config.toml:
	cp $(EXAMPLES)/config.example.toml $@

$(PKG)/logo.png:
	cp $(EXAMPLES)/logo.example.png $@

# install dependencies
install:
	echo "Installing dependencies..."
	uv sync

# upgrade dependencies
upgrade:
	echo "Upgrading dependencies..."
	uv sync --upgrade

# show project version
version:
	uv version

# bump patch version
bump-patch:
	$(MAKE) bump BUMP=patch

# bump minor version
bump-minor:
	$(MAKE) bump BUMP=minor

# bump major version
bump-major:
	$(MAKE) bump BUMP=major

# bump version
bump: check
	case "$(BUMP)" in \
		patch|minor|major) ;; \
		*) echo "BUMP must be patch, minor, or major."; exit 1 ;; \
	esac; \
	if [ -n "$$(git status --porcelain)" ]; then \
		echo "Working tree has uncommitted changes."; \
		exit 1; \
	fi; \
	old_version="$$(uv version --short)" && \
	echo "Bumping $(BUMP) version..." && \
	uv version --bump $(BUMP) && \
	new_version="$$(uv version --short)" && \
	git add pyproject.toml uv.lock && \
	echo "Committing version $$new_version..." && \
	git commit -m "Bump version to $$new_version" && \
	git tag -a "v$$new_version" -m "DocGen v$$new_version" && \
	git push --follow-tags && \
	echo "Bumped version $$old_version -> $$new_version"

# check types
type:
	echo "Checking types..."
	$(TY) check

# fix types
type-fix:
	echo "Fixing types..."
	$(TY) check --fix

# check linting
lint:
	echo "Linting..."
	$(RUFF) check .

# fix linting
lint-fix:
	echo "Fixing linting..."
	$(RUFF) check --fix .

# check code formatting
format-check:
	echo "Checking code format..."
	$(RUFF) format --check .

# format code
format:
	echo "Formatting code..."
	$(RUFF) format .

# run all checks
check:
	status=0; \
	echo "Running all checks..."; \
	echo "----------------------------------------"; \
	$(MAKE) type || status=1; \
	echo "----------------------------------------"; \
	$(MAKE) lint || status=1; \
	echo "----------------------------------------"; \
	$(MAKE) format-check || status=1; \
	echo "----------------------------------------"; \
	exit $$status

# run all fixes
fix:
	status=0; \
	echo "Running all fixes..."; \
	echo "----------------------------------------"; \
	$(MAKE) type-fix || status=1; \
	echo "----------------------------------------"; \
	$(MAKE) lint-fix || status=1; \
	echo "----------------------------------------"; \
	$(MAKE) format || status=1; \
	echo "----------------------------------------"; \
	exit $$status

# run application
run:
	echo "Running DocGen application..."
	$(RUN) docgen

# build application
build:
	echo "Building DocGen application..."
	$(RUN) pyinstaller \
		--name $(APP) \
		--windowed \
		--onedir \
		--icon "$(ASSETS)/docgen.icns" \
		--add-data "$(ASSETS):docgen/assets" \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py
	cp $(EXAMPLES)/config.example.toml dist/config.toml
	cp $(EXAMPLES)/logo.example.png dist/logo.png

# run built application
run-build:
	if [ ! -d "dist/$(APP).app" ]; then \
		echo "Build not found. Run 'make build' first."; \
		exit 1; \
	fi; \
	echo "Running built DocGen application..."; \
	open "dist/$(APP).app"

# clean build artifacts
clean-build:
	echo "Cleaning build artifacts..."
	rm -rf build dist $(APP).spec
