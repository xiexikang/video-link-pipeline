"""Environment diagnostics helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DoctorCheck:
    """Represents one doctor check result."""

    name: str
    ok: bool
    detail: str


def run_checks() -> list[DoctorCheck]:
    """Return the current set of diagnostics.

    Placeholder implementation for M2.
    """
    return [DoctorCheck(name="package", ok=True, detail="CLI package scaffold is installed.")]
