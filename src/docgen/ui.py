from functools import partial
import tkinter as tk
from tkinter import ttk

from docgen.utils import snap

def window(title: str = "", fields: tuple[str, ...] = (), formats: dict[str, str] = {}, dropdowns: dict[str, tuple[str, ...]] = {}, cols: int = 2, size: tuple[float, float] = (0.6, 0.9)) -> tuple[tk.Tk, dict[str, ttk.Entry | ttk.Combobox]]:
    root = tk.Tk()
    root.title(title)
    style = ttk.Style(root)
    style.theme_use("aqua") # aqua, clam, alt, default, classic
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    rel_width = size[0]
    rel_height = size[1]
    width = int(screen_width * rel_width)
    height = int(screen_height * rel_height)
    root.geometry(f"{width}x{height}")

    form = ttk.Frame(root)
    form.pack(padx=30, pady=30, fill="both", expand=True)

    entries: dict[str, ttk.Entry | ttk.Combobox] = {}

    max_row = (len(fields) + 1) // cols

    for i, field in enumerate(fields):
        col = i // max_row
        row = i % max_row
        label_col = 2 * col
        entry_col = label_col + 1

        if field in dropdowns.keys():
            combobox = ttk.Combobox(
                form,
                values=dropdowns[field],
                state="readonly",
                width=30,
            )
            combobox.grid(
                row=row,
                column=entry_col,
                sticky="ew",
                padx=(0, 25),
                pady=8,
            )

            entries[field] = combobox

        else:
            entry = ttk.Entry(
                form,
                width=30,
            )
            entry.grid(
                row=row,
                column=entry_col,
                sticky="ew",
                padx=(0, 25),
                pady=8,
            )
            entry.bind(
                "<FocusOut>",
                partial(snap, format_type=formats.get(field)),
            )

            entries[field] = entry

        ttk.Label(
            form,
            text=field,
        ).grid(
            row=row,
            column=label_col,
            sticky="w",
            padx=(10, 8),
            pady=8,
        )

    form.columnconfigure(1, weight=1)
    form.columnconfigure(3, weight=1)

    return root, entries
