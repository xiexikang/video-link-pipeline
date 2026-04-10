"""Subtitle conversion helpers and service functions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from ..errors import ConfigError, InputNotFoundError

SubtitleFormat = Literal["srt", "vtt"]


def parse_vtt_time(time_str: str) -> float:
    """Parse VTT timestamps into seconds."""
    time_str = time_str.strip()
    if "." in time_str:
        time_str = time_str.replace(".", ",")

    parts = time_str.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2].replace(",", "."))
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1].replace(",", "."))
    else:
        hours = 0
        minutes = 0
        seconds = float(parts[0].replace(",", "."))

    return hours * 3600 + minutes * 60 + seconds


def format_srt_time(seconds: float) -> str:
    """Format seconds as an SRT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """Format seconds as a VTT timestamp."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def vtt_to_srt(vtt_content: str) -> str:
    """Convert VTT text into SRT text."""
    lines = vtt_content.strip().split("\n")
    index = 0
    while index < len(lines) and (
        lines[index].strip() == ""
        or lines[index].strip().startswith("WEBVTT")
        or lines[index].strip().startswith("NOTE")
    ):
        index += 1

    srt_lines: list[str] = []
    cue_index = 1
    while index < len(lines):
        line = lines[index].strip()
        if " --> " not in line:
            index += 1
            continue

        time_parts = line.split(" --> ")
        start_time = parse_vtt_time(time_parts[0])
        end_time = parse_vtt_time(time_parts[1].split()[0])

        text_lines: list[str] = []
        index += 1
        while index < len(lines) and lines[index].strip() != "":
            text = re.sub(r"<[^>]+>", "", lines[index].strip())
            if text:
                text_lines.append(text)
            index += 1

        if text_lines:
            srt_lines.append(str(cue_index))
            srt_lines.append(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}")
            srt_lines.extend(text_lines)
            srt_lines.append("")
            cue_index += 1

    return "\n".join(srt_lines)


def srt_to_vtt(srt_content: str) -> str:
    """Convert SRT text into VTT text."""
    lines = srt_content.strip().split("\n")
    vtt_lines = ["WEBVTT", ""]

    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line.isdigit():
            index += 1
            continue

        if " --> " not in line:
            index += 1
            continue

        time_parts = line.replace(",", ".").split(" --> ")
        start_time = time_parts[0].strip()
        end_time = time_parts[1].strip()
        vtt_lines.append(f"{start_time} --> {end_time}")

        index += 1
        while index < len(lines) and lines[index].strip() != "":
            vtt_lines.append(lines[index].strip())
            index += 1

        vtt_lines.append("")

    return "\n".join(vtt_lines)


def detect_subtitle_format(content: str) -> SubtitleFormat:
    """Infer subtitle format from file content."""
    normalized = content.lstrip("\ufeff").strip()
    return "vtt" if normalized.startswith("WEBVTT") else "srt"


def normalize_output_format(output_format: str | None) -> SubtitleFormat | None:
    """Normalize user-provided format names."""
    if output_format is None:
        return None
    normalized = output_format.lower().strip()
    if normalized not in {"srt", "vtt"}:
        raise ConfigError(
            f"invalid subtitle format: {output_format}",
            hint="allowed values: srt, vtt",
        )
    return normalized


def convert_subtitle_file(
    input_path: str | Path,
    output_path: str | Path | None = None,
    output_format: str | None = None,
) -> dict[str, object]:
    """Convert one subtitle file."""
    source_path = Path(input_path)
    if not source_path.exists():
        raise InputNotFoundError(f"subtitle input does not exist: {source_path}")
    if source_path.is_dir():
        raise ConfigError("single-file conversion requires a file path, not a directory")

    try:
        content = source_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"failed to read subtitle file: {source_path}", hint=str(exc)) from exc

    input_format = detect_subtitle_format(content)
    normalized_format = normalize_output_format(output_format)
    target_format: SubtitleFormat = normalized_format or ("srt" if input_format == "vtt" else "vtt")

    resolved_output_path = Path(output_path) if output_path else source_path.with_suffix(f".{target_format}")

    if input_format == target_format:
        return {
            "success": True,
            "input_path": str(source_path),
            "output_path": str(resolved_output_path),
            "input_format": input_format,
            "output_format": target_format,
            "changed": False,
            "message": f"input already matches requested format: {input_format}",
        }

    if input_format == "vtt" and target_format == "srt":
        converted = vtt_to_srt(content)
    elif input_format == "srt" and target_format == "vtt":
        converted = srt_to_vtt(content)
    else:
        raise ConfigError(
            f"unsupported subtitle conversion: {input_format} -> {target_format}"
        )

    try:
        resolved_output_path.write_text(converted, encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"failed to write subtitle file: {resolved_output_path}", hint=str(exc)) from exc

    return {
        "success": True,
        "input_path": str(source_path),
        "output_path": str(resolved_output_path),
        "input_format": input_format,
        "output_format": target_format,
        "changed": True,
        "message": "subtitle conversion completed",
    }


def batch_convert_subtitles(input_dir: str | Path, output_format: str = "srt") -> dict[str, object]:
    """Convert all matching subtitle files in a directory tree."""
    root = Path(input_dir)
    if not root.exists():
        raise InputNotFoundError(f"subtitle input does not exist: {root}")
    if not root.is_dir():
        raise ConfigError("batch conversion requires a directory path")

    target_format = normalize_output_format(output_format)
    assert target_format is not None
    source_ext = ".vtt" if target_format == "srt" else ".srt"
    files = sorted(root.glob(f"**/*{source_ext}"))

    results: list[dict[str, object]] = []
    for file_path in files:
        results.append(convert_subtitle_file(file_path, output_format=target_format))

    return {
        "success": True,
        "input_path": str(root),
        "output_format": target_format,
        "source_extension": source_ext,
        "matched_files": len(files),
        "converted_files": sum(1 for item in results if item.get("success")),
        "results": results,
    }

