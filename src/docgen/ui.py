"""User interface with Tkinter"""

import platform
import tkinter as tk
from functools import partial
from tkinter import ttk
from typing import TYPE_CHECKING

from .config import ICON_PATH
from .utils import formatting

if TYPE_CHECKING:
    from typing import Any


class Textbox(tk.Text):
    """Tall text box with similar behavior to tk.Entry"""

    def get(self, index1: Any = None, index2: Any = None) -> str:
        if index1 is None:
            index1 = "1.0"
            index2 = "end-1c"

        return super().get(index1=index1, index2=index2)


def snap(event: tk.Event[ttk.Entry | Textbox], format_type: str | None = None) -> None:
    """Snap an event to it's proper formatting"""

    entry = event.widget
    raw = entry.get().strip()

    if not raw:
        return

    indexing: str | int
    if format_type == "paragraph":
        indexing = "1.0"
    else:
        indexing = 0

    formatted = formatting(string=raw, format_type=format_type)

    entry.delete(indexing, tk.END)
    entry.insert(indexing, formatted)


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
    size: tuple[float, float] = (0.8, 0.8),
    box_line_height: int = 3,
) -> tuple[tk.Tk, dict[str, ttk.Entry | ttk.Combobox | Textbox]]:
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
        lambda _: canvas.configure(
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

    entries: dict[str, ttk.Entry | ttk.Combobox | Textbox] = {}

    column_frames: list[ttk.Frame] = []
    column_rows = [0] * cols

    field_heights = {
        field: box_line_height if formats.get(field) == "paragraph" else 1
        for field in fields
    }

    remaining_height = sum(field_heights.values())

    col = 0
    current_height = 0

    for _ in range(cols):
        column = ttk.Frame(form)
        column.pack(
            side="left",
            fill="both",
            expand=True,
            anchor="n",
        )

        column.columnconfigure(
            1,
            weight=1,
        )

        column_frames.append(column)

    for field in fields:
        column = column_frames[col]
        row = column_rows[col]

        label = ttk.Label(
            column,
            text=field,
        )

        label.grid(
            row=row,
            column=0,
            sticky="nw",
            padx=(10, 8),
            pady=8,
        )

        widget: ttk.Combobox | ttk.Entry | Textbox

        if field in dropdowns:
            widget = ttk.Combobox(
                column,
                values=dropdowns[field],
                state="readonly",
                width=30,
            )

        elif formats.get(field) == "paragraph":
            widget = Textbox(
                column,
                width=40,
                height=box_line_height * 3.1 - 1,
                wrap="word",
            )

        else:
            widget = ttk.Entry(
                column,
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
            column=1,
            sticky="ew",
            padx=(0, 25),
            pady=8,
        )

        entries[field] = widget

        column_rows[col] += 1

        current_height += field_heights[field]
        remaining_height -= field_heights[field]

        if col < cols - 1:
            remaining_cols = cols - col - 1

            if current_height >= remaining_height / remaining_cols:
                col += 1
                current_height = 0

    return root, entries
