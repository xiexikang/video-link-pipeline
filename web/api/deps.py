"""Shared FastAPI dependencies."""

from __future__ import annotations

from pathlib import Path

from video_link_pipeline.config import ConfigBundle, load_config, redact_config

DEFAULT_CONFIG_PATH = Path("config.yaml")


def get_config_bundle() -> ConfigBundle:
    """Load the active configuration bundle."""
    return load_config(config_path=DEFAULT_CONFIG_PATH)


def get_output_dir() -> Path:
    bundle = get_config_bundle()
    output_dir = Path(bundle.effective_config["output_dir"])
    if not output_dir.is_absolute():
        output_dir = Path.cwd() / output_dir
    return output_dir.resolve()


def get_redacted_config() -> dict:
    bundle = get_config_bundle()
    return redact_config(bundle.effective_config)
