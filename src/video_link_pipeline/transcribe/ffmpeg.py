"""FFmpeg resolution and audio extraction helpers."""

from __future__ import annotations

import subprocess
import shutil
from pathlib import Path

from ..errors import ConfigError, DependencyMissingError


def resolve_ffmpeg_executable() -> str | None:
    """Return the preferred ffmpeg executable path if available."""
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    try:
        import imageio_ffmpeg as imageio_ffmpeg

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

    return str(Path(ffmpeg_path))


def extract_audio_from_video(video_path: str | Path, output_dir: str | Path) -> Path:
    """Extract MP3 audio from a video file using ffmpeg."""
    ffmpeg_executable = resolve_ffmpeg_executable()
    if ffmpeg_executable is None:
        raise DependencyMissingError(
            "ffmpeg is not available for audio extraction",
            hint="install ffmpeg or keep imageio-ffmpeg available in the environment",
        )

    source = Path(video_path)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    audio_path = target_dir / f"{source.stem}.mp3"
    if audio_path.exists():
        return audio_path

    command = [
        ffmpeg_executable,
        "-i",
        str(source),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-q:a",
        "2",
        str(audio_path),
        "-y",
    ]
    try:
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as exc:
        raise ConfigError(f"failed to extract audio from video: {source}", hint=str(exc)) from exc

    if not audio_path.exists():
        raise ConfigError(f"ffmpeg finished but did not produce audio output: {audio_path}")
    return audio_path
