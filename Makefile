.PHONY: init install run

PKG := src/docgen
IMAGES := $(PKG)/images
TEMPLATES := $(PKG)/templates
DOCUMENTS := $(PKG)/documents
EXAMPLES := $(PKG)/examples
APP := DocGen

init: \
    $(PKG)/config.py \
    $(IMAGES)/logo.png \
    $(TEMPLATES)/example.tex \
    $(DOCUMENTS)/example.py \
    install

$(PKG)/config.py:
	cp $(EXAMPLES)/config.example.py $@

$(IMAGES)/logo.png:
	mkdir -p $(@D)
	cp $(EXAMPLES)/logo.example.png $@

$(TEMPLATES)/example.tex:
	mkdir -p $(@D)
	cp $(EXAMPLES)/template.example.tex $@

$(DOCUMENTS)/example.py:
	mkdir -p $(@D)
	cp $(EXAMPLES)/document.example.py $@

install:
	uv sync

run:
	uv run docgen

build:
	uv run pyinstaller \
		--name $(APP) \
		--windowed \
		--onefile \
		--add-data "$(IMAGES):docgen/images" \
		--add-data "$(TEMPLATES):docgen/templates" \
		--collect-submodules docgen.documents \
		$(PKG)/main.py

run-build:
	./dist/$(APP)

clean-build:
	rm -rf build dist $(APP).spec
