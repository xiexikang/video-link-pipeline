"""Environment diagnostics helpers."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .download.diagnostics import (
    preferred_warning_hint,
    warning_code_description,
    warning_code_remediation,
)
from .download.cookies import KNOWN_BROWSERS
from .transcribe.ffmpeg import resolve_ffmpeg_executable


@dataclass(slots=True)
class DoctorCheck:
    """Represents one doctor check result."""

    name: str
    ok: bool
    detail: str
    section: str = "download_prerequisites"
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
    checks.extend(_check_download_config_risks(effective_config))
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
    return DoctorCheck(name="python", ok=ok, detail=detail, section="runtime", hint=hint)


def _check_python_executable() -> DoctorCheck:
    executable = Path(sys.executable).resolve()
    detail = f"python executable: {executable}"
    return DoctorCheck(name="python_env", ok=True, detail=detail, section="runtime")


def _check_ffmpeg() -> DoctorCheck:
    system_ffmpeg = shutil.which("ffmpeg")
    selected_ffmpeg = resolve_ffmpeg_executable()
    if selected_ffmpeg is None:
        return DoctorCheck(
            name="ffmpeg",
            ok=False,
            detail="ffmpeg was not found in PATH and imageio-ffmpeg is unavailable",
            section="download_prerequisites",
            code="ffmpeg_unavailable",
            hint=preferred_warning_hint("ffmpeg_unavailable"),
        )

    selected_path = Path(selected_ffmpeg).resolve()
    if system_ffmpeg:
        detail = f"selected ffmpeg source=system path={Path(system_ffmpeg).resolve()}"
    else:
        detail = f"selected ffmpeg source=imageio-ffmpeg path={selected_path}"
    return DoctorCheck(
        name="ffmpeg",
        ok=True,
        detail=detail,
        section="download_prerequisites",
        code="ffmpeg_unavailable",
    )


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
            section="download_prerequisites",
            code="browser_driver_unavailable",
            hint=preferred_warning_hint("browser_driver_unavailable", hint),
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
        section="download_prerequisites",
        code="browser_driver_unavailable",
        hint=preferred_warning_hint("browser_driver_unavailable", hint),
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
                    section="download_prerequisites",
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
                section="download_prerequisites",
                code="browser_cookie_locked",
                hint=preferred_warning_hint("browser_cookie_locked", windows_hint),
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
        return [
            DoctorCheck(
                name="cookies",
                ok=ok,
                detail=detail,
                section="download_prerequisites",
                code=None,
                hint=hint,
            )
        ]

    return [
        DoctorCheck(
            name="cookies",
            ok=True,
            detail="no cookie source configured",
            section="download_prerequisites",
            code="primary_auth_required",
            hint=preferred_warning_hint(
                "primary_auth_required",
                "use --cookies-from-browser or --cookie-file when a site requires login",
            ),
        )
    ]


def _check_download_config_risks(config: dict[str, Any]) -> list[DoctorCheck]:
    download_config = config.get("download", {}) if isinstance(config, dict) else {}
    browser = download_config.get("cookies_from_browser")
    cookie_file = download_config.get("cookie_file")
    selenium_mode = str(download_config.get("selenium") or "auto").strip().lower()
    checks: list[DoctorCheck] = []

    effective_browser = str(browser).strip().lower() if browser else "none"
    effective_cookie_file = str(cookie_file) if cookie_file else "none"

    checks.append(
        DoctorCheck(
            name="download_selenium",
            ok=True,
            detail=f"effective download.selenium={selenium_mode}",
            section="config_risks",
        )
    )
    checks.append(
        DoctorCheck(
            name="download_cookies_from_browser",
            ok=True,
            detail=f"effective download.cookies_from_browser={effective_browser}",
            section="config_risks",
        )
    )
    checks.append(
        DoctorCheck(
            name="download_cookie_file",
            ok=True,
            detail=f"effective download.cookie_file={effective_cookie_file}",
            section="config_risks",
        )
    )

    if browser and cookie_file:
        checks.append(
            DoctorCheck(
                name="download_config",
                ok=False,
                detail="download config sets both cookies_from_browser and cookie_file",
                section="config_risks",
                hint="use either --cookies-from-browser or --cookie-file, not both",
            )
        )

    if selenium_mode == "off" and not browser and not cookie_file:
        checks.append(
            DoctorCheck(
                name="download_config",
                ok=True,
                detail="download selenium=off and no cookie source is configured",
                section="config_risks",
                code="primary_auth_required",
                hint=preferred_warning_hint(
                    "primary_auth_required",
                    "sites that require login or anti-bot verification may fail without cookies or fallback",
                ),
            )
        )

    if selenium_mode == "on":
        checks.append(
            DoctorCheck(
                name="download_config",
                ok=True,
                detail="download selenium=on will always attempt browser fallback after qualifying failures",
                section="config_risks",
                code="browser_driver_unavailable",
                hint=preferred_warning_hint(
                    "browser_driver_unavailable",
                    "make sure the Selenium extra is installed and Chrome can launch normally",
                ),
            )
        )

    return checks
