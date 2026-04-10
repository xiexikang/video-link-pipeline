"""High-level download service helpers and scaffolding."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..errors import ConfigError
from ..transcribe.ffmpeg import resolve_ffmpeg_executable
from .cookies import CookieSource, build_cookie_options, normalize_cookie_source


@dataclass(slots=True)
class DownloadPreparation:
    """Reusable derived state for a yt-dlp download request."""

    url: str
    output_dir: Path
    title_hint: str
    cookie_source: CookieSource
    ffmpeg_path: str | None
    ydl_options: dict[str, Any]


def sanitize_filename(filename: str) -> str:
    """Normalize titles into filesystem-safe directory/file names."""
    normalized = re.sub(r'[\\/*?:"<>|]', "_", filename)
    normalized = re.sub(r"\s+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_.") or "untitled"


def resolve_job_directory(output_dir: str | Path, title: str, video_id: str | None = None) -> Path:
    """Resolve the target job directory for downloaded artifacts."""
    root = Path(output_dir)
    slug = sanitize_filename(title)
    folder_name = f"{video_id}-{slug}" if video_id else slug
    return root / folder_name


def build_base_ydl_options(
    *,
    output_template: str,
    languages: list[str],
    quality: str,
    audio_only: bool,
    ffmpeg_path: str | None,
    cookie_source: CookieSource,
) -> dict[str, Any]:
    """Build the baseline yt-dlp options shared by old and new entry points."""
    options: dict[str, Any] = {
        "outtmpl": {"default": output_template},
        "quiet": False,
        "noprogress": False,
        "format": "bestaudio/best" if audio_only else quality,
        "writesubtitles": not audio_only,
        "writeautomaticsub": not audio_only,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt/srt",
    }
    if ffmpeg_path:
        options["ffmpeg_location"] = ffmpeg_path
    options.update(build_cookie_options(cookie_source))
    return options


def prepare_download(
    *,
    url: str,
    output_dir: str | Path,
    title_hint: str,
    languages: list[str] | None = None,
    quality: str = "best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
) -> DownloadPreparation:
    """Prepare derived paths and yt-dlp options for a download request."""
    normalized_languages = languages or ["zh", "en"]
    if not normalized_languages:
        raise ConfigError("at least one subtitle language must be provided")

    cookie_source = normalize_cookie_source(
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    )
    ffmpeg_path = resolve_ffmpeg_executable()
    title = sanitize_filename(title_hint)
    job_dir = resolve_job_directory(output_dir, title)
    ydl_options = build_base_ydl_options(
        output_template=str(job_dir / f"{title}.%(ext)s"),
        languages=normalized_languages,
        quality=quality,
        audio_only=audio_only,
        ffmpeg_path=ffmpeg_path,
        cookie_source=cookie_source,
    )
    return DownloadPreparation(
        url=url,
        output_dir=job_dir,
        title_hint=title,
        cookie_source=cookie_source,
        ffmpeg_path=ffmpeg_path,
        ydl_options=ydl_options,
    )


def standardize_download_artifacts(src_folder: str | Path, dst_folder: str | Path) -> dict[str, str | None]:
    """Normalize yt-dlp output names into stable artifact names."""
    source = Path(src_folder)
    target = Path(dst_folder)
    target.mkdir(parents=True, exist_ok=True)

    artifacts: dict[str, str | None] = {
        "video": None,
        "audio_m4a": None,
        "audio_mp3": None,
        "subtitle_vtt": None,
        "subtitle_srt": None,
        "info_json": None,
    }

    def move_first(glob_pattern: str, dest_name: str, artifact_key: str, picker=None) -> None:
        files = list(source.glob(glob_pattern))
        if not files:
            return
        selected = picker(files) if picker else files[0]
        destination = target / dest_name
        if selected.resolve() != destination.resolve() and not destination.exists():
            selected.rename(destination)
        artifacts[artifact_key] = destination.name if destination.exists() else selected.name

    def pick_subtitle(files: list[Path]) -> Path:
        zh = [file for file in files if ".zh" in file.name or "zh-hans" in file.name]
        en = [file for file in files if ".en" in file.name]
        return (zh or en or files)[0]

    move_first("*.mp4", "video.mp4", "video")
    move_first("*.m4a", "audio.m4a", "audio_m4a")
    move_first("*.mp3", "audio.mp3", "audio_mp3")
    move_first("*.vtt", "subtitle.vtt", "subtitle_vtt", picker=pick_subtitle)
    move_first("*.srt", "subtitle.srt", "subtitle_srt", picker=pick_subtitle)
    move_first("*.info.json", "info.json", "info_json")

    return artifacts


def download_url(url: str) -> dict[str, object]:
    """Package-level scaffold for download migration."""
    prepared = prepare_download(url=url, output_dir="./output", title_hint="download")
    return {
        "success": False,
        "url": url,
        "message": "download service not implemented",
        "ffmpeg_path": prepared.ffmpeg_path,
        "cookie_source": {
            "browser": prepared.cookie_source.browser,
            "cookie_file": str(prepared.cookie_source.cookie_file) if prepared.cookie_source.cookie_file else None,
        },
        "output_dir": str(prepared.output_dir),
    }
