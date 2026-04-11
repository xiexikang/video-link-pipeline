"""faster-whisper engine integration."""

from __future__ import annotations

from typing import Any

from ..errors import DependencyMissingError


def transcribe_with_faster_whisper(
    *,
    input_path: str,
    model_size: str,
    language: str,
    device: str,
    compute_type: str,
) -> tuple[list[dict[str, Any]], str | None]:
    """Run transcription with faster-whisper and return normalized segments."""
    try:
        from faster_whisper import WhisperModel
    except Exception as exc:
        raise DependencyMissingError(
            "faster-whisper is not available",
            hint=str(exc),
        ) from exc

    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        input_path,
        language=language if language != "auto" else None,
        beam_size=5,
        best_of=5,
        condition_on_previous_text=True,
    )

    normalized_segments: list[dict[str, Any]] = []
    for segment in segments:
        normalized_segments.append(
            {
                "id": segment.id,
                "start": float(segment.start),
                "end": float(segment.end),
                "text": segment.text.strip(),
            }
        )
    return normalized_segments, getattr(info, "language", None)
