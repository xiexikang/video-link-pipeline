"""Pipeline orchestration shared by CLI and web."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..config import load_config
from ..download.service import execute_download
from ..errors import InputNotFoundError, VlpError
from ..summarize.service import summarize_transcript
from ..transcribe.service import transcribe_path
from .. import cli as vlp_cli


@dataclass(slots=True)
class PipelineResult:
    """Outcome of a pipeline execution."""

    success: bool
    job_dir: str | None
    manifest_path: Path | None = None
    error: str | None = None
    error_code: str | None = None
    hint: str | None = None


def _resolve_output_root(effective: dict[str, Any]) -> Path:
    output_root = Path(effective["output_dir"])
    if not output_root.is_absolute():
        output_root = Path.cwd() / output_root
    return output_root.resolve()


def _job_dir_from_folder(folder: object | None, output_root: Path) -> str | None:
    if folder is None:
        return None
    absolute = vlp_cli._absolute_from_root(str(folder), output_root)
    if absolute is None:
        return None
    return vlp_cli._relative_to_root(str(folder), output_root)


def _download_job(
    *,
    command_name: str,
    url: str,
    audio_only: bool,
    subtitle_only: bool,
    overrides: dict[str, Any],
) -> PipelineResult:
    bundle = load_config(overrides=overrides)
    effective = bundle.effective_config
    download_config = effective["download"]
    output_root = _resolve_output_root(effective)

    result = execute_download(
        url=url,
        output_dir=effective["output_dir"],
        languages=download_config["subtitles_langs"],
        quality=download_config["quality"],
        audio_only=audio_only,
        subtitle_only=subtitle_only,
        cookies_from_browser=download_config.get("cookies_from_browser"),
        cookie_file=download_config.get("cookie_file"),
        selenium_mode=download_config["selenium"],
        group_output_by_site=bool(effective.get("group_output_by_site", False)),
    )
    manifest_path = vlp_cli._write_download_manifest(
        command_name=command_name,
        result=result,
        effective_config=effective,
        output_root=output_root,
        url=url,
        audio_only=audio_only,
        subtitle_only=subtitle_only,
    )
    job_dir = _job_dir_from_folder(result.get("folder"), output_root)

    if not result["success"]:
        return PipelineResult(
            success=False,
            job_dir=job_dir,
            manifest_path=manifest_path,
            error=str(result.get("error") or "download failed"),
            error_code=str(result.get("error_code") or "DOWNLOAD_FAILED"),
            hint=str(result.get("hint") or "") or None,
        )
    return PipelineResult(success=True, job_dir=job_dir, manifest_path=manifest_path)


def _transcribe_job(*, input_path: Path, overrides: dict[str, Any]) -> PipelineResult:
    if not input_path.exists():
        raise InputNotFoundError(f"input path does not exist: {input_path}")

    bundle = load_config(overrides=overrides)
    whisper_config = bundle.effective_config["whisper"]
    output_root = input_path.parent if input_path.is_file() else input_path
    if not output_root.is_absolute():
        output_root = Path.cwd() / output_root

    result = transcribe_path(
        input_path=input_path,
        output_dir=bundle.effective_config["output_dir"] if overrides.get("output_dir") else None,
        model_size=whisper_config["model"],
        language=whisper_config["language"],
        device=whisper_config["device"],
        compute_type=whisper_config["compute_type"],
        engine=whisper_config["engine"],
    )
    manifest_path = vlp_cli._write_transcribe_manifest(
        result=result,
        effective_config=bundle.effective_config,
        output_root=_resolve_output_root(bundle.effective_config),
        input_path=input_path,
    )
    job_dir = None
    if manifest_path is not None:
        try:
            job_dir = manifest_path.parent.resolve().relative_to(
                _resolve_output_root(bundle.effective_config)
            ).as_posix()
        except ValueError:
            job_dir = manifest_path.parent.as_posix()

    if not result["success"]:
        return PipelineResult(
            success=False,
            job_dir=job_dir,
            manifest_path=manifest_path,
            error=str(result.get("error") or "transcription failed"),
            error_code="TRANSCRIBE_FAILED",
        )
    return PipelineResult(success=True, job_dir=job_dir, manifest_path=manifest_path)


def _summarize_job(*, transcript_path: Path, overrides: dict[str, Any]) -> PipelineResult:
    if not transcript_path.exists():
        raise InputNotFoundError(f"transcript file does not exist: {transcript_path}")

    bundle = load_config(overrides=overrides)
    output_root = _resolve_output_root(bundle.effective_config)
    result = summarize_transcript(
        transcript_path=transcript_path,
        output_dir=bundle.effective_config["output_dir"] if overrides.get("output_dir") else None,
        config=bundle.effective_config,
    )
    manifest_path = vlp_cli._write_summary_manifest(
        result=result,
        effective_config=bundle.effective_config,
        output_root=output_root,
        transcript_path=transcript_path,
    )
    job_dir = None
    if manifest_path is not None:
        try:
            job_dir = manifest_path.parent.resolve().relative_to(output_root).as_posix()
        except ValueError:
            job_dir = manifest_path.parent.as_posix()

    if not result["success"]:
        return PipelineResult(
            success=False,
            job_dir=job_dir,
            manifest_path=manifest_path,
            error=str(result.get("error") or "summary generation failed"),
            error_code="SUMMARY_FAILED",
        )
    return PipelineResult(success=True, job_dir=job_dir, manifest_path=manifest_path)


def _run_pipeline_job(*, url: str, options: dict[str, Any], overrides: dict[str, Any]) -> PipelineResult:
    bundle = load_config(overrides=overrides)
    effective = bundle.effective_config
    download_config = effective["download"]
    whisper_config = effective["whisper"]
    output_root = _resolve_output_root(effective)

    do_transcribe = bool(options.get("do_transcribe", False))
    do_summary = bool(options.get("do_summary", False))

    download_result = execute_download(
        url=url,
        output_dir=effective["output_dir"],
        languages=download_config["subtitles_langs"],
        quality=download_config["quality"],
        audio_only=False,
        subtitle_only=False,
        cookies_from_browser=download_config.get("cookies_from_browser"),
        cookie_file=download_config.get("cookie_file"),
        selenium_mode=download_config["selenium"],
        group_output_by_site=bool(effective.get("group_output_by_site", False)),
    )
    manifest_path = vlp_cli._write_download_manifest(
        command_name="vlp download",
        result=download_result,
        effective_config=effective,
        output_root=output_root,
        url=url,
        audio_only=False,
        subtitle_only=False,
    )
    job_dir = _job_dir_from_folder(download_result.get("folder"), output_root)

    if not download_result["success"]:
        return PipelineResult(
            success=False,
            job_dir=job_dir,
            manifest_path=manifest_path,
            error=str(download_result.get("error") or "download failed"),
            error_code=str(download_result.get("error_code") or "DOWNLOAD_FAILED"),
            hint=str(download_result.get("hint") or "") or None,
        )

    job_dir_path = vlp_cli._absolute_from_root(str(download_result.get("folder")), output_root)
    if job_dir_path is None:
        return PipelineResult(
            success=False,
            job_dir=job_dir,
            manifest_path=manifest_path,
            error="download succeeded but output folder could not be resolved",
            error_code="VLP_ERROR",
        )

    transcript_path = vlp_cli._find_existing_transcript(job_dir_path)
    should_transcribe = (
        bool(download_result.get("needs_whisper"))
        or do_transcribe
        or (do_summary and transcript_path is None)
    )

    if should_transcribe:
        transcribe_result = transcribe_path(
            input_path=job_dir_path,
            output_dir=None,
            model_size=whisper_config["model"],
            language=whisper_config["language"],
            device=whisper_config["device"],
            compute_type=whisper_config["compute_type"],
            engine=whisper_config["engine"],
        )
        manifest_path = (
            vlp_cli._write_transcribe_manifest(
                result=transcribe_result,
                effective_config=effective,
                output_root=output_root,
                input_path=job_dir_path,
            )
            or manifest_path
        )
        if not transcribe_result["success"]:
            return PipelineResult(
                success=False,
                job_dir=job_dir,
                manifest_path=manifest_path,
                error=str(transcribe_result.get("error") or "transcription failed"),
                error_code="TRANSCRIBE_FAILED",
            )
        transcript_path = Path(str(transcribe_result["transcript_file"]))
    elif transcript_path is not None:
        manifest_path = (
            vlp_cli._write_reused_transcript_manifest(
                transcript_path=transcript_path,
                effective_config=effective,
                output_root=output_root,
                input_path=job_dir_path,
            )
            or manifest_path
        )

    if do_summary:
        if transcript_path is None or not transcript_path.exists():
            return PipelineResult(
                success=False,
                job_dir=job_dir,
                manifest_path=manifest_path,
                error="summary step requires transcript.txt but no transcript was found",
                error_code="INPUT_NOT_FOUND",
            )
        summary_path = vlp_cli._find_existing_summary(job_dir_path)
        if summary_path is not None:
            manifest_path = (
                vlp_cli._write_reused_summary_manifest(
                    summary_path=summary_path,
                    effective_config=effective,
                    output_root=output_root,
                    transcript_path=transcript_path,
                )
                or manifest_path
            )
        else:
            summary_result = summarize_transcript(
                transcript_path=transcript_path,
                output_dir=None,
                config=effective,
            )
            manifest_path = (
                vlp_cli._write_summary_manifest(
                    result=summary_result,
                    effective_config=effective,
                    output_root=output_root,
                    transcript_path=transcript_path,
                )
                or manifest_path
            )
            if not summary_result["success"]:
                return PipelineResult(
                    success=False,
                    job_dir=job_dir,
                    manifest_path=manifest_path,
                    error=str(summary_result.get("error") or "summary generation failed"),
                    error_code="SUMMARY_FAILED",
                )

    vlp_cli._finalize_run_manifest(manifest_path, effective_config=effective, url=url)
    return PipelineResult(success=True, job_dir=job_dir, manifest_path=manifest_path)


def _build_overrides(options: dict[str, Any]) -> dict[str, Any]:
    download_opts = options.get("download") if isinstance(options.get("download"), dict) else {}
    whisper_opts = options.get("whisper") if isinstance(options.get("whisper"), dict) else {}
    summary_opts = options.get("summary") if isinstance(options.get("summary"), dict) else {}

    overrides: dict[str, Any] = {
        "output_dir": options.get("output_dir"),
        "group_output_by_site": options.get("group_by_site"),
        "download": {
            "subtitles_langs": options.get("sub_lang") or download_opts.get("subtitles_langs"),
            "quality": options.get("quality") or download_opts.get("quality"),
            "cookies_from_browser": options.get("cookies_from_browser")
            or download_opts.get("cookies_from_browser"),
            "cookie_file": options.get("cookie_file") or download_opts.get("cookie_file"),
            "selenium": options.get("selenium") or download_opts.get("selenium"),
        },
        "whisper": {
            "model": whisper_opts.get("model"),
            "language": whisper_opts.get("language"),
            "engine": whisper_opts.get("engine"),
            "device": whisper_opts.get("device"),
            "compute_type": whisper_opts.get("compute_type"),
        },
        "summary": {
            "provider": summary_opts.get("provider"),
            "model": summary_opts.get("model"),
            "base_url": summary_opts.get("base_url"),
            "max_tokens": summary_opts.get("max_tokens"),
            "temperature": summary_opts.get("temperature"),
        },
    }
    return overrides


def run_job(
    *,
    job_type: str,
    url: str | None = None,
    input_path: str | None = None,
    options: dict[str, Any] | None = None,
) -> PipelineResult:
    """Execute a pipeline job aligned with vlp CLI commands."""
    opts = options or {}
    overrides = _build_overrides(opts)

    if job_type == "download":
        if not url:
            raise VlpError("download requires url", error_code="INPUT_NOT_FOUND")
        return _download_job(
            command_name="vlp download",
            url=url,
            audio_only=bool(opts.get("audio_only", False)),
            subtitle_only=False,
            overrides=overrides,
        )

    if job_type == "download-subs":
        if not url:
            raise VlpError("download-subs requires url", error_code="INPUT_NOT_FOUND")
        if overrides["download"].get("subtitles_langs") is None:
            overrides["download"]["subtitles_langs"] = ["all"]
        return _download_job(
            command_name="vlp download-subs",
            url=url,
            audio_only=False,
            subtitle_only=True,
            overrides=overrides,
        )

    if job_type == "transcribe":
        if not input_path:
            raise VlpError("transcribe requires input_path", error_code="INPUT_NOT_FOUND")
        return _transcribe_job(input_path=Path(input_path), overrides=overrides)

    if job_type == "summarize":
        if not input_path:
            raise VlpError("summarize requires input_path", error_code="INPUT_NOT_FOUND")
        return _summarize_job(transcript_path=Path(input_path), overrides=overrides)

    if job_type == "run":
        if not url:
            raise VlpError("run requires url", error_code="INPUT_NOT_FOUND")
        return _run_pipeline_job(url=url, options=opts, overrides=overrides)

    raise VlpError(f"unsupported job type: {job_type}", error_code="NOT_IMPLEMENTED")
