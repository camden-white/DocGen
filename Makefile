.PHONY: init install run build run-build clean-build

PKG := src/docgen
TEMPLATES := $(PKG)/templates
EXAMPLES := $(PKG)/examples
APP := DocGen
ASSETS := $(PKG)/assets

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
		--icon "$(ASSETS)/docgen.icns" \
		--add-data "$(ASSETS):docgen/assets" \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py
	cp $(EXAMPLES)/config.example.toml dist/config.toml
	cp $(EXAMPLES)/logo.example.png dist/logo.png

run-build:
	open dist/$(APP).app

clean-build:
	rm -rf build dist $(APP).spec
