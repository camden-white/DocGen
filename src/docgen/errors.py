"""Expected application failures that callers can present to users."""


class DocGenError(Exception):
    """Base class for an expected, actionable application failure."""


class ConfigurationError(DocGenError):
    """Configuration is missing, invalid, or cannot be saved."""


class ValidationError(DocGenError):
    """One or more form fields require correction before generation."""

    def __init__(self, errors: dict[str, str]) -> None:
        """Retain errors by field identifier and provide a readable summary."""
        self.errors = dict(errors)
        message = "\n".join(f"{field}: {message}" for field, message in errors.items())
        super().__init__(message or "Please correct the invalid input.")


class PdfCompilationError(DocGenError):
    """LaTeX could not produce a usable PDF."""

    def __init__(self, message: str, *, details: str | None = None) -> None:
        """Keep diagnostics separate from the concise user-facing message."""
        self.details = details
        super().__init__(message)


class PdfOpenError(DocGenError):
    """A PDF was saved successfully but could not be opened."""
