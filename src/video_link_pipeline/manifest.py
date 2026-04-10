"""Manifest helpers for stable machine-readable outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Manifest:
    """In-memory representation of a pipeline manifest."""

    path: Path
    data: dict[str, Any] = field(default_factory=dict)


def load_manifest(path: str | Path) -> Manifest:
    """Load an existing manifest or create an empty in-memory manifest."""
    return Manifest(path=Path(path), data={})


def merge_manifest(manifest: Manifest, patch: dict[str, Any]) -> Manifest:
    """Merge a partial update into the manifest.

    The real merge semantics are introduced in M1a-6.
    """
    merged = dict(manifest.data)
    merged.update(patch)
    return Manifest(path=manifest.path, data=merged)
