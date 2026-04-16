from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from video_link_pipeline.config import load_config, redact_config
from video_link_pipeline.errors import ConfigError


def test_load_config_applies_cli_env_yaml_precedence(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "output_dir": "./yaml-output",
                "download": {"quality": "yaml-quality"},
                "whisper": {"device": "cpu"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (tmp_path / ".env").write_text(
        "VLP_OUTPUT_DIR=./env-output\nVLP_DOWNLOAD_QUALITY=env-quality\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("VLP_WHISPER_DEVICE", "cuda")

    bundle = load_config(
        config_path=config_path,
        overrides={
            "output_dir": "./cli-output",
            "download": {"quality": "cli-quality"},
        },
    )

    assert bundle.effective_config["output_dir"] == "./cli-output"
    assert bundle.effective_config["download"]["quality"] == "cli-quality"
    assert bundle.effective_config["whisper"]["device"] == "cuda"


def test_load_config_merges_legacy_summary_api_keys_with_warning(monkeypatch, tmp_path: Path) -> None:
    for env_name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "summary": {
                    "provider": "claude",
                    "api_keys": {
                        "claude": "legacy-claude-key",
                        "openai": "legacy-openai-key",
                    },
                }
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bundle = load_config(config_path=config_path)

    assert "deprecated" in bundle.warnings[0]
    assert bundle.effective_config["api_keys"]["claude"] == "legacy-claude-key"
    assert bundle.effective_config["api_keys"]["openai"] == "legacy-openai-key"
    assert "api_keys" not in bundle.effective_config["summary"]


def test_redact_config_masks_api_keys() -> None:
    redacted = redact_config(
        {
            "summary": {"provider": "claude"},
            "api_keys": {"claude": "secret", "openai": None},
        }
    )

    assert redacted["summary"]["provider"] == "claude"
    assert redacted["api_keys"]["claude"] == "***"
    assert redacted["api_keys"]["openai"] is None


def test_load_config_rejects_invalid_enum(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"download": {"selenium": "maybe"}}, sort_keys=False),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="invalid value for download.selenium"):
        load_config(config_path=config_path)
