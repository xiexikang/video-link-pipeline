"""Shared exception types and stable error codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ERROR_CODES = {
    "CONFIG_ERROR",
    "INPUT_NOT_FOUND",
    "DEPENDENCY_MISSING",
    "DOWNLOAD_FAILED",
    "DOWNLOAD_PRIMARY_FAILED",
    "DOWNLOAD_FALLBACK_PREPARE_FAILED",
    "DOWNLOAD_FALLBACK_RETRY_FAILED",
    "PLATFORM_RESTRICTED",
    "COOKIE_ACCESS_FAILED",
    "FFMPEG_NOT_FOUND",
    "TRANSCRIBE_FAILED",
    "SUMMARY_FAILED",
    "PROVIDER_AUTH_FAILED",
    "NOT_IMPLEMENTED",
    "VLP_ERROR",
}


@dataclass(slots=True)
class VlpError(Exception):
    """Base exception for domain-specific CLI failures."""

    message: str
    error_code: str = "VLP_ERROR"
    hint: str | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.error_code not in ERROR_CODES:
            raise ValueError(f"unknown error code: {self.error_code}")

    def __str__(self) -> str:
        return self.message


class ConfigError(VlpError):
    """Raised when configuration resolution fails."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="CONFIG_ERROR", hint=hint)


class DependencyMissingError(VlpError):
    """Raised when an optional or required dependency is unavailable."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="DEPENDENCY_MISSING", hint=hint)


class InputNotFoundError(VlpError):
    """Raised when a user-provided input path cannot be found."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="INPUT_NOT_FOUND", hint=hint)


class NotImplementedVlpError(VlpError):
    """Raised for commands that are scaffolded but not migrated yet."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="NOT_IMPLEMENTED", hint=hint)
