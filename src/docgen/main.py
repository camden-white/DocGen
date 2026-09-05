"""DocGen application"""

import importlib
import pkgutil
from collections.abc import Callable
from tkinter import ttk

import docgen.documents
from docgen.ui import window


def load_documents() -> dict[str, Callable[[], None]]:
    """Load the modules in the documents/ directory"""

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
    """DocGen application"""

    documents = load_documents()

    if len(documents) == 1:
        for command in documents.values():
            command()

    else:
        root = window(
            title="DocGen",
            size=(0.4, 0.6),
        )

        button_frame = ttk.Frame(root)
        button_frame.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
        )

        for name, command in documents.items():
            button = ttk.Button(
                button_frame,
                text=name,
                command=command,
                width=24,
            )
            button.pack(pady=8)

        root.mainloop()


if __name__ == "__main__":
    main()
