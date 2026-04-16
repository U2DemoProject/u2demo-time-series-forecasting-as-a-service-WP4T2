class ModelNotFoundError(Exception):
    """Raised when model metadata or artifacts cannot be found."""


class JobNotFoundError(Exception):
    """Raised when a job id cannot be found in the backend."""


class SourceValidationError(Exception):
    """Raised when input sources fail validation or retrieval."""
