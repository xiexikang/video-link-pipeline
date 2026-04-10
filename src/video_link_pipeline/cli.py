"""CLI entry point for the video-link-pipeline package."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    help="Unified CLI for video download, transcription, summarization, and subtitle conversion.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("download")
def download_command(
    url: str,
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output root directory."),
) -> None:
    """Download a video URL into a managed job directory."""
    typer.echo(f"download is not implemented yet. url={url} output_dir={output_dir}")


@app.command("transcribe")
def transcribe_command(
    path: Path,
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory."),
) -> None:
    """Transcribe an audio or video path."""
    typer.echo(f"transcribe is not implemented yet. path={path} output_dir={output_dir}")


@app.command("summarize")
def summarize_command(
    transcript: Path,
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory."),
) -> None:
    """Generate a structured summary from a transcript file."""
    typer.echo(f"summarize is not implemented yet. transcript={transcript} output_dir={output_dir}")


@app.command("convert-subtitle")
def convert_subtitle_command(
    input_path: Path = typer.Argument(..., help="Subtitle file or directory."),
    output_format: Optional[str] = typer.Option(None, "--format", help="Target subtitle format."),
) -> None:
    """Convert subtitle files between VTT and SRT."""
    typer.echo(
        f"convert-subtitle is not implemented yet. input={input_path} format={output_format}"
    )


@app.command("run")
def run_command(
    url: str,
    do_transcribe: bool = typer.Option(False, "--do-transcribe", help="Run transcription step."),
    do_summary: bool = typer.Option(False, "--do-summary", help="Run summary step."),
) -> None:
    """Run the end-to-end pipeline for a URL."""
    typer.echo(
        f"run is not implemented yet. url={url} do_transcribe={do_transcribe} do_summary={do_summary}"
    )


@app.command("doctor")
def doctor_command() -> None:
    """Run environment diagnostics for the current installation."""
    typer.echo("doctor is not implemented yet.")


def main() -> None:
    """Entrypoint used by the installed `vlp` script."""
    app()
