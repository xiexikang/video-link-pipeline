"""FFmpeg resolution helpers."""

from __future__ import annotations

import shutil
from pathlib import Path


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
