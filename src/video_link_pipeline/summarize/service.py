"""High-level summarization service interface."""

from __future__ import annotations


def summarize_transcript(path: str) -> dict[str, object]:
    """Placeholder summary service."""
    return {"success": False, "path": path, "message": "summarize service not implemented"}
