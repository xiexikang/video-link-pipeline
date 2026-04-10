"""Small logging helpers for consistent CLI messaging."""

from __future__ import annotations

from typing import Iterable

import typer

from .errors import VlpError


def info(message: str) -> None:
    typer.echo(f"[INFO] {message}")


def success(message: str) -> None:
    typer.secho(f"[OK] {message}", fg=typer.colors.GREEN)


def warning(message: str) -> None:
    typer.secho(f"[WARN] {message}", fg=typer.colors.YELLOW)


def error(message: str) -> None:
    typer.secho(f"[ERROR] {message}", fg=typer.colors.RED, err=True)


def bullet_list(title: str, items: Iterable[str]) -> None:
    typed_items = list(items)
    if not typed_items:
        return
    info(title)
    for item in typed_items:
        typer.echo(f"- {item}")


def render_vlp_error(exc: VlpError) -> None:
    error(f"{exc.error_code}: {exc.message}")
    if exc.hint:
        warning(exc.hint)
