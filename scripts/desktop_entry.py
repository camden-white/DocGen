"""PyInstaller entry point using the same main function as the console script."""

from docgen.main import main

if __name__ == "__main__":
    raise SystemExit(main())
