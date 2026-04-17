"""High-level download service helpers and execution."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
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
    classify_extraction_kind,
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
    video_id: str | None
    duration_seconds: float | int | None
    duration_human: str | None
    ydl_options: dict[str, Any]


@dataclass(frozen=True, slots=True)
class FallbackFailureState:
    """Normalized failure-state mapping for fallback-stage exceptions."""

    error_code: str
    error_stage: str
    fallback_status: str
    warning_code: str
    preferred_hint_code: str | None = None


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
        "media_duration_seconds": None,
        "media_duration_human": None,
        "needs_whisper": False,
        "used_selenium_fallback": False,
        "ffmpeg_path": None,
        "started_at": None,
        "started_at_local": None,
        "finished_at": None,
        "finished_at_local": None,
        "elapsed_seconds": None,
        "error_code": None,
        "error_stage": None,
        "fallback_status": "not_attempted",
        "warnings": [],
        "warning_details": [],
        "fallback_context": None,
        "error": None,
        "hint": None,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _local_now() -> str:
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def _format_duration_human(duration_seconds: float | int | None) -> str | None:
    if duration_seconds is None:
        return None
    try:
        total_seconds = int(round(float(duration_seconds)))
    except (TypeError, ValueError):
        return None
    if total_seconds < 0:
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def _finalize_download_timing(
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
    result["elapsed_seconds"] = max(0.0, round(perf_counter() - started_perf, 3))


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


def _append_warning_with_hint(
    result: dict[str, object],
    *,
    code: str,
    message: str,
    stage: str,
    fallback_hint: str | None = None,
    overwrite_hint: bool = False,
) -> None:
    """Append a warning and then promote the best matching hint in a stable order."""
    _append_warning(
        result,
        code=code,
        message=message,
        stage=stage,
    )
    _set_result_hint(
        result,
        preferred_warning_hint(code, fallback_hint),
        overwrite=overwrite_hint,
    )


def _set_failure_state(
    result: dict[str, object],
    *,
    error: str,
    error_code: str,
    error_stage: str,
    fallback_status: str | None = None,
) -> None:
    """Update the structured result with a normalized failure state."""
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
    """Append a warning derived from a hint string and optionally promote its remediation."""
    warning_code = _classify_hint_warning(hint, default_code=default_code)
    _append_warning_with_hint(
        result=result,
        code=warning_code,
        message=hint,
        stage=stage,
        fallback_hint=hint,
        overwrite_hint=overwrite_hint,
    )
    return warning_code


def _primary_warning_message(error_message: str) -> str:
    return f"primary download failed and triggered selenium fallback: {error_message}"


def _classify_warning_message(message: str, *, default_code: str) -> str:
    lowered = message.lower()
    if "403" in lowered or "forbidden" in lowered:
        return "primary_http_403"
    if "captcha" in lowered or "verify you are human" in lowered or "verification" in lowered:
        return "primary_captcha_required"
    if "cookie" in lowered and ("database" in lowered or "locked" in lowered or "copy" in lowered):
        return "browser_cookie_locked"
    if "could not copy database" in lowered or "database is locked" in lowered or "locked" in lowered:
        return "browser_cookie_locked"
    if "sign in" in lowered or "login required" in lowered or "account access" in lowered:
        return "primary_auth_required"
    if "chromedriver" in lowered or "webdriver" in lowered:
        return "browser_driver_unavailable"
    if "ffmpeg" in lowered:
        return "ffmpeg_unavailable"
    return default_code


def _fallback_failure_state(exc: VlpError) -> FallbackFailureState:
    if isinstance(exc, DependencyMissingError):
        return FallbackFailureState(
            error_code="DEPENDENCY_MISSING",
            error_stage="fallback_dependency",
            fallback_status="dependency_missing",
            warning_code="fallback_dependency_hint",
            preferred_hint_code="browser_driver_unavailable",
        )
    if isinstance(exc, SeleniumFallbackError):
        return FallbackFailureState(
            error_code="DOWNLOAD_FALLBACK_PREPARE_FAILED",
            error_stage="fallback_prepare",
            fallback_status="prepare_failed",
            warning_code="fallback_prepare_hint",
        )
    return FallbackFailureState(
        error_code="DOWNLOAD_FALLBACK_RETRY_FAILED",
        error_stage="fallback_retry",
        fallback_status="retry_failed",
        warning_code="fallback_retry_hint",
    )


def _record_primary_failure(result: dict[str, object], error_message: str) -> None:
    """Record the normalized primary-download failure state on the result."""
    _set_failure_state(
        result,
        error=error_message,
        error_code="DOWNLOAD_PRIMARY_FAILED",
        error_stage="primary_download",
    )


def _record_primary_exception(result: dict[str, object], exc: Exception) -> None:
    """Normalize an exception raised on the primary path into result state."""
    if isinstance(exc, DownloadError):
        _record_primary_failure(result, exc.message)
        return
    _record_primary_failure(result, str(exc))


def _record_primary_download_warning(result: dict[str, object], error_message: str) -> str:
    """Record the primary-download failure warning and set its best hint."""
    warning_code = _classify_primary_warning(error_message)
    _append_warning_with_hint(
        result=result,
        code=warning_code,
        message=_primary_warning_message(error_message),
        stage="primary_download",
    )
    return warning_code


def _build_fallback_context(context: SeleniumContext) -> dict[str, str]:
    """Serialize Selenium context into the stable manifest-friendly shape."""
    return {
        "resolved_url": context.resolved_url,
        "canonical_url": context.canonical_url,
        "media_hint_url": context.media_hint_url,
        "site_name": context.site_name,
        "extraction_source": context.extraction_source,
        "extraction_kind": classify_extraction_kind(context.extraction_source),
    }


def _missing_explicit_media_hint(context: SeleniumContext) -> bool:
    return not context.media_hint_url or context.media_hint_url in {
        context.resolved_url,
        context.canonical_url,
    }


def _missing_media_hint_warning_code(context: SeleniumContext) -> str:
    extraction_kind = classify_extraction_kind(context.extraction_source)
    if extraction_kind in {"meta", "jsonld", "next_data", "window_state"}:
        return "fallback_media_hint_missing_structured"
    if extraction_kind in {"inline_html", "inline_script"}:
        return "fallback_media_hint_missing_inline_only"
    return "fallback_media_hint_missing_page_only"


def _record_fallback_prepare_warnings(result: dict[str, object], context: SeleniumContext) -> None:
    """Record warnings emitted while preparing fallback browser context."""
    extraction_kind = classify_extraction_kind(context.extraction_source)
    _append_warning(
        result,
        code="fallback_context_prepared",
        message=(
            "selenium fallback context prepared "
            f"via {context.extraction_source or 'browser-dom'} "
            f"(kind={extraction_kind})"
        ),
        stage="fallback_prepare",
    )
    if _missing_explicit_media_hint(context):
        _append_warning(
            result,
            code=_missing_media_hint_warning_code(context),
            message=(
                "selenium fallback did not extract an explicit media URL "
                f"(kind={extraction_kind}) and will retry with the resolved page URL"
            ),
            stage="fallback_prepare",
        )


def _apply_preparation_metadata(result: dict[str, object], preparation: DownloadPreparation) -> None:
    """Copy common preparation metadata onto the structured result."""
    result["title"] = preparation.title_hint
    result["folder"] = str(preparation.output_dir)
    result["ffmpeg_path"] = preparation.ffmpeg_path
    result["media_duration_seconds"] = preparation.duration_seconds
    result["media_duration_human"] = preparation.duration_human


def _build_retry_headers(context: SeleniumContext) -> dict[str, str]:
    """Build the headers used when retrying yt-dlp with browser-derived context."""
    headers = {
        "User-Agent": context.user_agent,
        "Referer": context.canonical_url or context.referer,
    }
    origin = _origin_from_url(context.canonical_url or context.resolved_url)
    if origin:
        headers["Origin"] = origin
    return headers


def _prepare_retry_download(
    *,
    context: SeleniumContext,
    output_dir: str | Path,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    subtitle_only: bool,
    result: dict[str, object],
) -> DownloadPreparation:
    """Probe and prepare the fallback retry download request."""
    retry_url = context.media_hint_url or context.canonical_url or context.resolved_url
    preparation = probe_download(
        url=retry_url,
        output_dir=output_dir,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
        cookie_file=context.cookie_file,
    )
    preparation.output_dir.mkdir(parents=True, exist_ok=True)
    preparation.ydl_options["http_headers"] = _build_retry_headers(context)
    _apply_preparation_metadata(result, preparation)
    return preparation


def _record_retry_context_state(result: dict[str, object], context: SeleniumContext) -> None:
    """Persist prepared fallback context and related warnings onto the result."""
    _apply_page_description(result, context.page_description)
    _record_fallback_prepare_warnings(result, context)
    _set_prepared_fallback_context(result, context)


def _apply_page_description(result: dict[str, object], page_description: str | None) -> None:
    if page_description and not result.get("error"):
        result["error"] = page_description


def _set_prepared_fallback_context(result: dict[str, object], context: SeleniumContext) -> None:
    result["fallback_context"] = _build_fallback_context(context)
    result["fallback_status"] = "prepared"


def _fallback_exception_warning_code(exc: Exception) -> str:
    """Map retry-stage exceptions to their default warning code family."""
    if isinstance(exc, VlpError):
        return _fallback_failure_state(exc).warning_code
    return "fallback_retry_unhandled_exception"


def _handle_fallback_vlp_error(result: dict[str, object], exc: VlpError) -> None:
    """Record fallback-stage VlpError failures and optional hint warnings."""
    failure_state = _fallback_failure_state(exc)
    _set_failure_state(
        result,
        error=exc.message,
        error_code=failure_state.error_code,
        error_stage=failure_state.error_stage,
        fallback_status=failure_state.fallback_status,
    )
    if failure_state.preferred_hint_code:
        generic_hint = preferred_warning_hint(failure_state.preferred_hint_code, exc.hint)
        _set_result_hint(
            result,
            generic_hint,
            overwrite=True,
        )
    else:
        generic_hint = None

    if exc.hint:
        warning_code = _append_hint_warning(
            result,
            hint=exc.hint,
            default_code=failure_state.warning_code,
            stage=str(result["error_stage"] or "download"),
            overwrite_hint=False,
        )
        if warning_code != failure_state.warning_code:
            specific_hint = preferred_warning_hint(warning_code, exc.hint)
            if not result.get("hint") or result.get("hint") == generic_hint:
                _set_result_hint(
                    result,
                    specific_hint,
                    overwrite=True,
                )


def _handle_unexpected_fallback_exception(result: dict[str, object], exc: Exception) -> None:
    """Record non-domain fallback exceptions using the stable retry failure contract."""
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


def _classify_primary_warning(error_message: str) -> str:
    return _classify_warning_message(error_message, default_code="primary_download_failed")


def _classify_hint_warning(hint: str, *, default_code: str) -> str:
    return _classify_warning_message(hint, default_code=default_code)


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
    subtitle_only: bool,
    ffmpeg_path: str | None,
    cookie_source: CookieSource,
) -> dict[str, Any]:
    """Build the baseline yt-dlp options shared by old and new entry points."""
    if subtitle_only:
        options: dict[str, Any] = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": languages,
            "subtitlesformat": "vtt/srt",
        }
    elif audio_only:
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
    elif not audio_only and not subtitle_only:
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
    subtitle_only: bool = False,
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
        subtitle_only=subtitle_only,
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
        video_id=None,
        duration_seconds=None,
        duration_human=None,
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
    subtitle_only: bool = False,
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
        subtitle_only=subtitle_only,
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
    duration_seconds = info.get("duration")
    duration_human = info.get("duration_string") or _format_duration_human(duration_seconds)
    return prepare_download(
        url=url,
        output_dir=output_dir,
        title_hint=raw_title,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    ).__class__(
        url=url,
        output_root=Path(output_dir),
        output_dir=resolve_job_directory(output_dir, raw_title, video_id),
        title_hint=sanitize_filename(raw_title),
        cookie_source=probe_prep.cookie_source,
        ffmpeg_path=probe_prep.ffmpeg_path,
        video_id=str(video_id) if video_id else None,
        duration_seconds=duration_seconds if isinstance(duration_seconds, (int, float)) else None,
        duration_human=str(duration_human) if duration_human else None,
        ydl_options=build_base_ydl_options(
            output_template=str(resolve_job_directory(output_dir, raw_title, video_id) / f"{sanitize_filename(raw_title)}.%(ext)s"),
            languages=languages or ["zh", "en"],
            quality=quality,
            audio_only=audio_only,
            subtitle_only=subtitle_only,
            ffmpeg_path=probe_prep.ffmpeg_path,
            cookie_source=probe_prep.cookie_source,
        ),
    )


def _validate_downloaded_files(job_dir: Path, *, audio_only: bool, subtitle_only: bool) -> None:
    files = list(job_dir.glob("*"))
    if not files:
        raise DownloadError("download failed: no files were created")

    if audio_only:
        audio_candidates = [job_dir / "audio.mp3", job_dir / "audio.m4a"]
        if any(path.exists() for path in audio_candidates):
            return
        raise DownloadError("download failed: no audio artifact was produced")

    if subtitle_only:
        subtitle_candidates = [job_dir / "subtitle.vtt", job_dir / "subtitle.srt"]
        if any(path.exists() for path in subtitle_candidates):
            return
        raise DownloadError("download failed: no subtitle artifact was produced")

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
    def _relpath(name: str) -> str:
        return (output_dir / name).relative_to(output_root).as_posix()

    if artifacts["video"]:
        result["video"] = _relpath(artifacts["video"])
    if artifacts["audio_mp3"]:
        result["audio"] = _relpath(artifacts["audio_mp3"])
    elif artifacts["audio_m4a"]:
        result["audio"] = _relpath(artifacts["audio_m4a"])
    if artifacts["subtitle_vtt"]:
        result["subtitle"] = _relpath(artifacts["subtitle_vtt"])
        result["subtitle_vtt"] = result["subtitle"]
    if artifacts["subtitle_srt"]:
        result["subtitle_srt"] = _relpath(artifacts["subtitle_srt"])
        if not result.get("subtitle"):
            result["subtitle"] = result["subtitle_srt"]
    if artifacts["info_json"]:
        result["info"] = _relpath(artifacts["info_json"])
    if not audio_only and not result.get("subtitle") and not result.get("subtitle_srt"):
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


def _execute_primary_download(
    *,
    url: str,
    output_dir: str | Path,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    subtitle_only: bool,
    cookies_from_browser: str | None,
    cookie_file: str | Path | None,
    result: dict[str, object],
) -> dict[str, object]:
    """Run the primary yt-dlp path and populate the structured result on success."""
    preparation = probe_download(
        url=url,
        output_dir=output_dir,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
        cookies_from_browser=cookies_from_browser,
        cookie_file=cookie_file,
    )
    preparation.output_dir.mkdir(parents=True, exist_ok=True)
    _apply_preparation_metadata(result, preparation)

    artifacts = _execute_ydl_download(preparation)
    _validate_downloaded_files(
        preparation.output_dir,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
    )
    return _populate_result_from_artifacts(
        result=result,
        artifacts=artifacts,
        output_dir=preparation.output_dir,
        output_root=preparation.output_root,
        audio_only=audio_only,
    )


def _retry_with_selenium_context(
    *,
    context: SeleniumContext,
    output_dir: str | Path,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    subtitle_only: bool,
    result: dict[str, object],
) -> dict[str, object]:
    preparation = _prepare_retry_download(
        context=context,
        output_dir=output_dir,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
        result=result,
    )
    _record_retry_context_state(result, context)

    artifacts = _execute_ydl_download(preparation)
    _validate_downloaded_files(
        preparation.output_dir,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
    )
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


def _continue_after_primary_failure(
    *,
    result: dict[str, object],
    output_dir: str | Path,
    selenium_mode: str,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    subtitle_only: bool,
) -> dict[str, object]:
    """Continue from a normalized primary failure into optional fallback handling."""
    return _handle_download_failure(
        result=result,
        output_dir=output_dir,
        selenium_mode=selenium_mode,
        languages=languages,
        quality=quality,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
    )


def execute_download(
    *,
    url: str,
    output_dir: str | Path,
    languages: list[str] | None = None,
    quality: str = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    audio_only: bool = False,
    subtitle_only: bool = False,
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
    selenium_mode: str = "auto",
) -> dict[str, object]:
    """Run the primary yt-dlp download path and return a structured result."""
    result = new_download_result(url)
    started_at = _utc_now()
    started_at_local = _local_now()
    started_perf = perf_counter()

    try:
        result = _execute_primary_download(
            url=url,
            output_dir=output_dir,
            languages=languages,
            quality=quality,
            audio_only=audio_only,
            subtitle_only=subtitle_only,
            cookies_from_browser=cookies_from_browser,
            cookie_file=cookie_file,
            result=result,
        )
    except Exception as exc:
        _record_primary_exception(result, exc)
        result = _continue_after_primary_failure(
            result=result,
            output_dir=output_dir,
            selenium_mode=selenium_mode,
            languages=languages,
            quality=quality,
            audio_only=audio_only,
            subtitle_only=subtitle_only,
        )
    finally:
        _finalize_download_timing(
            result,
            started_at=started_at,
            started_at_local=started_at_local,
            started_perf=started_perf,
        )
    return result


def _handle_download_failure(
    *,
    result: dict[str, object],
    output_dir: str | Path,
    selenium_mode: str,
    languages: list[str] | None,
    quality: str,
    audio_only: bool,
    subtitle_only: bool,
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
            subtitle_only=subtitle_only,
            result=result,
        )
    except (DependencyMissingError, SeleniumFallbackError, DownloadError, Exception) as exc:
        result["used_selenium_fallback"] = False
        if isinstance(exc, VlpError):
            _handle_fallback_vlp_error(result, exc)
        else:
            _handle_unexpected_fallback_exception(result, exc)
        return result


def download_url(url: str) -> dict[str, object]:
    """Compatibility wrapper for older scaffolding callers."""
    return execute_download(url=url, output_dir="./output")
