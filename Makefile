.PHONY: init install generate

init: config.py install generate

config.py:
	cp config.example.py config.py

install:
	uv sync

generate:
	uv run python scripts/generate_files.py

run:
	uv run docgen
