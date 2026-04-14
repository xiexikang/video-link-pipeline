"""CLI entry point for the video-link-pipeline package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from . import logging as log
from .config import ConfigBundle, load_config, redact_config
from .doctor import doctor_guidance, doctor_reference_lines_for_remaining_codes, run_checks
from .download.service import execute_download
from .errors import InputNotFoundError, NotImplementedVlpError, VlpError
from .manifest import upsert_manifest
from .subtitles.convert import batch_convert_subtitles, convert_subtitle_file
from .summarize.service import summarize_transcript
from .transcribe.service import transcribe_path

app = typer.Typer(
    help="Unified CLI for video download, transcription, summarization, and subtitle conversion.",
    no_args_is_help=True,
    add_completion=False,
)


def _command_context(config_path: Path, overrides: dict[str, Any] | None = None) -> ConfigBundle:
    bundle = load_config(config_path=config_path, overrides=overrides)
    for message in bundle.warnings:
        log.warning(message)
    return bundle


def _render_placeholder(command_name: str, bundle: ConfigBundle, extra: str) -> None:
    redacted = redact_config(bundle.effective_config)
    log.info(f"loaded configuration from {bundle.source_path or 'defaults/.env/environment'}")
    log.info(f"effective output_dir={redacted['output_dir']}")
    raise NotImplementedVlpError(
        f"{command_name} command has not been migrated into the new package yet.",
        hint=extra,
    )


def _absolute_from_root(path_value: str | None, output_root: Path) -> Path | None:
    if not path_value:
        return None
    path = Path(path_value)
    if path.is_absolute():
        return path
    cwd = Path.cwd().resolve()
    root_abs = (cwd / output_root).resolve()
    path_abs = (cwd / path).resolve()
    if root_abs in path_abs.parents or path_abs == root_abs:
        return path_abs
    return (root_abs / path).resolve()


def _relative_to_root(path_value: str | None, output_root: Path) -> str | None:
    absolute_path = _absolute_from_root(path_value, output_root)
    if absolute_path is None:
        return None
    root_abs = (Path.cwd().resolve() / output_root).resolve()
    try:
        return str(absolute_path.relative_to(root_abs))
    except ValueError:
        return str(absolute_path)


def _download_manifest_path(result: dict[str, object], output_root: Path) -> Path | None:
    folder = result.get("folder")
    folder_path = _absolute_from_root(str(folder) if folder else None, output_root)
    if folder_path is None:
        return None
    return folder_path / "manifest.json"


def _write_download_manifest(
    *,
    result: dict[str, object],
    effective_config: dict[str, Any],
    output_root: Path,
    url: str,
    audio_only: bool,
) -> Path | None:
    manifest_path = _download_manifest_path(result, output_root)
    if manifest_path is None:
        return None

    folder = _relative_to_root(str(result.get("folder")) if result.get("folder") else None, output_root)
    artifacts = {
        "folder": folder,
        "video": result.get("video"),
        "audio": result.get("audio"),
        "subtitle_vtt": result.get("subtitle_vtt"),
        "subtitle_srt": result.get("subtitle_srt"),
        "info_json": result.get("info"),
    }
    config_snapshot = redact_config(effective_config)
    config_snapshot["download"] = dict(config_snapshot.get("download", {}))
    config_snapshot["download"]["audio_only"] = audio_only

    upsert_manifest(
        manifest_path,
        command="vlp download",
        input_data={"url": url, "input_path": None},
        config_effective=config_snapshot,
        artifacts={key: value for key, value in artifacts.items() if value is not None},
        execution={
            "download": {
                "success": bool(result.get("success")),
                "used_selenium_fallback": bool(result.get("used_selenium_fallback", False)),
                "fallback_status": result.get("fallback_status"),
                "fallback_context": result.get("fallback_context"),
                "error_code": result.get("error_code") or (None if result.get("success") else "DOWNLOAD_FAILED"),
                "error": result.get("error"),
                "hint": result.get("hint"),
                "warnings": list(result.get("warnings") or []),
                "warning_details": list(result.get("warning_details") or []),
            }
        },
    )
    return manifest_path


def _render_download_diagnostics(result: dict[str, object]) -> None:
    warnings = [str(item) for item in list(result.get("warnings") or []) if item]
    warning_details = [
        item for item in list(result.get("warning_details") or []) if isinstance(item, dict)
    ]
    fallback_context = result.get("fallback_context")
    fallback_status = result.get("fallback_status")
    error_code = result.get("error_code")
    if bool(result.get("used_selenium_fallback")):
        log.warning("download used selenium fallback")
    if fallback_status and fallback_status != "not_attempted":
        log.info(f"fallback status={fallback_status}")
    if error_code:
        log.info(f"download error_code={error_code}")
    if result.get("hint"):
        log.info(f"download hint={result['hint']}")
    if isinstance(fallback_context, dict):
        extraction_source = fallback_context.get("extraction_source")
        media_hint_url = fallback_context.get("media_hint_url")
        if extraction_source:
            log.info(f"fallback extraction_source={extraction_source}")
        if media_hint_url:
            log.info(f"fallback media_hint_url={media_hint_url}")
    if warning_details:
        for item in warning_details[:3]:
            code = item.get("code")
            message = item.get("message")
            stage = item.get("stage")
            if code and message:
                suffix = f" stage={stage}" if stage else ""
                log.info(f"download warning[{code}]{suffix}: {message}")
    else:
        for warning in warnings[:3]:
            log.info(f"download warning: {warning}")


def _write_transcribe_manifest(
    *,
    result: dict[str, object],
    effective_config: dict[str, Any],
    output_root: Path,
    input_path: Path,
) -> Path | None:
    transcript_file = result.get("transcript_file")
    transcript_path = Path(str(transcript_file)) if transcript_file else None
    if transcript_path is None:
        return None
    manifest_path = transcript_path.parent / "manifest.json"

    config_snapshot = redact_config(effective_config)
    artifacts = {
        "transcript_txt": _relative_to_root(str(result.get("transcript_file")), output_root),
        "subtitle_srt": _relative_to_root(str(result.get("srt_file")), output_root),
        "subtitle_vtt": _relative_to_root(str(result.get("vtt_file")), output_root),
        "transcript_json": _relative_to_root(str(result.get("json_file")), output_root),
    }

    upsert_manifest(
        manifest_path,
        command="vlp transcribe",
        input_data={"url": None, "input_path": str(input_path)},
        config_effective=config_snapshot,
        artifacts={key: value for key, value in artifacts.items() if value is not None},
        execution={
            "transcribe": {
                "success": bool(result.get("success")),
                "detected_language": result.get("detected_language"),
                "engine": result.get("engine"),
                "error_code": None if result.get("success") else "TRANSCRIBE_FAILED",
                "error": result.get("error"),
                "warnings": [],
            }
        },
    )
    return manifest_path


def _write_summary_manifest(
    *,
    result: dict[str, object],
    effective_config: dict[str, Any],
    output_root: Path,
    transcript_path: Path,
) -> Path | None:
    summary_file = result.get("summary_file")
    summary_path = Path(str(summary_file)) if summary_file else None
    if summary_path is None:
        return None
    manifest_path = summary_path.parent / "manifest.json"
    config_snapshot = redact_config(effective_config)
    artifacts = {
        "summary_md": _relative_to_root(str(result.get("summary_file")), output_root),
        "keywords_json": _relative_to_root(str(result.get("keywords_file")), output_root),
    }
    upsert_manifest(
        manifest_path,
        command="vlp summarize",
        input_data={"url": None, "input_path": str(transcript_path)},
        config_effective=config_snapshot,
        artifacts={key: value for key, value in artifacts.items() if value is not None},
        execution={
            "summarize": {
                "success": bool(result.get("success")),
                "provider": result.get("provider"),
                "error_code": None if result.get("success") else "SUMMARY_FAILED",
                "error": result.get("error"),
                "warnings": [],
            }
        },
    )
    return manifest_path


def _find_existing_transcript(job_dir: Path) -> Path | None:
    transcript_path = job_dir / "transcript.txt"
    if transcript_path.exists():
        return transcript_path
    matches = sorted(job_dir.glob("**/transcript.txt"))
    return matches[0] if matches else None


def _finalize_run_manifest(
    manifest_path: Path | None,
    *,
    effective_config: dict[str, Any],
    url: str,
) -> None:
    if manifest_path is None:
        return
    upsert_manifest(
        manifest_path,
        command="vlp run",
        input_data={"url": url, "input_path": None},
        config_effective=redact_config(effective_config),
    )


@app.command("download")
def download_command(
    url: str,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output root directory."),
    sub_lang: list[str] | None = typer.Option(None, "--sub-lang", help="Subtitle languages."),
    quality: str | None = typer.Option(None, "--quality", help="yt-dlp format selector."),
    audio_only: bool = typer.Option(False, "--audio-only", help="Download audio only."),
    cookies_from_browser: str | None = typer.Option(None, "--cookies-from-browser", help="Browser name for yt-dlp cookies."),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", help="Netscape cookie file path."),
    selenium: str | None = typer.Option(None, "--selenium", help="Selenium fallback mode: auto/on/off."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    overrides = {
        "output_dir": str(output_dir) if output_dir else None,
        "download": {
            "subtitles_langs": sub_lang,
            "quality": quality,
            "cookie_file": str(cookie_file) if cookie_file else None,
            "cookies_from_browser": cookies_from_browser,
            "selenium": selenium,
        },
    }
    bundle = _command_context(config, overrides)
    effective = bundle.effective_config
    download_config = effective["download"]
    output_root = Path(effective["output_dir"])

    log.info(f"loaded configuration from {bundle.source_path or 'defaults/.env/environment'}")
    log.info(f"output_dir={effective['output_dir']}")
    result = execute_download(
        url=url,
        output_dir=effective["output_dir"],
        languages=download_config["subtitles_langs"],
        quality=download_config["quality"],
        audio_only=audio_only,
        cookies_from_browser=download_config.get("cookies_from_browser"),
        cookie_file=download_config.get("cookie_file"),
        selenium_mode=download_config["selenium"],
    )

    manifest_path = _write_download_manifest(
        result=result,
        effective_config=effective,
        output_root=output_root,
        url=url,
        audio_only=audio_only,
    )
    _render_download_diagnostics(result)

    if not result["success"]:
        raise VlpError(
            str(result["error"] or "download failed"),
            error_code=str(result.get("error_code") or "DOWNLOAD_FAILED"),
            hint=str(result.get("hint") or "") or None,
        )

    log.success("download completed")
    log.info(f"folder={result['folder']}")
    if result.get("video"):
        log.info(f"video={result['video']}")
    if result.get("audio"):
        log.info(f"audio={result['audio']}")
    if result.get("subtitle"):
        log.info(f"subtitle={result['subtitle']}")
    if result.get("needs_whisper"):
        log.warning("download completed without subtitles; transcription may be needed")
    if manifest_path is not None:
        log.info(f"manifest={manifest_path}")


@app.command("transcribe")
def transcribe_command(
    path: Path,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output directory."),
    model: str | None = typer.Option(None, "--model", help="Whisper model size."),
    language: str | None = typer.Option(None, "--language", help="Language code or auto."),
    engine: str | None = typer.Option(None, "--engine", help="Transcription engine: auto/faster/openai."),
    device: str | None = typer.Option(None, "--device", help="Device: auto/cpu/cuda."),
    compute_type: str | None = typer.Option(None, "--compute-type", help="Compute type: int8/float16/float32."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    if not path.exists():
        raise InputNotFoundError(f"input path does not exist: {path}")
    overrides = {
        "output_dir": str(output_dir) if output_dir else None,
        "whisper": {
            "model": model,
            "language": language,
            "engine": engine,
            "device": device,
            "compute_type": compute_type,
        },
    }
    bundle = _command_context(config, overrides)
    whisper_config = bundle.effective_config["whisper"]
    resolved_output_root = Path(output_dir) if output_dir else path.parent
    result = transcribe_path(
        input_path=path,
        output_dir=bundle.effective_config["output_dir"] if output_dir else None,
        model_size=whisper_config["model"],
        language=whisper_config["language"],
        device=whisper_config["device"],
        compute_type=whisper_config["compute_type"],
        engine=whisper_config["engine"],
    )
    manifest_path = _write_transcribe_manifest(
        result=result,
        effective_config=bundle.effective_config,
        output_root=resolved_output_root,
        input_path=path,
    )
    if not result["success"]:
        raise VlpError(str(result["error"] or "transcription failed"), error_code="TRANSCRIBE_FAILED")
    log.success("transcription completed")
    log.info(f"transcript={result['transcript_file']}")
    log.info(f"srt={result['srt_file']}")
    log.info(f"vtt={result['vtt_file']}")
    if result.get("detected_language"):
        log.info(f"detected_language={result['detected_language']}")
    if manifest_path is not None:
        log.info(f"manifest={manifest_path}")


@app.command("summarize")
def summarize_command(
    transcript: Path,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output directory."),
    provider: str | None = typer.Option(None, "--provider", help="Summary provider."),
    model: str | None = typer.Option(None, "--model", help="Provider model name."),
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI-compatible base URL."),
    max_tokens: int | None = typer.Option(None, "--max-tokens", help="Maximum output tokens."),
    temperature: float | None = typer.Option(None, "--temperature", help="Sampling temperature."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    if not transcript.exists():
        raise InputNotFoundError(f"transcript file does not exist: {transcript}")
    overrides = {
        "output_dir": str(output_dir) if output_dir else None,
        "summary": {
            "provider": provider,
            "model": model,
            "base_url": base_url,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
    }
    bundle = _command_context(config, overrides)
    resolved_output_root = Path(output_dir) if output_dir else transcript.parent
    result = summarize_transcript(
        transcript_path=transcript,
        output_dir=bundle.effective_config["output_dir"] if output_dir else None,
        config=bundle.effective_config,
    )
    manifest_path = _write_summary_manifest(
        result=result,
        effective_config=bundle.effective_config,
        output_root=resolved_output_root,
        transcript_path=transcript,
    )
    if not result["success"]:
        raise VlpError(str(result["error"] or "summary generation failed"), error_code="SUMMARY_FAILED")
    log.success("summary completed")
    log.info(f"summary={result['summary_file']}")
    log.info(f"keywords={result['keywords_file']}")
    if result.get("one_sentence_summary"):
        log.info(f"one_sentence_summary={result['one_sentence_summary']}")
    if manifest_path is not None:
        log.info(f"manifest={manifest_path}")


@app.command("convert-subtitle")
def convert_subtitle_command(
    input_path: Path = typer.Argument(..., help="Subtitle file or directory."),
    output_path: Path | None = typer.Option(None, "--output", help="Output subtitle file path."),
    output_format: str | None = typer.Option(None, "--format", help="Target subtitle format."),
    batch: bool = typer.Option(False, "--batch", help="Convert matching subtitle files in a directory."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    if not input_path.exists():
        raise InputNotFoundError(f"subtitle input does not exist: {input_path}")
    _command_context(config)

    if batch:
        result = batch_convert_subtitles(input_path, output_format or "srt")
        log.success(
            f"batch subtitle conversion completed: {result['converted_files']}/{result['matched_files']}"
        )
        return

    result = convert_subtitle_file(input_path, output_path=output_path, output_format=output_format)
    if result["changed"]:
        log.success("subtitle conversion completed")
    else:
        log.info(str(result["message"]))
    log.info(f"input={result['input_path']} ({result['input_format']})")
    log.info(f"output={result['output_path']} ({result['output_format']})")


@app.command("run")
def run_command(
    url: str,
    do_transcribe: bool = typer.Option(False, "--do-transcribe", help="Run transcription step."),
    do_summary: bool = typer.Option(False, "--do-summary", help="Run summary step."),
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output root directory."),
    sub_lang: list[str] | None = typer.Option(None, "--sub-lang", help="Subtitle languages."),
    quality: str | None = typer.Option(None, "--quality", help="yt-dlp format selector."),
    cookies_from_browser: str | None = typer.Option(None, "--cookies-from-browser", help="Browser name for yt-dlp cookies."),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", help="Netscape cookie file path."),
    selenium: str | None = typer.Option(None, "--selenium", help="Selenium fallback mode: auto/on/off."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    overrides = {
        "output_dir": str(output_dir) if output_dir else None,
        "download": {
            "subtitles_langs": sub_lang,
            "quality": quality,
            "cookie_file": str(cookie_file) if cookie_file else None,
            "cookies_from_browser": cookies_from_browser,
            "selenium": selenium,
        },
    }
    bundle = _command_context(config, overrides)
    effective = bundle.effective_config
    download_config = effective["download"]
    whisper_config = effective["whisper"]
    output_root = Path(effective["output_dir"])

    log.info(f"loaded configuration from {bundle.source_path or 'defaults/.env/environment'}")
    log.info(f"output_dir={effective['output_dir']}")

    download_result = execute_download(
        url=url,
        output_dir=effective["output_dir"],
        languages=download_config["subtitles_langs"],
        quality=download_config["quality"],
        audio_only=False,
        cookies_from_browser=download_config.get("cookies_from_browser"),
        cookie_file=download_config.get("cookie_file"),
        selenium_mode=download_config["selenium"],
    )
    manifest_path = _write_download_manifest(
        result=download_result,
        effective_config=effective,
        output_root=output_root,
        url=url,
        audio_only=False,
    )
    _render_download_diagnostics(download_result)
    if not download_result["success"]:
        raise VlpError(
            str(download_result["error"] or "download failed"),
            error_code=str(download_result.get("error_code") or "DOWNLOAD_FAILED"),
            hint=str(download_result.get("hint") or "") or None,
        )

    job_dir = _absolute_from_root(str(download_result.get("folder")), output_root)
    if job_dir is None:
        raise VlpError("download succeeded but output folder could not be resolved")

    log.success("download completed")
    log.info(f"folder={download_result['folder']}")

    transcript_path = _find_existing_transcript(job_dir)
    should_transcribe = bool(download_result.get("needs_whisper")) or do_transcribe or (do_summary and transcript_path is None)

    if should_transcribe:
        transcribe_result = transcribe_path(
            input_path=job_dir,
            output_dir=None,
            model_size=whisper_config["model"],
            language=whisper_config["language"],
            device=whisper_config["device"],
            compute_type=whisper_config["compute_type"],
            engine=whisper_config["engine"],
        )
        manifest_path = _write_transcribe_manifest(
            result=transcribe_result,
            effective_config=effective,
            output_root=output_root,
            input_path=job_dir,
        ) or manifest_path
        if not transcribe_result["success"]:
            raise VlpError(
                str(transcribe_result["error"] or "transcription failed"),
                error_code="TRANSCRIBE_FAILED",
            )
        transcript_path = Path(str(transcribe_result["transcript_file"]))
        log.success("transcription completed")
        log.info(f"transcript={transcribe_result['transcript_file']}")
    elif transcript_path is not None:
        log.info(f"reusing existing transcript={transcript_path}")

    if do_summary:
        if transcript_path is None or not transcript_path.exists():
            raise VlpError(
                "summary step requires transcript.txt but no transcript was found",
                error_code="INPUT_NOT_FOUND",
            )
        summary_result = summarize_transcript(
            transcript_path=transcript_path,
            output_dir=None,
            config=effective,
        )
        manifest_path = _write_summary_manifest(
            result=summary_result,
            effective_config=effective,
            output_root=output_root,
            transcript_path=transcript_path,
        ) or manifest_path
        if not summary_result["success"]:
            raise VlpError(
                str(summary_result["error"] or "summary generation failed"),
                error_code="SUMMARY_FAILED",
            )
        log.success("summary completed")
        log.info(f"summary={summary_result['summary_file']}")

    _finalize_run_manifest(manifest_path, effective_config=effective, url=url)
    log.success("pipeline completed")
    if manifest_path is not None:
        log.info(f"manifest={manifest_path}")


@app.command("doctor")
def doctor_command(config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML.")) -> None:
    bundle = _command_context(config)
    redacted = redact_config(bundle.effective_config)
    log.info(f"config source={bundle.source_path or 'defaults/.env/environment'}")
    log.info(f"output_dir={redacted['output_dir']}")
    log.info(f"summary provider={redacted['summary']['provider']}")
    checks = run_checks(bundle.effective_config)
    guidance = doctor_guidance(checks)
    reference_lines = doctor_reference_lines_for_remaining_codes(checks)

    has_failures = False

    def _render_doctor_check(check: object) -> None:
        nonlocal has_failures
        section = str(getattr(check, "section", "download_prerequisites"))
        if bool(getattr(check, "ok", False)):
            if section == "config_risks":
                log.info(f"{check.name}: {check.detail}")
            else:
                log.success(f"{check.name}: {check.detail}")
        else:
            has_failures = True
            log.warning(f"{check.name}: {check.detail}")
        if check.hint:
            log.info(f"hint: {check.hint}")

    sections = [
        ("runtime", "runtime:"),
        ("download_prerequisites", "download prerequisites:"),
        ("effective_download_config", "effective download config:"),
        ("config_risks", "config risks:"),
    ]
    for section_key, section_title in sections:
        section_checks = [check for check in checks if getattr(check, "section", "download_prerequisites") == section_key]
        if not section_checks:
            continue
        log.info(section_title)
        for check in section_checks:
            _render_doctor_check(check)

    for check in checks:
        if getattr(check, "section", "download_prerequisites") in {
            "runtime",
            "download_prerequisites",
            "effective_download_config",
            "config_risks",
        }:
            continue
        _render_doctor_check(check)

    if guidance:
        log.info("common diagnostic guidance:")
        for line in guidance:
            log.info(f"- {line}")

    if reference_lines:
        log.info("known diagnostic codes:")
        for line in reference_lines:
            log.info(f"- {line}")

    if has_failures:
        log.warning("doctor found items that may block some workflows")
    else:
        log.success("doctor checks passed")


def main() -> int:
    try:
        app()
    except VlpError as exc:
        log.render_vlp_error(exc)
        return 1
    return 0
