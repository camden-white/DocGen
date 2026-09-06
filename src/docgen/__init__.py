"""DocGen package."""

from importlib.metadata import PackageNotFoundError, version

from .ui import Textbox, form_window, window
from .utils import load_documents

try:
    __version__ = version("docgen")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = [
    "Textbox",
    "__version__",
    "form_window",
    "load_documents",
    "window",
]
