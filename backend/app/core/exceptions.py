class AppError(Exception):
    """Base error for the application."""


class StageError(AppError):
    """Raised when a pipeline stage fails in a controlled way."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(f"[{stage}] {message}")


class MissingDependencyError(StageError):
    """Raised when a stage's prerequisite artifact is missing."""
