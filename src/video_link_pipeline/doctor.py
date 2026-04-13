"""Environment diagnostics helpers."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .download.diagnostics import warning_code_description, warning_code_remediation
from .download.cookies import KNOWN_BROWSERS
from .transcribe.ffmpeg import resolve_ffmpeg_executable


@dataclass(slots=True)
class DoctorCheck:
    """Represents one doctor check result."""

    name: str
    ok: bool
    detail: str
    code: str | None = None
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


def doctor_guidance(checks: list[DoctorCheck]) -> list[str]:
    lines: list[str] = []
    seen: set[str] = set()
    for check in checks:
        if not check.code or check.code in seen:
            continue
        description = warning_code_description(check.code)
        remediation = warning_code_remediation(check.code)
        if description:
            lines.append(f"{check.code}: {description}")
        if remediation:
            lines.append(f"{check.code} fix: {remediation}")
        seen.add(check.code)
    return lines


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
            code="ffmpeg_unavailable",
            hint="install ffmpeg or keep imageio-ffmpeg in the environment",
        )

    selected_path = Path(selected_ffmpeg).resolve()
    if system_ffmpeg:
        detail = f"selected ffmpeg source=system path={Path(system_ffmpeg).resolve()}"
    else:
        detail = f"selected ffmpeg source=imageio-ffmpeg path={selected_path}"
    return DoctorCheck(name="ffmpeg", ok=True, detail=detail, code="ffmpeg_unavailable")


def _check_selenium_extra() -> DoctorCheck:
    has_selenium = importlib.util.find_spec("selenium") is not None
    has_webdriver_manager = importlib.util.find_spec("webdriver_manager") is not None
    ok = has_selenium and has_webdriver_manager
    if ok:
        detail = "selenium extra is available: selenium=yes webdriver-manager=yes"
        hint = "make sure Chrome is installed and can launch normally if browser fallback is needed"
        return DoctorCheck(
            name="selenium",
            ok=True,
            detail=detail,
            code="browser_driver_unavailable",
            hint=hint,
        )

    missing = []
    if not has_selenium:
        missing.append("selenium")
    if not has_webdriver_manager:
        missing.append("webdriver-manager")
    detail = (
        "selenium fallback is unavailable: "
        f"selenium={'yes' if has_selenium else 'no'} "
        f"webdriver-manager={'yes' if has_webdriver_manager else 'no'}"
    )
    hint = (
        "install with: pip install 'video-link-pipeline[selenium]'"
        f"; missing {', '.join(missing)}"
    )
    return DoctorCheck(
        name="selenium",
        ok=False,
        detail=detail,
        code="browser_driver_unavailable",
        hint=hint,
    )


def _check_cookie_configuration(config: dict[str, Any]) -> list[DoctorCheck]:
    download_config = config.get("download", {}) if isinstance(config, dict) else {}
    browser = download_config.get("cookies_from_browser")
    cookie_file = download_config.get("cookie_file")

    if browser:
        browser_name = str(browser).strip().lower()
        if browser_name not in KNOWN_BROWSERS:
            return [
                DoctorCheck(
                    name="cookies",
                    ok=False,
                    detail=f"configured browser cookies source is not recognized: {browser}",
                    code="browser_cookie_locked",
                    hint="supported browsers: chrome, edge, firefox, opera, brave, vivaldi, safari",
                )
            ]

        windows_hint = (
            "on Windows, fully close the browser before retrying if yt-dlp reports "
            "'could not copy database' or a locked cookies database"
        )
        return [
            DoctorCheck(
                name="cookies",
                ok=True,
                detail=f"configured browser cookies source: {browser_name} (yt-dlp cookiesfrombrowser)",
                code="browser_cookie_locked",
                hint=windows_hint,
            )
        ]

    if cookie_file:
        path = Path(str(cookie_file))
        ok = path.exists()
        detail = f"configured cookie file: {path}"
        if ok:
            detail = f"{detail} exists=yes"
            hint = "make sure the file is in Netscape cookies.txt format if download authentication still fails"
        else:
            detail = f"{detail} exists=no"
            hint = "export a Netscape-format cookies.txt file and point --cookie-file to it"
        return [DoctorCheck(name="cookies", ok=ok, detail=detail, code=None, hint=hint)]

    return [
        DoctorCheck(
            name="cookies",
            ok=True,
            detail="no cookie source configured",
            code="primary_auth_required",
            hint="use --cookies-from-browser or --cookie-file when a site requires login",
        )
    ]
