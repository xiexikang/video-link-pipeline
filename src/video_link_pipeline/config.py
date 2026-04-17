"""Configuration loading and schema utilities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

from .errors import ConfigError

DEFAULT_CONFIG: dict[str, Any] = {
    "output_dir": "./output",
    "group_output_by_site": False,
    "temp_dir": "./temp",
    "download": {
        "quality": "best",
        "format": "mp4",
        "subtitles_langs": ["zh", "en"],
        "write_subtitles": True,
        "write_auto_subs": True,
        "cookies_from_browser": None,
        "cookie_file": None,
        "selenium": "auto",
    },
    "whisper": {
        "model": "small",
        "engine": "auto",
        "language": "auto",
        "device": "auto",
        "compute_type": "int8",
    },
    "summary": {
        "enabled": True,
        "provider": "claude",
        "model": "claude-3-5-sonnet-20241022",
        "base_url": None,
        "max_tokens": 4096,
        "temperature": 0.3,
    },
    "api_keys": {
        "claude": None,
        "openai": None,
        "gemini": None,
        "deepseek": None,
        "kimi": None,
        "moonshot": None,
        "minimax": None,
        "glm": None,
        "zhipu": None,
    },
}

ENV_MAPPING: dict[str, tuple[str, ...]] = {
    "VLP_OUTPUT_DIR": ("output_dir",),
    "VLP_GROUP_OUTPUT_BY_SITE": ("group_output_by_site",),
    "VLP_TEMP_DIR": ("temp_dir",),
    "VLP_DOWNLOAD_QUALITY": ("download", "quality"),
    "VLP_DOWNLOAD_FORMAT": ("download", "format"),
    "VLP_DOWNLOAD_SUBTITLES_LANGS": ("download", "subtitles_langs"),
    "VLP_DOWNLOAD_WRITE_SUBTITLES": ("download", "write_subtitles"),
    "VLP_DOWNLOAD_WRITE_AUTO_SUBS": ("download", "write_auto_subs"),
    "VLP_DOWNLOAD_COOKIES_FROM_BROWSER": ("download", "cookies_from_browser"),
    "VLP_DOWNLOAD_COOKIE_FILE": ("download", "cookie_file"),
    "VLP_DOWNLOAD_SELENIUM": ("download", "selenium"),
    "VLP_WHISPER_MODEL": ("whisper", "model"),
    "VLP_WHISPER_ENGINE": ("whisper", "engine"),
    "VLP_WHISPER_LANGUAGE": ("whisper", "language"),
    "VLP_WHISPER_DEVICE": ("whisper", "device"),
    "VLP_WHISPER_COMPUTE_TYPE": ("whisper", "compute_type"),
    "VLP_SUMMARY_ENABLED": ("summary", "enabled"),
    "VLP_SUMMARY_PROVIDER": ("summary", "provider"),
    "VLP_SUMMARY_MODEL": ("summary", "model"),
    "VLP_SUMMARY_BASE_URL": ("summary", "base_url"),
    "VLP_SUMMARY_MAX_TOKENS": ("summary", "max_tokens"),
    "VLP_SUMMARY_TEMPERATURE": ("summary", "temperature"),
    "ANTHROPIC_API_KEY": ("api_keys", "claude"),
    "OPENAI_API_KEY": ("api_keys", "openai"),
    "GEMINI_API_KEY": ("api_keys", "gemini"),
    "DEEPSEEK_API_KEY": ("api_keys", "deepseek"),
    "KIMI_API_KEY": ("api_keys", "kimi"),
    "MOONSHOT_API_KEY": ("api_keys", "moonshot"),
    "MINIMAX_API_KEY": ("api_keys", "minimax"),
    "GLM_API_KEY": ("api_keys", "glm"),
    "ZHIPU_API_KEY": ("api_keys", "zhipu"),
}

SECRET_KEYS = {"api_keys", "api_key"}
ENUM_CONSTRAINTS: dict[tuple[str, ...], set[str]] = {
    ("download", "selenium"): {"auto", "on", "off"},
    ("whisper", "engine"): {"auto", "faster", "openai"},
    ("whisper", "device"): {"auto", "cpu", "cuda"},
    ("whisper", "compute_type"): {"int8", "float16", "float32"},
}


@dataclass(slots=True)
class ConfigBundle:
    """Container for raw and effective configuration state."""

    source_path: Path | None
    raw_config: dict[str, Any] = field(default_factory=dict)
    env_config: dict[str, Any] = field(default_factory=dict)
    effective_config: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def load_config(
    config_path: str | Path = "config.yaml",
    overrides: dict[str, Any] | None = None,
) -> ConfigBundle:
    """Load configuration from defaults, YAML, dotenv/environment, and CLI overrides."""
    path = Path(config_path)
    warnings: list[str] = []
    file_config = _load_yaml_config(path)
    _merge_legacy_summary_api_keys(file_config, warnings)

    env_values = _load_env_values(path.parent if path.parent != Path("") else Path.cwd())
    env_config = _build_env_config(env_values)

    effective = deepcopy(DEFAULT_CONFIG)
    _deep_merge(effective, file_config)
    _deep_merge(effective, env_config)

    cli_overrides = overrides or {}
    _deep_merge(effective, _prune_nones(cli_overrides))

    _validate_config(effective)

    return ConfigBundle(
        source_path=path if path.exists() else None,
        raw_config=file_config,
        env_config=env_config,
        effective_config=effective,
        warnings=warnings,
    )


def redact_config(config: dict[str, Any]) -> dict[str, Any]:
    """Return a redacted copy of config data for logging or manifests."""
    return _redact_mapping(config)


def _load_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse config file: {path}", hint=str(exc)) from exc

    if not isinstance(loaded, dict):
        raise ConfigError(f"config file must contain a mapping: {path}")

    return loaded


def _load_env_values(base_dir: Path) -> dict[str, str]:
    dotenv_path = base_dir / ".env"
    values: dict[str, str] = {}
    if dotenv_path.exists():
        values.update({k: v for k, v in dotenv_values(dotenv_path).items() if v is not None})

    for key in ENV_MAPPING:
        import os
        value = os.getenv(key)
        if value is not None:
            values[key] = value

    return values


def _build_env_config(env_values: dict[str, str]) -> dict[str, Any]:
    env_config: dict[str, Any] = {}
    for env_key, path_parts in ENV_MAPPING.items():
        if env_key not in env_values:
            continue
        template = _schema_value_for_path(path_parts)
        converted = _convert_scalar(env_values[env_key], template)
        _set_nested(env_config, path_parts, converted)
    return env_config


def _merge_legacy_summary_api_keys(config: dict[str, Any], warnings: list[str]) -> None:
    summary = config.get("summary")
    if not isinstance(summary, dict):
        return

    legacy_api_keys = summary.pop("api_keys", None)
    if legacy_api_keys is None:
        return
    if not isinstance(legacy_api_keys, dict):
        raise ConfigError("summary.api_keys must be a mapping when present")

    warnings.append(
        "legacy config key 'summary.api_keys' is deprecated; move provider keys to top-level 'api_keys'."
    )
    api_keys = config.setdefault("api_keys", {})
    if not isinstance(api_keys, dict):
        raise ConfigError("api_keys must be a mapping when present")

    for key, value in legacy_api_keys.items():
        api_keys.setdefault(key, value)


def _schema_value_for_path(path_parts: tuple[str, ...]) -> Any:
    current: Any = DEFAULT_CONFIG
    for part in path_parts:
        current = current[part]
    return current


def _convert_scalar(raw_value: str, template: Any) -> Any:
    text = raw_value.strip()
    if text.lower() in {"null", "none", ""}:
        return None
    if isinstance(template, bool):
        lowered = text.lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
        raise ConfigError(f"invalid boolean value: {raw_value}")
    if isinstance(template, int) and not isinstance(template, bool):
        try:
            return int(text)
        except ValueError as exc:
            raise ConfigError(f"invalid integer value: {raw_value}") from exc
    if isinstance(template, float):
        try:
            return float(text)
        except ValueError as exc:
            raise ConfigError(f"invalid float value: {raw_value}") from exc
    if isinstance(template, list):
        return [item.strip() for item in text.split(",") if item.strip()]
    return text


def _set_nested(target: dict[str, Any], path_parts: tuple[str, ...], value: Any) -> None:
    current = target
    for part in path_parts[:-1]:
        current = current.setdefault(part, {})
    current[path_parts[-1]] = value


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _prune_nones(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _prune_nones(item)
            for key, item in value.items()
            if item is not None and _prune_nones(item) is not None
        }
    return value


def _validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get("api_keys"), dict):
        raise ConfigError("api_keys must be a mapping")

    for path_parts, allowed_values in ENUM_CONSTRAINTS.items():
        value = _get_nested(config, path_parts)
        if value not in allowed_values:
            joined = ".".join(path_parts)
            allowed = ", ".join(sorted(allowed_values))
            raise ConfigError(f"invalid value for {joined}: {value}", hint=f"allowed values: {allowed}")


def _get_nested(source: dict[str, Any], path_parts: tuple[str, ...]) -> Any:
    current: Any = source
    for part in path_parts:
        if not isinstance(current, dict) or part not in current:
            raise ConfigError(f"missing config key: {'.'.join(path_parts)}")
        current = current[part]
    return current


def _redact_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if key in SECRET_KEYS:
                redacted[key] = _redact_secret_block(item)
            else:
                redacted[key] = _redact_mapping(item)
        return redacted
    if isinstance(value, list):
        return [_redact_mapping(item) for item in value]
    return value


def _redact_secret_block(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: ("***" if item else None) for key, item in value.items()}
    if isinstance(value, list):
        return ["***" for _ in value]
    if value is None:
        return None
    return "***"
