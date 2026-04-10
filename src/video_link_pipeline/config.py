"""Configuration loading and schema utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ConfigBundle:
    """Container for raw and effective configuration state."""

    source_path: Path | None = None
    data: dict[str, Any] | None = None


def load_config(config_path: str | Path = "config.yaml") -> ConfigBundle:
    """Load configuration data.

    This is a placeholder scaffold for M1a. Validation and precedence merging land next.
    """
    path = Path(config_path)
    return ConfigBundle(source_path=path if path.exists() else None, data={})


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted copy of config data for logging or manifests."""
    return dict(config)
