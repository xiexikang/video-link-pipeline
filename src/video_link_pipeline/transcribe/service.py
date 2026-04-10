"""High-level transcription service interface."""

from __future__ import annotations


def transcribe_path(path: str) -> dict[str, object]:
    """Placeholder transcription service."""
    return {"success": False, "path": path, "message": "transcribe service not implemented"}
