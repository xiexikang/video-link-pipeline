"""CLI entry point for the video-link-pipeline package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from . import logging as log
from .config import ConfigBundle, load_config, redact_config
from .download.service import execute_download
from .errors import InputNotFoundError, NotImplementedVlpError, VlpError
from .subtitles.convert import batch_convert_subtitles, convert_subtitle_file

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


@app.command("download")
def download_command(
    url: str,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output root directory."),
    sub_lang: list[str] | None = typer.Option(None, "--sub-lang", help="Subtitle languages."),
    quality: str | None = typer.Option(None, "--quality", help="yt-dlp format selector."),
    audio_only: bool = typer.Option(False, "--audio-only", help="Download audio only."),
    cookies_from_browser: str | None = typer.Option(None, "--cookies-from-browser", help="Browser name for yt-dlp cookies."),
    cookie_file: Path | None = typer.Option(None, "--cookie-file", help="Netscape cookie file path."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Download a video URL into a managed job directory."""
    overrides = {
        "output_dir": str(output_dir) if output_dir else None,
        "download": {
            "subtitles_langs": sub_lang,
            "quality": quality,
            "cookie_file": str(cookie_file) if cookie_file else None,
            "cookies_from_browser": cookies_from_browser,
        },
    }
    bundle = _command_context(config, overrides)
    effective = bundle.effective_config
    download_config = effective["download"]

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
    )

    if not result["success"]:
        raise VlpError(str(result["error"] or "download failed"), error_code="DOWNLOAD_FAILED")

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


@app.command("transcribe")
def transcribe_command(
    path: Path,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output directory."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Transcribe an audio or video path."""
    if not path.exists():
        raise InputNotFoundError(f"input path does not exist: {path}")
    bundle = _command_context(config, {"output_dir": str(output_dir) if output_dir else None})
    _render_placeholder("transcribe", bundle, f"input={path}")


@app.command("summarize")
def summarize_command(
    transcript: Path,
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output directory."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Generate a structured summary from a transcript file."""
    if not transcript.exists():
        raise InputNotFoundError(f"transcript file does not exist: {transcript}")
    bundle = _command_context(config, {"output_dir": str(output_dir) if output_dir else None})
    _render_placeholder("summarize", bundle, f"transcript={transcript}")


@app.command("convert-subtitle")
def convert_subtitle_command(
    input_path: Path = typer.Argument(..., help="Subtitle file or directory."),
    output_path: Path | None = typer.Option(None, "--output", help="Output subtitle file path."),
    output_format: str | None = typer.Option(None, "--format", help="Target subtitle format."),
    batch: bool = typer.Option(False, "--batch", help="Convert matching subtitle files in a directory."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Convert subtitle files between VTT and SRT."""
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
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Run the end-to-end pipeline for a URL."""
    bundle = _command_context(config)
    _render_placeholder(
        "run",
        bundle,
        f"url={url} do_transcribe={do_transcribe} do_summary={do_summary}",
    )


@app.command("doctor")
def doctor_command(config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML.")) -> None:
    """Run environment diagnostics for the current installation."""
    bundle = _command_context(config)
    redacted = redact_config(bundle.effective_config)
    log.info("doctor command is not implemented yet.")
    log.info(f"config source={bundle.source_path or 'defaults/.env/environment'}")
    log.info(f"summary provider={redacted['summary']['provider']}")


def main() -> int:
    """Entrypoint used by the installed `vlp` script."""
    try:
        app()
    except VlpError as exc:
        log.render_vlp_error(exc)
        return 1
    return 0
