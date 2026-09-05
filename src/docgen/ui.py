"""User interface with Tkinter"""

import platform
import tkinter as tk
from functools import partial
from tkinter import ttk

from docgen.config import ICON_PATH
from docgen.utils import snap


def window(title: str = "", size: tuple[float, float] = (0.5, 0.5)) -> tk.Tk:
    """Standard root window"""

    root = tk.Tk()
    root.title(title)
    style = ttk.Style(root)

    if platform.system() == "Darwin":
        style.theme_use("aqua")
    elif platform.system() == "Windows":
        style.theme_use("vista")
        root.iconbitmap(str(ICON_PATH))
    else:
        style.theme_use("clam")

    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    rel_width = size[0]
    rel_height = size[1]
    width = int(screen_width * rel_width)
    height = int(screen_height * rel_height)
    root.geometry(f"{width}x{height}")

    return root


def form_window(
    title: str = "",
    fields: tuple[str, ...] = (),
    formats: dict[str, str] | None = None,
    dropdowns: dict[str, tuple[str, ...]] | None = None,
    cols: int = 2,
    size: tuple[float, float] = (0.6, 0.8),
) -> tuple[tk.Tk, dict[str, ttk.Entry | ttk.Combobox]]:
    """Document form window"""

    if formats is None:
        formats = {}

    if dropdowns is None:
        dropdowns = {}

    root = window(
        title=title,
        size=size,
    )

    container = ttk.Frame(root)
    container.pack(
        padx=30,
        pady=30,
        fill="both",
        expand=True,
    )

    canvas = tk.Canvas(
        container,
        highlightthickness=0,
        borderwidth=0,
        background=root.cget("background"),
    )

    scrollbar = ttk.Scrollbar(
        container,
        orient="vertical",
        command=canvas.yview,
    )

    canvas.configure(
        yscrollcommand=scrollbar.set,
    )

    canvas.pack(
        side="left",
        fill="both",
        expand=True,
    )

    scrollbar.pack(
        side="right",
        fill="y",
    )

    form = ttk.Frame(canvas)

    form_window_id = canvas.create_window(
        (0, 0),
        window=form,
        anchor="nw",
    )

    form.bind(
        "<Configure>",
        lambda event: canvas.configure(
            scrollregion=canvas.bbox("all"),
        ),
    )

    canvas.bind(
        "<Configure>",
        lambda event: canvas.itemconfigure(
            form_window_id,
            width=event.width,
        ),
    )

    def mousewheel_scroll(event: tk.Event) -> str:
        """Mousewheel scrolling"""
        if platform.system() == "Darwin":
            canvas.yview_scroll(-event.delta, "units")
        elif platform.system() == "Windows":
            canvas.yview_scroll(-(event.delta // 120), "units")

        return "break"

    def touchpad_scroll(event: tk.Event) -> str:
        """Touchpad scrolling"""
        raw = event.delta & 0xFFFFFFFF
        delta_y = raw & 0xFFFF

        if delta_y >= 0x8000:
            delta_y -= 0x10000

        first, _ = canvas.yview()
        canvas.yview_moveto(first - delta_y * 0.001)

        return "break"

    if platform.system() == "Darwin":
        root.bind_all(
            "<TouchpadScroll>",
            touchpad_scroll,
            add="+",
        )
        root.bind_all(
            "<MouseWheel>",
            mousewheel_scroll,
            add="+",
        )

    elif platform.system() == "Windows":
        root.bind_all(
            "<MouseWheel>",
            mousewheel_scroll,
            add="+",
        )

    else:
        root.bind_all(
            "<Button-4>",
            lambda _: canvas.yview_scroll(-1, "units"),
            add="+",
        )
        root.bind_all(
            "<Button-5>",
            lambda _: canvas.yview_scroll(1, "units"),
            add="+",
        )

    entries: dict[str, ttk.Entry | ttk.Combobox] = {}

    max_row = (len(fields) + cols - 1) // cols

    for col in range(cols):
        form.columnconfigure(
            2 * col + 1,
            weight=1,
        )

    for i, field in enumerate(fields):
        col = i // max_row
        row = i % max_row

        label_col = 2 * col
        entry_col = label_col + 1

        widget: ttk.Combobox | ttk.Entry

        if field in dropdowns:
            widget = ttk.Combobox(
                form,
                values=dropdowns[field],
                state="readonly",
                width=30,
            )

        else:
            widget = ttk.Entry(
                form,
                width=30,
            )

            widget.bind(
                "<FocusOut>",
                partial(
                    snap,
                    format_type=formats.get(field),
                ),
            )

        widget.grid(
            row=row,
            column=entry_col,
            sticky="ew",
            padx=(0, 25),
            pady=8,
        )

        entries[field] = widget

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

    return root, entries
