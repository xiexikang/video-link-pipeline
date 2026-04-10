"""CLI entry point for the video-link-pipeline package."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .config import ConfigBundle, load_config, redact_config
from .errors import InputNotFoundError, NotImplementedVlpError, VlpError
from . import logging as log

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
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Download a video URL into a managed job directory."""
    bundle = _command_context(config, {"output_dir": str(output_dir) if output_dir else None})
    _render_placeholder("download", bundle, f"url={url}")


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
    output_format: str | None = typer.Option(None, "--format", help="Target subtitle format."),
    config: Path = typer.Option(Path("config.yaml"), "--config", help="Path to config YAML."),
) -> None:
    """Convert subtitle files between VTT and SRT."""
    if not input_path.exists():
        raise InputNotFoundError(f"subtitle input does not exist: {input_path}")
    bundle = _command_context(config)
    _render_placeholder("convert-subtitle", bundle, f"input={input_path} format={output_format}")


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
