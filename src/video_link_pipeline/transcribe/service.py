"""High-level transcription service interface."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from ..errors import ConfigError, InputNotFoundError, VlpError
from .faster_engine import transcribe_with_faster_whisper
from .ffmpeg import extract_audio_from_video
from .openai_engine import transcribe_with_openai_whisper

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm"}


class TranscribeError(VlpError):
    """Raised when transcription cannot be completed."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="TRANSCRIBE_FAILED", hint=hint)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _finalize_timing(result: dict[str, object], *, started_at: str, started_perf: float) -> None:
    result["started_at"] = started_at
    result["finished_at"] = _utc_now()
    result["elapsed_ms"] = max(0, int(round((perf_counter() - started_perf) * 1000)))


def normalize_engine_name(engine: str) -> str:
    mapping = {
        "auto": "auto",
        "faster": "faster",
        "faster_whisper": "faster",
        "openai": "openai",
        "openai_whisper": "openai",
    }
    normalized = mapping.get(engine.lower().strip())
    if normalized is None:
        raise ConfigError(
            f"invalid transcription engine: {engine}",
            hint="allowed values: auto, faster, openai",
        )
    return normalized


def resolve_input_media(input_path: str | Path) -> tuple[Path, Path, bool]:
    """Resolve input path to a concrete media file and default output directory."""
    source = Path(input_path)
    if not source.exists():
        raise InputNotFoundError(f"input path does not exist: {source}")

    if source.is_dir():
        for extension in VIDEO_EXTENSIONS:
            matches = list(source.glob(f"*{extension}"))
            if matches:
                return matches[0], source, True
        for extension in AUDIO_EXTENSIONS:
            matches = list(source.glob(f"*{extension}"))
            if matches:
                return matches[0], source, False
        raise TranscribeError(f"no supported audio or video file found in directory: {source}")

    suffix = source.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return source, source.parent, True
    if suffix in AUDIO_EXTENSIONS:
        return source, source.parent, False
    raise TranscribeError(f"unsupported input file type: {source.suffix or '<none>'}")


def format_time_srt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_time_vtt(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def generate_srt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for segment in segments:
        lines.append(str(int(segment["id"]) + 1))
        lines.append(f"{format_time_srt(segment['start'])} --> {format_time_srt(segment['end'])}")
        lines.append(str(segment["text"]))
        lines.append("")
    return "\n".join(lines)


def generate_vtt(segments: list[dict[str, Any]]) -> str:
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.append(f"{format_time_vtt(segment['start'])} --> {format_time_vtt(segment['end'])}")
        lines.append(str(segment["text"]))
        lines.append("")
    return "\n".join(lines)


def _choose_engine(engine: str) -> str:
    normalized = normalize_engine_name(engine)
    if normalized != "auto":
        return normalized
    try:
        import faster_whisper  # noqa: F401
        return "faster"
    except Exception:
        return "openai"


def transcribe_path(
    *,
    input_path: str | Path,
    output_dir: str | Path | None = None,
    model_size: str = "small",
    language: str = "auto",
    device: str = "auto",
    compute_type: str = "int8",
    engine: str = "auto",
) -> dict[str, object]:
    """Run transcription and write transcript/subtitle artifacts."""
    started_at = _utc_now()
    started_perf = perf_counter()
    resolved_input, default_output_dir, is_video = resolve_input_media(input_path)
    target_output_dir = Path(output_dir) if output_dir else default_output_dir
    target_output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = extract_audio_from_video(resolved_input, target_output_dir) if is_video else resolved_input
    selected_engine = _choose_engine(engine)

    result: dict[str, object] = {
        "success": False,
        "input_path": str(resolved_input),
        "audio_path": str(audio_path),
        "engine": selected_engine,
        "transcript_file": None,
        "srt_file": None,
        "vtt_file": None,
        "json_file": None,
        "segments": [],
        "detected_language": None,
        "error": None,
        "started_at": None,
        "finished_at": None,
        "elapsed_ms": None,
    }

    try:
        if selected_engine == "faster":
            segments, detected_language = transcribe_with_faster_whisper(
                input_path=str(audio_path),
                model_size=model_size,
                language=language,
                device=device,
                compute_type=compute_type,
            )
        else:
            segments, detected_language = transcribe_with_openai_whisper(
                input_path=str(audio_path),
                model_size=model_size,
                language=language,
            )

        transcript_file = target_output_dir / "transcript.txt"
        srt_file = target_output_dir / "subtitle_whisper.srt"
        vtt_file = target_output_dir / "subtitle_whisper.vtt"
        json_file = target_output_dir / "transcript.json"

        transcript_file.write_text("\n".join(segment["text"] for segment in segments), encoding="utf-8")
        srt_file.write_text(generate_srt(segments), encoding="utf-8")
        vtt_file.write_text(generate_vtt(segments), encoding="utf-8")

        result.update(
            {
                "success": True,
                "segments": segments,
                "detected_language": detected_language,
                "transcript_file": str(transcript_file),
                "srt_file": str(srt_file),
                "vtt_file": str(vtt_file),
            }
        )
        json_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["json_file"] = str(json_file)
        return result
    except VlpError as exc:
        result["error"] = exc.message
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result
    finally:
        _finalize_timing(result, started_at=started_at, started_perf=started_perf)
