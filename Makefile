.PHONY: init install run

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
		--onefile \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py
	cp $(EXAMPLES)/config.example.toml dist/config.toml
	cp $(EXAMPLES)/logo.example.png dist/logo.png

run-build:
	./dist/$(APP)

clean-build:
	rm -rf build dist $(APP).spec
