"""Environment diagnostics helpers."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .transcribe.ffmpeg import resolve_ffmpeg_executable


@dataclass(slots=True)
class DoctorCheck:
    """Represents one doctor check result."""

    name: str
    ok: bool
    detail: str
    hint: str | None = None


def run_checks(config: dict[str, Any] | None = None) -> list[DoctorCheck]:
    """Return the current set of diagnostics."""
    effective_config = config or {}
    checks = [
        _check_python_runtime(),
        _check_python_executable(),
        _check_ffmpeg(),
        _check_selenium_extra(),
    ]
    checks.extend(_check_cookie_configuration(effective_config))
    return checks


def _check_python_runtime() -> DoctorCheck:
    version = sys.version_info
    ok = (version.major, version.minor) >= (3, 10)
    detail = f"Python {version.major}.{version.minor}.{version.micro}"
    hint = None if ok else "video-link-pipeline requires Python 3.10 or newer"
    return DoctorCheck(name="python", ok=ok, detail=detail, hint=hint)


def _check_python_executable() -> DoctorCheck:
    executable = Path(sys.executable).resolve()
    detail = f"python executable: {executable}"
    return DoctorCheck(name="python_env", ok=True, detail=detail)


def _check_ffmpeg() -> DoctorCheck:
    system_ffmpeg = shutil.which("ffmpeg")
    selected_ffmpeg = resolve_ffmpeg_executable()
    if selected_ffmpeg is None:
        return DoctorCheck(
            name="ffmpeg",
            ok=False,
            detail="ffmpeg was not found in PATH and imageio-ffmpeg is unavailable",
            hint="install ffmpeg or keep imageio-ffmpeg in the environment",
        )

    if system_ffmpeg:
        detail = f"using system ffmpeg: {Path(system_ffmpeg).resolve()}"
    else:
        detail = f"using imageio-ffmpeg executable: {Path(selected_ffmpeg).resolve()}"
    return DoctorCheck(name="ffmpeg", ok=True, detail=detail)


def _check_selenium_extra() -> DoctorCheck:
    has_selenium = importlib.util.find_spec("selenium") is not None
    has_webdriver_manager = importlib.util.find_spec("webdriver_manager") is not None
    ok = has_selenium and has_webdriver_manager
    if ok:
        detail = "selenium extra is available"
        return DoctorCheck(name="selenium", ok=True, detail=detail)

    missing = []
    if not has_selenium:
        missing.append("selenium")
    if not has_webdriver_manager:
        missing.append("webdriver-manager")
    detail = f"selenium fallback is unavailable; missing {', '.join(missing)}"
    hint = "install with: pip install 'video-link-pipeline[selenium]'"
    return DoctorCheck(name="selenium", ok=False, detail=detail, hint=hint)


def _check_cookie_configuration(config: dict[str, Any]) -> list[DoctorCheck]:
    download_config = config.get("download", {}) if isinstance(config, dict) else {}
    browser = download_config.get("cookies_from_browser")
    cookie_file = download_config.get("cookie_file")

    if browser:
        return [
            DoctorCheck(
                name="cookies",
                ok=True,
                detail=f"configured browser cookies source: {browser}",
                hint=(
                    "if yt-dlp reports 'could not copy database', close the browser first "
                    "and retry, especially on Windows"
                ),
            )
        ]

    if cookie_file:
        path = Path(str(cookie_file))
        ok = path.exists()
        detail = f"configured cookie file: {path}"
        hint = None if ok else "export a Netscape-format cookies.txt file and point --cookie-file to it"
        return [DoctorCheck(name="cookies", ok=ok, detail=detail, hint=hint)]

    return [
        DoctorCheck(
            name="cookies",
            ok=True,
            detail="no cookie source configured",
            hint="use --cookies-from-browser or --cookie-file when a site requires login",
        )
    ]
