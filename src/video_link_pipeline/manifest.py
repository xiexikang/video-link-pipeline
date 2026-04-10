"""Manifest helpers for stable machine-readable outputs."""

from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .errors import ConfigError

SCHEMA_VERSION = "1.0"


@dataclass(slots=True)
class Manifest:
    """In-memory representation of a pipeline manifest."""

    path: Path
    data: dict[str, Any] = field(default_factory=dict)


def create_manifest(
    path: str | Path,
    *,
    command: str | None = None,
    input_data: dict[str, Any] | None = None,
    config_effective: dict[str, Any] | None = None,
) -> Manifest:
    """Create a new manifest object with v1 defaults."""
    timestamp = _utc_now()
    data = {
        "schema_version": SCHEMA_VERSION,
        "created_at": timestamp,
        "updated_at": timestamp,
        "command": command,
        "input": input_data or {"url": None, "input_path": None},
        "config_effective": config_effective or {},
        "artifacts": {},
        "execution": {},
    }
    return Manifest(path=Path(path), data=data)


def load_manifest(path: str | Path) -> Manifest:
    """Load an existing manifest or return a new default manifest object."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        return create_manifest(manifest_path)

    try:
        with manifest_path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ConfigError(
            f"failed to parse manifest file: {manifest_path}",
            hint=str(exc),
        ) from exc

    if not isinstance(loaded, dict):
        raise ConfigError(f"manifest file must contain a JSON object: {manifest_path}")

    manifest = create_manifest(manifest_path)
    manifest.data = _deep_merge_dicts(manifest.data, loaded)
    return manifest


def merge_manifest(manifest: Manifest, patch: dict[str, Any]) -> Manifest:
    """Deep-merge a partial update into a manifest."""
    if not isinstance(patch, dict):
        raise ConfigError("manifest patch must be a mapping")

    merged = _deep_merge_dicts(manifest.data, patch)
    merged.setdefault("schema_version", SCHEMA_VERSION)
    merged.setdefault("created_at", _utc_now())
    merged["updated_at"] = _utc_now()
    return Manifest(path=manifest.path, data=merged)


def update_manifest(
    manifest: Manifest,
    *,
    command: str | None = None,
    input_data: dict[str, Any] | None = None,
    config_effective: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> Manifest:
    """Apply command-oriented updates to a manifest."""
    patch: dict[str, Any] = {}
    if command is not None:
        patch["command"] = command
    if input_data:
        patch["input"] = input_data
    if config_effective:
        patch["config_effective"] = config_effective
    if artifacts:
        patch["artifacts"] = artifacts
    if execution:
        patch["execution"] = execution
    return merge_manifest(manifest, patch)


def write_manifest(manifest: Manifest) -> Path:
    """Atomically write a manifest to disk."""
    manifest.path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest.data, ensure_ascii=False, indent=2) + os.linesep

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=manifest.path.parent,
            prefix=f".{manifest.path.stem}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)

        os.replace(temp_path, manifest.path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)

    return manifest.path


def upsert_manifest(
    path: str | Path,
    *,
    command: str | None = None,
    input_data: dict[str, Any] | None = None,
    config_effective: dict[str, Any] | None = None,
    artifacts: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> Manifest:
    """Load, update, and persist a manifest in one call."""
    manifest = load_manifest(path)
    manifest = update_manifest(
        manifest,
        command=command,
        input_data=input_data,
        config_effective=config_effective,
        artifacts=artifacts,
        execution=execution,
    )
    write_manifest(manifest)
    return manifest


def _deep_merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dicts(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
