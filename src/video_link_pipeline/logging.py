"""Small logging helpers for consistent CLI messaging."""

from __future__ import annotations

import typer


def info(message: str) -> None:
    typer.echo(message)


def success(message: str) -> None:
    typer.secho(message, fg=typer.colors.GREEN)


def warning(message: str) -> None:
    typer.secho(message, fg=typer.colors.YELLOW)


def error(message: str) -> None:
    typer.secho(message, fg=typer.colors.RED, err=True)
