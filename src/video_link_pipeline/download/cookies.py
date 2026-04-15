"""Cookie parsing and normalization helpers for downloads."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .diagnostics import supported_browser_names, supported_browsers_hint
from ..errors import ConfigError, InputNotFoundError

KNOWN_BROWSERS = set(supported_browser_names())


@dataclass(slots=True)
class CookieSource:
    """Normalized cookie source for yt-dlp integration."""

    browser: str | None = None
    cookie_file: Path | None = None


def parse_cookie_file(cookie_file: str | Path) -> list[dict[str, Any]]:
    """Parse a Netscape-format cookies file into dictionaries."""
    source_path = Path(cookie_file)
    if not source_path.exists():
        raise InputNotFoundError(f"cookie file does not exist: {source_path}")

    cookies: list[dict[str, Any]] = []
    try:
        with source_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("#") or not line.strip():
                    continue
                fields = line.strip().split("\t")
                if len(fields) < 7:
                    continue
                cookies.append(
                    {
                        "domain": fields[0],
                        "flag": fields[1] == "TRUE",
                        "path": fields[2],
                        "secure": fields[3] == "TRUE",
                        "expiration": fields[4],
                        "name": fields[5],
                        "value": fields[6],
                    }
                )
    except OSError as exc:
        raise ConfigError(f"failed to read cookie file: {source_path}", hint=str(exc)) from exc

    return cookies


def normalize_cookie_source(
    cookies_from_browser: str | None = None,
    cookie_file: str | Path | None = None,
) -> CookieSource:
    """Normalize browser/file cookie settings into one structured object."""
    if cookies_from_browser and cookie_file:
        raise ConfigError(
            "cookies_from_browser and cookie_file are mutually exclusive",
            hint="use either --cookies-from-browser or --cookie-file",
        )

    if cookie_file is not None:
        path = Path(cookie_file)
        if not path.exists():
            raise InputNotFoundError(f"cookie file does not exist: {path}")
        return CookieSource(cookie_file=path)

    if cookies_from_browser is None:
        return CookieSource()

    normalized = cookies_from_browser.strip().lower()
    if normalized in KNOWN_BROWSERS:
        return CookieSource(browser=normalized)

    path = Path(cookies_from_browser)
    if path.exists():
        return CookieSource(cookie_file=path)

    raise ConfigError(
        f"unknown browser name or cookie file path: {cookies_from_browser}",
        hint=supported_browsers_hint(),
    )


def build_cookie_options(cookie_source: CookieSource) -> dict[str, Any]:
    """Build yt-dlp cookie options from a normalized cookie source."""
    options: dict[str, Any] = {}
    if cookie_source.browser:
        options["cookiesfrombrowser"] = (cookie_source.browser,)
    if cookie_source.cookie_file:
        options["cookiefile"] = str(cookie_source.cookie_file)
    return options
