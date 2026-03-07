"""
Custom exceptions for Mundaneum API.

These provide clean error responses and consistent error handling.
"""

from typing import Any


class MundaneumError(Exception):
    """Base exception for all Mundaneum errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        detail: dict[str, Any] | None = None,
    ):
        self.message = message
        self.status_code = status_code
        self.detail = detail or {}
        super().__init__(message)


class NotFoundError(MundaneumError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str | None = None):
        message = f"{resource} not found"
        if identifier:
            message = f"{resource} '{identifier}' not found"
        super().__init__(message, status_code=404)


class ValidationError(MundaneumError):
    """Request validation failed."""

    def __init__(self, message: str, errors: list[dict] | None = None):
        super().__init__(message, status_code=422, detail={"errors": errors or []})


class ServiceUnavailableError(MundaneumError):
    """External service is unavailable."""

    def __init__(self, service: str, reason: str | None = None):
        message = f"{service} is unavailable"
        if reason:
            message = f"{message}: {reason}"
        super().__init__(message, status_code=503)


class ConflictError(MundaneumError):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str):
        super().__init__(message, status_code=409)


class IngestError(MundaneumError):
    """BibTeX import failed."""

    def __init__(self, message: str, errors: int = 0):
        super().__init__(message, status_code=400, detail={"errors": errors})
