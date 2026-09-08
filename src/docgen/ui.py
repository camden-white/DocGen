"""Tkinter views; parsing and PDF generation remain independent of widgets."""

import logging
import platform
import re
import tkinter as tk
import traceback
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Literal, cast

from .config import ICON_PATH, Settings
from .documents.transaction_worksheet import generate, get_document
from .drafts import DraftError, load_draft, save_draft
from .errors import DocGenError, PdfOpenError, ValidationError
from .models import DocumentSpec, FieldSpec, validate_data
from .pdf import check_dependencies
from .tk_types import IconWindow, Scrollable, TclCommands
from .utils import formatting, open_pdf

logger = logging.getLogger(__name__)

type InputWidget = ttk.Entry | ttk.Combobox | Textbox


class Textbox(tk.Text):
    """Multiline input retaining Tk's native indexed ``get`` interface."""

    def get_value(self) -> str:
        """Read the entire field, excluding Tk's automatic trailing newline."""
        return self.get("1.0", "end-1c")


def get_input_value(widget: InputWidget) -> str:
    """Read an entry, choice, or multiline field through its native interface."""
    return widget.get_value() if isinstance(widget, Textbox) else widget.get()


def snap(event: tk.Event[ttk.Entry | Textbox], format_type: str | None = None) -> None:
    """Format valid input on focus loss, leaving invalid input available to edit."""
    widget = event.widget
    try:
        result = formatting(get_input_value(widget), format_type)
    except ValueError:
        return
    start = "1.0" if isinstance(widget, tk.Text) else 0
    widget.delete(start, tk.END)
    widget.insert(start, result)


def window(title: str = "DocGen", size: tuple[float, float] = (0.8, 0.8)) -> tk.Tk:
    """Create the application's single root with an available native theme."""
    root = tk.Tk()
    root.protocol("WM_DELETE_WINDOW", root.destroy)
    if platform.system() == "Darwin":
        # The application/Dock Quit action is distinct from closing a window.
        # Resolve the current protocol dynamically so a modal editor can guard it.
        def quit_application() -> None:
            root.tk.eval(root.protocol("WM_DELETE_WINDOW"))

        commands = cast(TclCommands, root.tk)
        commands.createcommand("::tk::mac::Quit", quit_application)
    root.title(title)
    style = ttk.Style(root)
    theme = {"Darwin": "aqua", "Windows": "vista"}.get(platform.system(), "clam")
    if theme in style.theme_names():
        style.theme_use(theme)
    if platform.system() == "Windows" and ICON_PATH.is_file():
        icon_window = cast(IconWindow, root)
        icon_window.iconbitmap(str(ICON_PATH))
    width = min(
        root.winfo_screenwidth(), max(760, int(root.winfo_screenwidth() * size[0]))
    )
    height = min(
        root.winfo_screenheight(), max(560, int(root.winfo_screenheight() * size[1]))
    )
    root.geometry(f"{width}x{height}")
    root.minsize(min(width, 760), min(height, 560))
    style.configure("Error.TLabel", foreground="#b42318")
    return root


def default_pdf_name(values: Mapping[str, str]) -> str:
    """Build a portable, bounded filename from the property street."""
    street = re.sub(r"[^\w .-]", "", values.get("property_street", ""), flags=re.ASCII)
    street = " ".join(street.split()).strip(" .")[:80].rstrip(" .")
    return f"Transaction Worksheet{' - ' + street if street else ''}.pdf"


class DocumentForm(ttk.Frame):
    """Scrollable form grouped by field sections with inline validation."""

    def __init__(
        self, parent: tk.Misc, document: DocumentSpec, on_change: Callable[[], None]
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.on_change = on_change
        self.widgets: dict[str, InputWidget] = {}
        self.variables: dict[str, tk.StringVar] = {}
        self.errors: dict[str, tk.StringVar] = {}
        self._updating = False
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.viewport = cast(Scrollable, self.canvas)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.viewport.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.content = ttk.Frame(self.canvas, padding=(20, 8, 20, 20))
        content_id = self.canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind(
            "<Configure>",
            lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.bind(
            "<Configure>",
            lambda event: self.canvas.itemconfigure(content_id, width=event.width),
        )
        self.content.columnconfigure(0, weight=1)
        sections: dict[str, ttk.LabelFrame] = {}
        rows: dict[str, int] = {}
        for field in document.fields:
            if field.section not in sections:
                section = ttk.LabelFrame(self.content, text=field.section, padding=14)
                section.grid(row=len(sections), column=0, sticky="ew", pady=(0, 16))
                section.columnconfigure(1, weight=1)
                sections[field.section] = section
                rows[field.section] = 0
            self._add_field(sections[field.section], rows[field.section], field)
            rows[field.section] += 2
        self._scroll_tag = f"DocGenScroll{id(self)}"
        self._scroll_sequences = ["<MouseWheel>", "<Button-4>", "<Button-5>"]
        for sequence in self._scroll_sequences:
            self.bind_class(self._scroll_tag, sequence, self._scroll)
        if platform.system() == "Darwin":
            try:
                self.bind_class(
                    self._scroll_tag, "<TouchpadScroll>", self._touchpad_scroll
                )
            except tk.TclError:
                # Tk 8 uses MouseWheel for trackpads; Tk 9 adds TouchpadScroll.
                pass
            else:
                self._scroll_sequences.append("<TouchpadScroll>")
        self._apply_scroll_tag(self)

    def _add_field(self, section: ttk.LabelFrame, row: int, field: FieldSpec) -> None:
        label = field.label + (" *" if field.required else "")
        ttk.Label(section, text=label, width=26, anchor="w").grid(
            row=row, column=0, sticky="nw", padx=(0, 16), pady=(5, 0)
        )
        widget: InputWidget
        if field.kind == "paragraph":
            widget = Textbox(section, width=38, height=4, wrap="word", undo=True)

            def text_changed(_event: tk.Event[tk.Misc]) -> None:
                self._text_changed(field.key)

            widget.bind("<<Modified>>", text_changed)
            widget.bind("<Tab>", self._next_field)
            widget.bind(
                "<Shift-Tab>", lambda event: self._next_field(event, reverse=True)
            )
            widget.bind(
                "<ISO_Left_Tab>", lambda event: self._next_field(event, reverse=True)
            )
        else:
            variable = tk.StringVar(self)
            self.variables[field.key] = variable
            if field.choices:
                widget = ttk.Combobox(
                    section,
                    textvariable=variable,
                    values=field.choices,
                    state="readonly",
                )
            else:
                widget = ttk.Entry(section, textvariable=variable)
            variable.trace_add("write", self._variable_changed)

        def validate(_event: tk.Event[tk.Misc]) -> None:
            self.validate_field(field)

        def reveal(_event: tk.Event[tk.Misc]) -> None:
            self._reveal_field(field.key)

        widget.grid(row=row, column=1, sticky="ew", pady=(3, 0))
        widget.bind("<FocusOut>", validate)
        widget.bind("<FocusIn>", reveal)
        if isinstance(widget, ttk.Combobox):
            widget.bind("<<ComboboxSelected>>", validate)
        self.widgets[field.key] = widget
        error = tk.StringVar(self)
        self.errors[field.key] = error
        hints = {
            "date": "M/D/YYYY or YYYY-MM-DD",
            "phone": "10 digits; optional +1 country code",
        }
        if field.kind in hints:
            ttk.Label(section, text=hints[field.kind], wraplength=190).grid(
                row=row + 1, column=0, sticky="nw", padx=(0, 16), pady=(0, 4)
            )
        ttk.Label(
            section, textvariable=error, style="Error.TLabel", wraplength=480
        ).grid(row=row + 1, column=1, sticky="w", pady=(0, 4))

    def _apply_scroll_tag(self, widget: tk.Misc) -> None:
        # A unique bindtag scopes scrolling to this form. Text and combobox widgets
        # retain their native scrolling rather than redirecting it to the form.
        if not isinstance(widget, tk.Text | ttk.Combobox | ttk.Scrollbar):
            widget.bindtags((*widget.bindtags(), self._scroll_tag))
        for child in widget.winfo_children():
            self._apply_scroll_tag(child)

    def _scroll(self, event: tk.Event[tk.Misc]) -> str:
        if event.num == 4:
            amount = -1
        elif event.num == 5:
            amount = 1
        elif platform.system() == "Darwin":
            amount = -event.delta
        elif not event.delta:
            return "break"
        else:
            amount = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.canvas.yview_scroll(amount, "units")
        return "break"

    def _touchpad_scroll(self, event: tk.Event[tk.Misc]) -> str:
        delta = event.delta & 0xFFFF
        if delta >= 0x8000:
            delta -= 0x10000
        first, _ = self.viewport.yview()
        self.canvas.yview_moveto(first - delta * 0.001)
        return "break"

    @staticmethod
    def _next_field(event: tk.Event[tk.Misc], *, reverse: bool = False) -> str:
        widget = event.widget.tk_focusPrev() if reverse else event.widget.tk_focusNext()
        if widget is not None:
            widget.focus_set()
        return "break"

    def destroy(self) -> None:
        for sequence in self._scroll_sequences:
            self.unbind_class(self._scroll_tag, sequence)
        super().destroy()

    def _changed(self) -> None:
        if not self._updating:
            self.on_change()

    def _variable_changed(self, *_args: str) -> None:
        self._changed()

    def _text_changed(self, key: str) -> None:
        widget = self.widgets[key]
        if isinstance(widget, Textbox) and widget.edit_modified():
            widget.edit_modified(False)
            self._changed()

    def collect(self) -> dict[str, str]:
        """Snapshot widget values on the UI thread."""
        return {key: get_input_value(widget) for key, widget in self.widgets.items()}

    def set_values(self, values: Mapping[str, str]) -> None:
        """Restore values without interpreting unfinished draft input."""
        self._updating = True
        try:
            for key, widget in self.widgets.items():
                value = values.get(key, "")
                if isinstance(widget, Textbox):
                    widget.delete("1.0", tk.END)
                    widget.insert("1.0", value)
                    widget.edit_modified(False)
                else:
                    self.variables[key].set(value)
                self.errors[key].set("")
        finally:
            self._updating = False
        self.on_change()

    def validate_field(self, field: FieldSpec) -> None:
        """Validate and normalize one field without discarding invalid text."""
        raw = get_input_value(self.widgets[field.key])
        try:
            validated = validate_data({field.key: raw}, (field,))
        except ValidationError as error:
            self.errors[field.key].set(error.errors.get(field.key, str(error)))
            return
        self.errors[field.key].set("")
        value = validated[field.key]
        if value == raw:
            return
        widget = self.widgets[field.key]
        if isinstance(widget, Textbox):
            widget.delete("1.0", tk.END)
            widget.insert("1.0", value)
        else:
            self.variables[field.key].set(value)

    def show_errors(self, errors: Mapping[str, str]) -> None:
        """Show validation errors and scroll the first invalid field into view."""
        for key, variable in self.errors.items():
            variable.set(errors.get(key, ""))
        first = next((self.widgets[key] for key in self.widgets if key in errors), None)
        if first is not None:
            self._reveal_field(next(key for key in self.widgets if key in errors))
            first.focus_set()

    def _reveal_field(self, key: str) -> None:
        """Keep keyboard focus visible without moving an already visible field."""
        self.update_idletasks()
        widget = self.widgets[key]
        top = widget.winfo_rooty() - self.canvas.winfo_rooty()
        bottom = top + widget.winfo_height()
        viewport_height = self.canvas.winfo_height()
        if top >= 12 and bottom <= viewport_height - 12:
            return
        offset = widget.winfo_rooty() - self.content.winfo_rooty()
        target = (
            offset - 12
            if top < 12
            else offset + widget.winfo_height() - viewport_height + 12
        )
        self.canvas.yview_moveto(max(0, target) / max(1, self.content.winfo_height()))

    def set_enabled(self, enabled: bool) -> None:
        """Prevent edits while a job uses a snapshot of the form."""
        for widget in self.widgets.values():
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                widget.configure(state="normal" if enabled else "disabled")


class Application:
    """One application root owning form state, drafts, and background work."""

    def __init__(self, root: tk.Tk, settings: Settings) -> None:
        self.root = root
        self.settings = settings
        self.document = get_document(settings)
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="docgen")
        self.future: Future[Path] | Future[list[str]] | Future[None] | None = None
        self.job_kind: Literal["generate", "check", "open"] = "generate"
        self.saved_pdf: Path | None = None
        self.draft_path: Path | None = None
        self.baseline: dict[str, str] = {}
        self.form: DocumentForm | None = None
        self.status = tk.StringVar(root, "Ready. Required fields are marked with *.")
        self.open_after = tk.BooleanVar(root, value=True)
        self.toolbar = ttk.Frame(root, padding=(20, 16))
        self.toolbar.pack(fill="x")
        self.controls: list[ttk.Button] = []
        for text, command in (
            ("Open Draft…", self.open_draft),
            ("Save Draft…", self.save_draft),
            ("Settings…", self.edit_settings),
            ("Check Setup", self.check_setup),
        ):
            button = ttk.Button(self.toolbar, text=text, command=command)
            button.pack(side="left", padx=(0, 8))
            self.controls.append(button)
        self.actions = ttk.Frame(root, padding=(20, 12))
        self.actions.pack(side="bottom", fill="x")
        self.actions.columnconfigure(0, weight=1)
        status_label = ttk.Label(self.actions, textvariable=self.status, wraplength=680)
        status_label.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        status_label.bind(
            "<Configure>",
            lambda event: status_label.configure(wraplength=max(240, event.width)),
        )
        self.generate_button = ttk.Button(
            self.actions, text="Generate PDF…", command=self.generate_pdf
        )
        self.generate_button.grid(row=1, column=2, sticky="e", padx=(12, 0))
        self.controls.append(self.generate_button)
        self.open_check = ttk.Checkbutton(
            self.actions, text="Open PDF when saved", variable=self.open_after
        )
        self.open_check.grid(row=1, column=1, sticky="e")
        self.progress = ttk.Progressbar(self.actions, mode="indeterminate", length=120)
        self.progress.grid(row=1, column=0, sticky="w", padx=(0, 12))
        self._build_form()
        self.baseline = self._form().collect()
        self._changed()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        modifier = "Command" if platform.system() == "Darwin" else "Control"
        self.root.bind(f"<{modifier}-s>", lambda _: self.save_draft())
        self.root.bind(f"<{modifier}-o>", lambda _: self.open_draft())

    def _form(self) -> DocumentForm:
        if self.form is None:
            raise RuntimeError("The document form has not been initialized.")
        return self.form

    def _build_form(self, values: Mapping[str, str] | None = None) -> None:
        if self.form is not None:
            self.form.destroy()
        self.form = DocumentForm(self.root, self.document, self._changed)
        self.form.pack(fill="both", expand=True)
        if values is not None:
            self.form.set_values(values)

    def _changed(self) -> None:
        dirty = self.form is not None and self.form.collect() != self.baseline
        name = self.draft_path.name if self.draft_path else "Untitled draft"
        self.root.title(
            f"{'* ' if dirty else ''}{name} — {self.document.display_name} — DocGen"
        )

    def _confirm_discard(self) -> bool:
        if self._form().collect() == self.baseline:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved draft",
            "Save your changes to a draft before continuing?",
            parent=self.root,
        )
        if answer is None:
            return False
        return self.save_draft() if answer else True

    def save_draft(self) -> bool:
        """Save all entered input, including values that are not yet valid."""
        if self.future is not None:
            return False
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save Draft",
            defaultextension=".json",
            initialdir=str(
                self.draft_path.parent if self.draft_path else self.settings.output_dir
            ),
            initialfile=self.draft_path.name
            if self.draft_path
            else "Transaction Draft.json",
            filetypes=[("DocGen drafts", "*.json")],
            confirmoverwrite=True,
        )
        if not path:
            return False
        values = self._form().collect()
        try:
            self.draft_path = save_draft(
                Path(path),
                self.document.key,
                values,
                (field.key for field in self.document.fields),
            )
        except DraftError as error:
            messagebox.showerror("Could not save draft", str(error), parent=self.root)
            return False
        self.baseline = values
        self._changed()
        self.status.set(f"Draft saved: {self.draft_path}")
        return True

    def open_draft(self) -> None:
        """Load a compatible draft after resolving unsaved work."""
        if self.future is not None or not self._confirm_discard():
            return
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Open Draft",
            filetypes=[("DocGen drafts", "*.json")],
        )
        if not selected:
            return
        try:
            values = load_draft(
                Path(selected),
                self.document.key,
                (field.key for field in self.document.fields),
            )
        except DraftError as error:
            messagebox.showerror("Could not open draft", str(error), parent=self.root)
            return
        self.draft_path = Path(selected)
        self.baseline = values
        self._form().set_values(values)
        self.status.set(f"Draft opened: {selected}")

    def edit_settings(self) -> None:
        """Open the settings editor without replacing entered document values."""
        if self.future is not None:
            return
        from .settings_dialog import edit_settings

        def saved(settings: Settings) -> None:
            values = self._form().collect()
            self.settings = settings
            self.document = get_document(settings)
            self._build_form(values)
            self.status.set("Settings saved. Existing form values were preserved.")

        edit_settings(self.root, self.settings.config_path, saved)

    def generate_pdf(self) -> None:
        """Validate the complete form and submit an immutable snapshot to a worker."""
        if self.future is not None:
            return
        try:
            values = validate_data(self._form().collect(), self.document.fields)
        except ValidationError as error:
            self._form().show_errors(error.errors)
            self.status.set("Correct the highlighted fields before generating the PDF.")
            return
        self._form().show_errors({})
        selected = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save PDF",
            defaultextension=".pdf",
            initialdir=str(self.settings.output_dir),
            initialfile=default_pdf_name(values),
            filetypes=[("PDF documents", "*.pdf")],
            confirmoverwrite=False,
        )
        if not selected:
            return
        destination = Path(selected)
        overwrite = destination.exists()
        if overwrite and not messagebox.askyesno(
            "Replace PDF?",
            f"Replace the existing file?\n{destination}",
            parent=self.root,
        ):
            return
        self.job_kind = "generate"
        self.future = self.executor.submit(
            generate, values, self.settings, destination, overwrite=overwrite
        )
        self._set_busy(True, "Generating PDF…")
        self.root.after(75, self._poll)

    def check_setup(self) -> None:
        """Check external PDF dependencies without blocking the form."""
        if self.future is not None:
            return
        self.job_kind = "check"
        self.future = self.executor.submit(check_dependencies, self.settings.logo_path)
        self._set_busy(True, "Checking PDF setup…")
        self.root.after(75, self._poll)

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        for control in self.controls:
            control.configure(state="disabled" if busy else "normal")
        self.open_check.configure(state="disabled" if busy else "normal")
        self._form().set_enabled(not busy)
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        if status is not None:
            self.status.set(status)

    def _poll(self) -> None:
        future = self.future
        if future is None:
            return
        if not future.done():
            self.root.after(75, self._poll)
            return
        self.future = None
        self._set_busy(False)
        try:
            result = future.result()
        except PdfOpenError as error:
            self.status.set(f"PDF saved: {self.saved_pdf}")
            messagebox.showwarning(
                "PDF saved",
                f"Your PDF was saved to:\n{self.saved_pdf}\n\n{error}",
                parent=self.root,
            )
            return
        except (DocGenError, OSError, ValueError) as error:
            self.status.set(
                "PDF setup check failed."
                if self.job_kind == "check"
                else f"PDF saved: {self.saved_pdf}"
                if self.job_kind == "open"
                else "PDF generation failed."
            )
            messagebox.showerror("DocGen", str(error), parent=self.root)
            details = getattr(error, "details", "")
            if details:
                self._show_details("Compilation diagnostics", str(details))
            return
        except Exception:
            logger.exception("Unexpected background job failure")
            self.status.set(
                "An unexpected error occurred. Your form is still available."
            )
            messagebox.showerror(
                "Unexpected error",
                "Your form has been preserved. Diagnostic details will open in a separate window.",
                parent=self.root,
            )
            self._show_details("Unexpected error diagnostics", traceback.format_exc())
            return
        if self.job_kind == "open":
            self.status.set(f"PDF saved: {self.saved_pdf}")
            return
        if isinstance(result, list):
            self.status.set(
                "PDF setup needs attention." if result else "PDF setup is ready."
            )
            if result:
                self._show_details("PDF setup", "\n\n".join(result))
            else:
                messagebox.showinfo(
                    "PDF setup",
                    "The PDF compiler and required resources are available.",
                    parent=self.root,
                )
            return
        if result is None:
            raise RuntimeError("A PDF generation job returned no output path.")
        self.saved_pdf = result
        self.status.set(f"PDF saved: {result}")
        if self.open_after.get():
            self.job_kind = "open"
            self.future = self.executor.submit(open_pdf, result)
            self._set_busy(True, f"PDF saved: {result}. Opening viewer…")
            self.root.after(75, self._poll)

    def _show_details(self, title: str, details: str) -> None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("760x460")
        text = Textbox(dialog, wrap="word", padx=12, pady=12)
        text.pack(fill="both", expand=True)
        text.insert("1.0", details)
        text.configure(state="disabled")
        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=12)
        dialog.transient(self.root)

    def close(self) -> None:
        """Protect unsaved input and never abandon an active output write."""
        if self.future is not None:
            messagebox.showinfo(
                "DocGen is working",
                "Wait for the current operation to finish before closing.",
                parent=self.root,
            )
            return
        if self._confirm_discard():
            self.executor.shutdown(wait=False, cancel_futures=True)
            self.root.destroy()
