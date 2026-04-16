"""High-level summarization service interface."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from ..errors import ConfigError, InputNotFoundError, VlpError
from .providers import (
    SummaryProviderError,
    summarize_with_claude,
    summarize_with_gemini,
    summarize_with_openai,
)

OPENAI_COMPATIBLE_DEFAULTS: dict[str, tuple[str, str | None]] = {
    "deepseek": ("deepseek-chat", "https://api.deepseek.com"),
    "kimi": ("moonshot-v1-8k", "https://api.moonshot.cn/v1"),
    "moonshot": ("moonshot-v1-8k", "https://api.moonshot.cn/v1"),
    "minimax": ("abab5.5-chat", "https://api.minimax.chat/v1"),
    "glm": ("glm-4", "https://open.bigmodel.cn/api/paas/v4"),
    "zhipu": ("glm-4", "https://open.bigmodel.cn/api/paas/v4"),
}


class SummarizeError(VlpError):
    """Raised when summarization cannot be completed."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="SUMMARY_FAILED", hint=hint)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _local_now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _finalize_timing(
    result: dict[str, object],
    *,
    started_at: str,
    started_at_local: str,
    started_perf: float,
) -> None:
    result["started_at"] = started_at
    result["started_at_local"] = started_at_local
    result["finished_at"] = _utc_now()
    result["finished_at_local"] = _local_now()
    result["elapsed_ms"] = max(0, int(round((perf_counter() - started_perf) * 1000)))


def load_transcript(transcript_path: str | Path) -> str:
    path = Path(transcript_path)
    if not path.exists():
        raise InputNotFoundError(f"transcript file does not exist: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SummarizeError(f"failed to read transcript file: {path}", hint=str(exc)) from exc
    if not content.strip():
        raise SummarizeError("transcript file is empty")
    return content


def resolve_api_key(provider: str, config: dict[str, Any]) -> str:
    api_keys = config.get("api_keys", {})
    key_mapping = {
        "claude": "claude",
        "openai": "openai",
        "gemini": "gemini",
        "deepseek": "deepseek",
        "kimi": "kimi",
        "moonshot": "moonshot",
        "minimax": "minimax",
        "glm": "glm",
        "zhipu": "zhipu",
    }
    key_name = key_mapping.get(provider)
    if not key_name:
        raise ConfigError(f"unsupported summary provider: {provider}")
    api_key = api_keys.get(key_name)
    if not api_key and provider == "kimi":
        api_key = api_keys.get("moonshot")
    if not api_key and provider == "glm":
        api_key = api_keys.get("zhipu")
    if not api_key and provider == "moonshot":
        api_key = api_keys.get("kimi")
    if not api_key and provider == "zhipu":
        api_key = api_keys.get("glm")
    if not api_key:
        raise SummarizeError(f"missing API key for provider: {provider}")
    return str(api_key)


def summarize_transcript(
    *,
    transcript_path: str | Path,
    output_dir: str | Path | None,
    config: dict[str, Any],
) -> dict[str, object]:
    started_at = _utc_now()
    started_at_local = _local_now()
    started_perf = perf_counter()
    transcript = load_transcript(transcript_path)
    transcript_file = Path(transcript_path)
    target_output_dir = Path(output_dir) if output_dir else transcript_file.parent
    target_output_dir.mkdir(parents=True, exist_ok=True)

    summary_config = config.get("summary", {})
    provider = str(summary_config.get("provider", "claude")).lower()
    model = str(summary_config.get("model") or "")
    base_url = summary_config.get("base_url")
    max_tokens = int(summary_config.get("max_tokens", 4096))
    temperature = float(summary_config.get("temperature", 0.3))
    api_key = resolve_api_key(provider, config)

    result: dict[str, object] = {
        "success": False,
        "provider": provider,
        "model": model,
        "summary_file": None,
        "keywords_file": None,
        "one_sentence_summary": "",
        "key_points": [],
        "key_quotes": [],
        "tags": [],
        "evaluation": "",
        "confidence": 0.0,
        "raw_response": "",
        "error": None,
        "started_at": None,
        "started_at_local": None,
        "finished_at": None,
        "finished_at_local": None,
        "elapsed_ms": None,
    }

    try:
        if provider == "claude":
            model = model or "claude-3-5-sonnet-20241022"
            response = summarize_with_claude(
                transcript=transcript,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        elif provider == "openai":
            model = model or "gpt-4o-mini"
            response = summarize_with_openai(
                transcript=transcript,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                base_url=base_url,
            )
        elif provider == "gemini":
            model = model or "gemini-1.5-flash"
            response = summarize_with_gemini(
                transcript=transcript,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        elif provider in OPENAI_COMPATIBLE_DEFAULTS:
            default_model, default_base_url = OPENAI_COMPATIBLE_DEFAULTS[provider]
            model = model or default_model
            response = summarize_with_openai(
                transcript=transcript,
                api_key=api_key,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                base_url=str(base_url or default_base_url),
            )
        else:
            raise ConfigError(f"unsupported summary provider: {provider}")

        result.update(response)
        result["provider"] = provider
        result["model"] = model
        summary_file = target_output_dir / "summary.md"
        keywords_file = target_output_dir / "keywords.json"

        summary_file.write_text(str(result.get("raw_response") or ""), encoding="utf-8")
        keywords_payload = {
            "one_sentence_summary": result.get("one_sentence_summary", ""),
            "key_points": result.get("key_points", []),
            "key_quotes": result.get("key_quotes", []),
            "tags": result.get("tags", []),
            "evaluation": result.get("evaluation", ""),
            "confidence": result.get("confidence", 0.0),
        }
        keywords_file.write_text(json.dumps(keywords_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        result["summary_file"] = str(summary_file)
        result["keywords_file"] = str(keywords_file)
        result["success"] = True
        return result
    except (SummaryProviderError, VlpError) as exc:
        result["error"] = exc.message
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result
    finally:
        _finalize_timing(
            result,
            started_at=started_at,
            started_at_local=started_at_local,
            started_perf=started_perf,
        )
