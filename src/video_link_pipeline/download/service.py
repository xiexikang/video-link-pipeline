"""High-level download service interface."""

from __future__ import annotations


def download_url(url: str) -> dict[str, object]:
    """Placeholder download service."""
    return {"success": False, "url": url, "message": "download service not implemented"}
