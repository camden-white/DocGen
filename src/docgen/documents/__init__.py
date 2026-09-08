"""Explicit catalog of supported documents; no import-time discovery or I/O."""

from ..config import Settings
from ..models import DocumentSpec
from .transaction_worksheet import get_document


def load_documents(settings: Settings) -> tuple[DocumentSpec, ...]:
    """Return the available document definitions for the current settings."""
    return (get_document(settings),)
