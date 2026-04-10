"""Shared exception types and error codes."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VlpError(Exception):
    """Base exception for domain-specific CLI failures."""

    message: str
    error_code: str = "VLP_ERROR"

    def __str__(self) -> str:
        return self.message


class ConfigError(VlpError):
    """Raised when configuration resolution fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="CONFIG_ERROR")


class DependencyMissingError(VlpError):
    """Raised when an optional or required dependency is unavailable."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="DEPENDENCY_MISSING")
