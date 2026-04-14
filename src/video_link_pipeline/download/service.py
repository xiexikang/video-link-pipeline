"""High-level download service helpers and execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

from ..errors import ConfigError, DependencyMissingError, VlpError
from ..transcribe.ffmpeg import resolve_ffmpeg_executable
from .cookies import CookieSource, build_cookie_options, normalize_cookie_source
from .diagnostics import (
    WARNING_CODES,
    preferred_warning_hint,
    warning_code_description,
    warning_code_remediation,
)
from .selenium_fallback import (
    SeleniumContext,
    SeleniumFallbackError,
    run_selenium_browser_context,
    should_attempt_selenium_fallback,
)


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


def new_download_result(url: str) -> dict[str, object]:
    """Build the default structured result payload for one download attempt."""
    return {
        "success": False,
        "url": url,
        "title": None,
        "folder": None,
        "video": None,
        "audio": None,
        "subtitle": None,
        "subtitle_vtt": None,
        "subtitle_srt": None,
        "info": None,
        "needs_whisper": False,
        "used_selenium_fallback": False,
        "ffmpeg_path": None,
        "error_code": None,
        "error_stage": None,
        "fallback_status": "not_attempted",
        "warnings": [],
        "warning_details": [],
        "fallback_context": None,
        "error": None,
        "hint": None,
    }


def _warning_details(result: dict[str, object]) -> list[dict[str, str]]:
    details = result.get("warning_details")
    if not isinstance(details, list):
        details = []
        result["warning_details"] = details
    return details


def _append_warning(
    result: dict[str, object],
    *,
    code: str,
    message: str,
    stage: str,
) -> None:
    if code not in WARNING_CODES:
        raise ValueError(f"unknown download warning code: {code}")
    warnings = list(result.get("warnings") or [])
    warnings.append(message)
    result["warnings"] = warnings
    _warning_details(result).append(
        {
            "code": code,
            "message": message,
            "stage": stage,
            "description": warning_code_description(code) or "",
            "remediation": warning_code_remediation(code) or "",
        }
    )


def _set_result_hint(result: dict[str, object], hint: str | None, *, overwrite: bool = False) -> None:
    normalized = str(hint or "").strip()
    if not normalized:
        return
    if overwrite or not result.get("hint"):
        result["hint"] = normalized


def _apply_warning_remediation(result: dict[str, object], code: str, *, overwrite: bool = False) -> None:
    _set_result_hint(result, preferred_warning_hint(code), overwrite=overwrite)


def _set_failure_state(
    result: dict[str, object],
    *,
    error: str,
    error_code: str,
    error_stage: str,
    fallback_status: str | None = None,
) -> None:
    result["error"] = error
    result["error_code"] = error_code
    result["error_stage"] = error_stage
    if fallback_status is not None:
        result["fallback_status"] = fallback_status


def _append_hint_warning(
    result: dict[str, object],
    *,
    hint: str,
    default_code: str,
    stage: str,
    overwrite_hint: bool = False,
) -> str:
    warning_code = _classify_hint_warning(hint, default_code=default_code)
    _append_warning(
        result,
        code=warning_code,
        message=hint,
        stage=stage,
    )
    _set_result_hint(
        result,
        preferred_warning_hint(warning_code, hint),
        overwrite=overwrite_hint,
    )
    return warning_code


def _record_primary_download_warning(result: dict[str, object], error_message: str) -> str:
    warning_code = _classify_primary_warning(error_message)
    _append_warning(
        result,
        code=warning_code,
        message=f"primary download failed and triggered selenium fallback: {error_message}",
        stage="primary_download",
    )
    _apply_warning_remediation(result, warning_code)
    return warning_code


def _build_fallback_context(context: SeleniumContext) -> dict[str, str]:
    return {
        "resolved_url": context.resolved_url,
        "canonical_url": context.canonical_url,
        "media_hint_url": context.media_hint_url,
        "site_name": context.site_name,
        "extraction_source": context.extraction_source,
    }


def _record_fallback_prepare_warnings(result: dict[str, object], context: SeleniumContext) -> None:
    _append_warning(
        result,
        code="fallback_context_prepared",
        message=f"selenium fallback context prepared via {context.extraction_source or 'browser-dom'}",
        stage="fallback_prepare",
    )
    if not context.media_hint_url or context.media_hint_url in {
        context.resolved_url,
        context.canonical_url,
    }:
        _append_warning(
            result,
            code="fallback_media_hint_missing",
            message="selenium fallback did not extract an explicit media URL and will retry with the resolved page URL",
            stage="fallback_prepare",
        )


def _apply_preparation_metadata(result: dict[str, object], preparation: DownloadPreparation) -> None:
    result["title"] = preparation.title_hint
    result["folder"] = str(preparation.output_dir)
    result["ffmpeg_path"] = preparation.ffmpeg_path


def _build_retry_headers(context: SeleniumContext) -> dict[str, str]:
    headers = {
        "User-Agent": context.user_agent,
        "Referer": context.canonical_url or context.referer,
    }
    origin = _origin_from_url(context.canonical_url or context.resolved_url)
    if origin:
        headers["Origin"] = origin
    return headers


def _fallback_exception_warning_code(exc: Exception) -> str:
    if isinstance(exc, DependencyMissingError):
        return "fallback_dependency_hint"
    if isinstance(exc, SeleniumFallbackError):
        return "fallback_prepare_hint"
    if isinstance(exc, DownloadError):
        return "fallback_retry_hint"
    return "fallback_retry_unhandled_exception"


def _classify_primary_warning(error_message: str) -> str:
    lowered = error_message.lower()
    if "403" in lowered or "forbidden" in lowered:
        return "primary_http_403"
    if "captcha" in lowered or "verify you are human" in lowered or "verification" in lowered:
        return "primary_captcha_required"
    if "cookie" in lowered and ("database" in lowered or "locked" in lowered or "copy" in lowered):
        return "browser_cookie_locked"
    if "sign in" in lowered or "login required" in lowered:
        return "primary_auth_required"
    return "primary_download_failed"


def _classify_hint_warning(hint: str, *, default_code: str) -> str:
    lowered = hint.lower()
    if "could not copy database" in lowered or "database is locked" in lowered or "locked" in lowered:
        return "browser_cookie_locked"
    if "chromedriver" in lowered or "webdriver" in lowered:
        return "browser_driver_unavailable"
    if "ffmpeg" in lowered:
        return "ffmpeg_unavailable"
    return default_code


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


def _populate_result_from_artifacts(
    *,
    result: dict[str, object],
    artifacts: dict[str, str | None],
    output_dir: Path,
    output_root: Path,
    audio_only: bool,
) -> dict[str, object]:
    if artifacts["video"]:
        result["video"] = str((output_dir / artifacts["video"]).relative_to(output_root))
    if artifacts["audio_mp3"]:
        result["audio"] = str((output_dir / artifacts["audio_mp3"]).relative_to(output_root))
    elif artifacts["audio_m4a"]:
        result["audio"] = str((output_dir / artifacts["audio_m4a"]).relative_to(output_root))
    if artifacts["subtitle_vtt"]:
        result["subtitle"] = str((output_dir / artifacts["subtitle_vtt"]).relative_to(output_root))
        result["subtitle_vtt"] = result["subtitle"]
    if artifacts["subtitle_srt"]:
        result["subtitle_srt"] = str((output_dir / artifacts["subtitle_srt"]).relative_to(output_root))
    if artifacts["info_json"]:
        result["info"] = str((output_dir / artifacts["info_json"]).relative_to(output_root))
    if not audio_only and not result["subtitle"]:
        result["needs_whisper"] = True
    result["success"] = True
    result["error_code"] = None
    result["error_stage"] = None
    return result


def _execute_ydl_download(preparation: DownloadPreparation) -> dict[str, str | None]:
    with YoutubeDL(preparation.ydl_options) as ydl:
        ydl.extract_info(preparation.url, download=True)
    artifacts = standardize_download_artifacts(preparation.output_dir, preparation.output_dir)
    return artifacts


def _retry_with_selenium_context(
    *,
    context: SeleniumContext,
    output_dir: str | Path,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    result: dict[str, object],
) -> dict[str, object]:
    retry_url = context.media_hint_url or context.canonical_url or context.resolved_url
    preparation = probe_download(
        url=retry_url,
        output_dir=output_dir,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        cookie_file=context.cookie_file,
    )
    preparation.output_dir.mkdir(parents=True, exist_ok=True)
    preparation.ydl_options["http_headers"] = _build_retry_headers(context)

    _apply_preparation_metadata(result, preparation)
    if context.page_description and not result.get("error"):
        result["error"] = context.page_description
    warnings = list(result.get("warnings") or [])
    _record_fallback_prepare_warnings(result, context)
    result["fallback_context"] = _build_fallback_context(context)
    result["fallback_status"] = "prepared"

    artifacts = _execute_ydl_download(preparation)
    _validate_downloaded_files(preparation.output_dir, audio_only=audio_only)
    result["used_selenium_fallback"] = True
    result["fallback_status"] = "succeeded"
    return _populate_result_from_artifacts(
        result=result,
        artifacts=artifacts,
        output_dir=preparation.output_dir,
        output_root=preparation.output_root,
        audio_only=audio_only,
    )


def _origin_from_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}"


def execute_download(
    *,
    url: str,
    output_dir: str | Path,
    languages: list[str] | None = None,
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    audio_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
    selenium_mode: str = "auto",
) -> dict[str, object]:
    """Run the primary yt-dlp download path and return a structured result."""
    result = new_download_result(url)

    try:
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
        _apply_preparation_metadata(result, preparation)

        artifacts = _execute_ydl_download(preparation)
        _validate_downloaded_files(preparation.output_dir, audio_only=audio_only)
        return _populate_result_from_artifacts(
            result=result,
            artifacts=artifacts,
            output_dir=preparation.output_dir,
            output_root=preparation.output_root,
            audio_only=audio_only,
        )
    except DownloadError as exc:
        _set_failure_state(
            result,
            error=exc.message,
            error_code="DOWNLOAD_PRIMARY_FAILED",
            error_stage="primary_download",
        )
        return _handle_download_failure(
            result=result,
            output_dir=output_dir,
            selenium_mode=selenium_mode,
            languages=languages,
            quality=quality,
            audio_only=audio_only,
        )
    except Exception as exc:
        _set_failure_state(
            result,
            error=str(exc),
            error_code="DOWNLOAD_PRIMARY_FAILED",
            error_stage="primary_download",
        )
        return _handle_download_failure(
            result=result,
            output_dir=output_dir,
            selenium_mode=selenium_mode,
            languages=languages,
            quality=quality,
            audio_only=audio_only,
        )


def _handle_download_failure(
    *,
    result: dict[str, object],
    output_dir: str | Path,
    selenium_mode: str,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
) -> dict[str, object]:
    error_message = str(result.get("error") or "download failed")
    if not should_attempt_selenium_fallback(selenium_mode, error_message):
        return result
    result["fallback_status"] = "triggered"
    _record_primary_download_warning(result, error_message)

    try:
        context = run_selenium_browser_context(
            url=str(result["url"]),
            workspace_dir=str(result.get("folder") or output_dir),
        )
        return _retry_with_selenium_context(
            context=context,
            output_dir=output_dir,
            languages=languages,
            quality=quality,
            audio_only=audio_only,
            result=result,
        )
    except (DependencyMissingError, SeleniumFallbackError, DownloadError, Exception) as exc:
        result["used_selenium_fallback"] = False
        if isinstance(exc, VlpError):
            if isinstance(exc, DependencyMissingError):
                _set_failure_state(
                    result,
                    error=exc.message,
                    error_code="DEPENDENCY_MISSING",
                    error_stage="fallback_dependency",
                    fallback_status="dependency_missing",
                )
                _set_result_hint(result, preferred_warning_hint("browser_driver_unavailable", exc.hint), overwrite=True)
            elif isinstance(exc, SeleniumFallbackError):
                _set_failure_state(
                    result,
                    error=exc.message,
                    error_code="DOWNLOAD_FALLBACK_PREPARE_FAILED",
                    error_stage="fallback_prepare",
                    fallback_status="prepare_failed",
                )
            elif isinstance(exc, DownloadError):
                _set_failure_state(
                    result,
                    error=exc.message,
                    error_code="DOWNLOAD_FALLBACK_RETRY_FAILED",
                    error_stage="fallback_retry",
                    fallback_status="retry_failed",
                )
            if exc.hint:
                _append_hint_warning(
                    result,
                    hint=exc.hint,
                    default_code=_fallback_exception_warning_code(exc),
                    stage=str(result["error_stage"] or "download"),
                    overwrite_hint=False,
                )
        else:
            _set_failure_state(
                result,
                error=str(exc),
                error_code="DOWNLOAD_FALLBACK_RETRY_FAILED",
                error_stage="fallback_retry",
                fallback_status="retry_failed",
            )
            _append_hint_warning(
                result,
                hint=str(exc),
                default_code=_fallback_exception_warning_code(exc),
                stage="fallback_retry",
            )
        return result


def download_url(url: str) -> dict[str, object]:
    """Compatibility wrapper for older scaffolding callers."""
    return execute_download(url=url, output_dir="./output")
