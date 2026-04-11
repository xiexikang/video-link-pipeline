"""openai-whisper engine integration."""

from __future__ import annotations

from typing import Any

from ..errors import DependencyMissingError


def transcribe_with_openai_whisper(
    *,
    input_path: str,
    model_size: str,
    language: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Run transcription with openai-whisper and return normalized segments."""
    try:
        import whisper
    except Exception as exc:
        raise DependencyMissingError(
            "openai-whisper is not available",
            hint="install openai-whisper to use --engine openai",
        ) from exc

    model = whisper.load_model(model_size)
    fp16 = getattr(model, "device", None) is not None and getattr(model.device, "type", None) != "cpu"
    result = model.transcribe(
        input_path,
        language=None if language == "auto" else language,
        fp16=fp16,
    )

    normalized_segments: list[dict[str, Any]] = []
    for index, segment in enumerate(result.get("segments", [])):
        normalized_segments.append(
            {
                "id": segment.get("id", index),
                "start": float(segment.get("start", 0.0)),
                "end": float(segment.get("end", 0.0)),
                "text": (segment.get("text") or "").strip(),
            }
        )
    return normalized_segments, result.get("language")
