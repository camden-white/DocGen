.PHONY: init install run build run-build clean-build

PKG := src/docgen
TEMPLATES := $(PKG)/templates
EXAMPLES := $(PKG)/examples
APP := DocGen

init: \
    $(PKG)/config.toml \
    $(PKG)/logo.png \
    install

$(PKG)/config.toml:
	cp $(EXAMPLES)/config.example.toml $@

$(PKG)/logo.png:
	cp $(EXAMPLES)/logo.example.png $@

install:
	uv sync

run:
	uv run docgen

build:
	uv run pyinstaller \
		--name $(APP) \
		--windowed \
		--onedir \
		--icon "$(PKG)/assets/docgen.ico" \
		--add-data "$(PKG)/assets:docgen/assets" \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py
	cp $(EXAMPLES)/config.example.toml dist/$(APP)/config.toml
	cp $(EXAMPLES)/logo.example.png dist/$(APP)/logo.png

run-build:
	./dist/$(APP)/$(APP)

build-macos:
	uv run pyinstaller \
		--name $(APP) \
		--windowed \
		--onedir \
		--icon "$(PKG)/assets/docgen.icns" \
		--add-data "$(PKG)/assets:docgen/assets" \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py
	cp $(EXAMPLES)/config.example.toml dist/config.toml
	cp $(EXAMPLES)/logo.example.png dist/logo.png

run-build-macos:
	open dist/$(APP).app

clean-build:
	rm -rf build dist $(APP).spec
