"""High-level download service helpers and execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL

from ..errors import ConfigError, DependencyMissingError, VlpError
from ..transcribe.ffmpeg import resolve_ffmpeg_executable
from .cookies import CookieSource, build_cookie_options, normalize_cookie_source


@dataclass(slots=True)
class DownloadPreparation:
    """Reusable derived state for a yt-dlp download request."""

    url: str
    output_root: Path
    output_dir: Path
    title_hint: str
    cookie_source: CookieSource
    ffmpeg_path: str | None
    ydl_options: dict[str, Any]


class DownloadError(VlpError):
    """Raised when the primary download path fails."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="DOWNLOAD_FAILED", hint=hint)


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
    if audio_only:
        options: dict[str, Any] = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
            "writesubtitles": False,
            "writeautomaticsub": False,
        }
    else:
        options = {
            "format": quality,
            "merge_output_format": "mp4",
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
            "subtitlesformat": "vtt/srt",
        }

    options.update(
        {
            "outtmpl": {"default": output_template},
            "quiet": False,
            "noprogress": False,
            "no_warnings": False,
            "writeinfojson": True,
        }
    )
    if ffmpeg_path:
        options["ffmpeg_location"] = ffmpeg_path
    elif not audio_only:
        options["format"] = "best[ext=mp4]/best"
        options.pop("merge_output_format", None)
    options.update(build_cookie_options(cookie_source))
    return options


def prepare_download(
    *,
    url: str,
    output_dir: str | Path,
    title_hint: str,
    languages: list[str] | None = None,
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
) -> DownloadPreparation:
    """Prepare derived paths and yt-dlp options for a download request."""
    normalized_languages = languages or ["zh", "en"]
    if not normalized_languages:
        raise ConfigError("at least one subtitle language must be provided")

    output_root = Path(output_dir)
    cookie_source = normalize_cookie_source(
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    )
    ffmpeg_path = resolve_ffmpeg_executable()
    title = sanitize_filename(title_hint)
    job_dir = resolve_job_directory(output_root, title)
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
        output_root=output_root,
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


def probe_download(
    *,
    url: str,
    output_dir: str | Path,
    languages: list[str] | None = None,
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
) -> DownloadPreparation:
    """Probe the remote URL and prepare a concrete download job."""
    probe_prep = prepare_download(
        url=url,
        output_dir=output_dir,
        title_hint="download",
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    )
    probe_options = dict(probe_prep.ydl_options)
    probe_options["outtmpl"] = {"default": str(probe_prep.output_root / "%(title)s" / "%(title)s.%(ext)s")}

    try:
        with YoutubeDL(probe_options) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:
        raise DownloadError(f"failed to probe download metadata: {url}", hint=str(exc)) from exc

    raw_title = info.get("title") or "download"
    video_id = info.get("id")
    return prepare_download(
        url=url,
        output_dir=output_dir,
        title_hint=raw_title,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    ).__class__(
        url=url,
        output_root=Path(output_dir),
        output_dir=resolve_job_directory(output_dir, raw_title, video_id),
        title_hint=sanitize_filename(raw_title),
        cookie_source=probe_prep.cookie_source,
        ffmpeg_path=probe_prep.ffmpeg_path,
        ydl_options=build_base_ydl_options(
            output_template=str(resolve_job_directory(output_dir, raw_title, video_id) / f"{sanitize_filename(raw_title)}.%(ext)s"),
            languages=languages or ["zh", "en"],
            quality=quality,
            audio_only=audio_only,
            ffmpeg_path=probe_prep.ffmpeg_path,
            cookie_source=probe_prep.cookie_source,
        ),
    )


def _validate_downloaded_files(job_dir: Path, *, audio_only: bool) -> None:
    files = list(job_dir.glob("*"))
    if not files:
        raise DownloadError("download failed: no files were created")

    if audio_only:
        audio_candidates = [job_dir / "audio.mp3", job_dir / "audio.m4a"]
        if any(path.exists() for path in audio_candidates):
            return
        raise DownloadError("download failed: no audio artifact was produced")

    video_file = job_dir / "video.mp4"
    if not video_file.exists():
        if all(item.stat().st_size < 100 * 1024 for item in files):
            raise DownloadError("download failed: only tiny files were produced")
        raise DownloadError("download failed: expected video.mp4 was not produced")
    if video_file.stat().st_size < 100 * 1024:
        raise DownloadError("download failed: downloaded video is too small")


def execute_download(
    *,
    url: str,
    output_dir: str | Path,
    languages: list[str] | None = None,
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
) -> dict[str, object]:
    """Run the primary yt-dlp download path and return a structured result."""
    preparation = probe_download(
        url=url,
        output_dir=output_dir,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    )
    preparation.output_dir.mkdir(parents=True, exist_ok=True)

    result: dict[str, object] = {
        "success": False,
        "url": url,
        "title": preparation.title_hint,
        "folder": str(preparation.output_dir),
        "video": None,
        "audio": None,
        "subtitle": None,
        "subtitle_vtt": None,
        "subtitle_srt": None,
        "info": None,
        "needs_whisper": False,
        "used_selenium_fallback": False,
        "ffmpeg_path": preparation.ffmpeg_path,
        "error": None,
    }

    try:
        with YoutubeDL(preparation.ydl_options) as ydl:
            ydl.extract_info(url, download=True)

        artifacts = standardize_download_artifacts(preparation.output_dir, preparation.output_dir)
        _validate_downloaded_files(preparation.output_dir, audio_only=audio_only)

        root = preparation.output_root
        if artifacts["video"]:
            result["video"] = str((preparation.output_dir / artifacts["video"]).relative_to(root))
        if artifacts["audio_mp3"]:
            result["audio"] = str((preparation.output_dir / artifacts["audio_mp3"]).relative_to(root))
        elif artifacts["audio_m4a"]:
            result["audio"] = str((preparation.output_dir / artifacts["audio_m4a"]).relative_to(root))
        if artifacts["subtitle_vtt"]:
            result["subtitle"] = str((preparation.output_dir / artifacts["subtitle_vtt"]).relative_to(root))
            result["subtitle_vtt"] = result["subtitle"]
        if artifacts["subtitle_srt"]:
            result["subtitle_srt"] = str((preparation.output_dir / artifacts["subtitle_srt"]).relative_to(root))
        if artifacts["info_json"]:
            result["info"] = str((preparation.output_dir / artifacts["info_json"]).relative_to(root))
        if not audio_only and not result["subtitle"]:
            result["needs_whisper"] = True

        result["success"] = True
        return result
    except DownloadError as exc:
        result["error"] = exc.message
        return result
    except Exception as exc:
        result["error"] = str(exc)
        return result


def download_url(url: str) -> dict[str, object]:
    """Compatibility wrapper for older scaffolding callers."""
    return execute_download(url=url, output_dir="./output")
