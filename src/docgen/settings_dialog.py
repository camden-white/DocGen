"""Validated configuration editing in a transient application window."""

import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import cast

from .config import Settings, save_settings_text, update_settings_paths
from .errors import ConfigurationError
from .tk_types import Scrollable


def edit_settings(
    parent: tk.Tk,
    path: Path,
    on_saved: Callable[[Settings], None],
    *,
    initial_error: str = "",
    on_cancel: Callable[[], None] | None = None,
) -> tk.Toplevel:
    """Edit the complete TOML configuration and save only validated settings."""
    dialog = tk.Toplevel(parent)
    dialog.title("DocGen Settings")
    dialog.geometry("840x680")
    dialog.minsize(640, 420)
    dialog.transient(parent)
    previous_close = parent.protocol("WM_DELETE_WINDOW")
    container = ttk.Frame(dialog, padding=20)
    container.pack(fill="both", expand=True)
    ttk.Label(container, text="Company, agents, financing, and output settings").pack(
        anchor="w"
    )
    ttk.Label(container, text=str(path), wraplength=760).pack(anchor="w", pady=(4, 10))
    ttk.Label(
        container,
        text=(
            "Edit the TOML settings below. Keep quoted values in quotes; add agents using "
            'the existing [agents."Name"] pattern. Save validates the complete configuration.'
        ),
        wraplength=760,
    ).pack(anchor="w", pady=(0, 12))
    editor_frame = ttk.Frame(container)
    editor_frame.pack(fill="both", expand=True)
    editor = tk.Text(editor_frame, wrap="none", undo=True, padx=10, pady=10)
    viewport = cast(Scrollable, editor)
    y_scroll = ttk.Scrollbar(editor_frame, orient="vertical", command=viewport.yview)
    x_scroll = ttk.Scrollbar(editor_frame, orient="horizontal", command=viewport.xview)
    editor.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
    editor.grid(row=0, column=0, sticky="nsew")
    y_scroll.grid(row=0, column=1, sticky="ns")
    x_scroll.grid(row=1, column=0, sticky="ew")
    editor_frame.columnconfigure(0, weight=1)
    editor_frame.rowconfigure(0, weight=1)
    error_text = tk.StringVar(dialog, initial_error)
    ttk.Label(
        container, textvariable=error_text, style="Error.TLabel", wraplength=760
    ).pack(anchor="w", pady=12)
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        original = ""
        error_text.set(f"Could not read settings: {error}")
    editor.insert("1.0", original)

    def browse(*, logo: bool) -> None:
        selected = (
            filedialog.askopenfilename(
                parent=dialog, title="Choose Logo", filetypes=[("PNG images", "*.png")]
            )
            if logo
            else filedialog.askdirectory(parent=dialog, title="Choose Output Folder")
        )
        if not selected:
            return
        try:
            updated = update_settings_paths(
                editor.get("1.0", "end-1c"),
                logo_path=Path(selected) if logo else None,
                output_dir=None if logo else Path(selected),
            )
        except ConfigurationError as error:
            error_text.set(str(error))
            return
        editor.edit_separator()
        editor.delete("1.0", tk.END)
        editor.insert("1.0", updated)
        editor.edit_separator()
        error_text.set("Path updated. Choose Save Settings to apply it.")

    def confirm_discard() -> bool:
        return editor.get("1.0", "end-1c") == original or messagebox.askyesno(
            "Discard settings changes?",
            "Close without saving your settings changes?",
            parent=dialog,
        )

    def close_editor() -> None:
        parent.protocol("WM_DELETE_WINDOW", previous_close)
        parent.deletecommand(quit_command)
        dialog.destroy()

    def cancel() -> None:
        if not confirm_discard():
            return
        close_editor()
        if on_cancel is not None:
            on_cancel()

    def quit_application() -> None:
        if not confirm_discard():
            return
        close_editor()
        if previous_close:
            parent.tk.eval(previous_close)
        else:
            parent.destroy()

    def save() -> None:
        try:
            settings = save_settings_text(editor.get("1.0", "end-1c"), path)
        except (ConfigurationError, OSError) as error:
            error_text.set(str(error))
            return
        close_editor()
        on_saved(settings)

    actions = ttk.Frame(container)
    actions.pack(fill="x")
    ttk.Button(actions, text="Output Folder…", command=lambda: browse(logo=False)).pack(
        side="left"
    )
    ttk.Button(actions, text="Logo…", command=lambda: browse(logo=True)).pack(
        side="left", padx=10
    )
    ttk.Button(actions, text="Save Settings", command=save).pack(side="right")
    ttk.Button(actions, text="Cancel", command=cancel).pack(side="right", padx=10)
    dialog.protocol("WM_DELETE_WINDOW", cancel)
    parent.protocol("WM_DELETE_WINDOW", quit_application)
    quit_command = parent.protocol("WM_DELETE_WINDOW")
    dialog.grab_set()
    editor.focus_set()
    return dialog
