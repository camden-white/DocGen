"""Paramount document program"""

from tkinter import ttk

from paramount.ui import window
from paramount.documents.transaction_worksheet import main as transaction_worksheet

def main() -> None:

    root, _ = window(
        title="Document Generator",
        size=(0.5,0.5),
    )

    transaction_worksheet_button=ttk.Button(
        root,
        text="Transaction Worksheet",
        command=transaction_worksheet,
    )

    transaction_worksheet_button.pack(pady=100)

    root.mainloop()


if __name__ == "__main__":
    main()
