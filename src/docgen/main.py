"""DocGen application"""

from tkinter import ttk

from docgen.ui import window
from docgen.utils import load_documents


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
