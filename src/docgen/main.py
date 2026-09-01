"""DocGen program"""

import importlib
import pkgutil
from collections.abc import Callable
from tkinter import ttk

from docgen.ui import window
import docgen.documents

def load_documents() -> dict[str, Callable[[], None]]:
    documents: dict[str, Callable[[], None]] = {}

    for module_info in pkgutil.iter_modules(docgen.documents.__path__):
        module = importlib.import_module(
            f"{docgen.documents.__name__}.{module_info.name}"
        )

        if hasattr(module, "main"):
            display_name = getattr(
                module,
                "DISPLAY_NAME",
                module_info.name.replace("_", " ").title(),
            )

            documents[display_name] = module.main

    return documents

def main() -> None:

    root = window(
        title="DocGen",
        size=(0.5,0.5)
    )

    for name, command in load_documents().items():
        button = ttk.Button(
            root,
            text=name,
            command=command,
        )
        button.pack()

    root.mainloop()


if __name__ == "__main__":
    main()
