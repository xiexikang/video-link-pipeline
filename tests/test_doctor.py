from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from video_link_pipeline.cli import app
from video_link_pipeline.download.diagnostics import warning_code_remediation
from video_link_pipeline.doctor import doctor_guidance, run_checks

runner = CliRunner()


def test_run_checks_reports_browser_cookie_hint(monkeypatch) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: None)
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"cookies_from_browser": "chrome"}})

    cookies_check = next(check for check in checks if check.name == "cookies")
    ffmpeg_check = next(check for check in checks if check.name == "ffmpeg")
    selenium_check = next(check for check in checks if check.name == "selenium")

    assert cookies_check.ok is True
    assert cookies_check.code == "browser_cookie_locked"
    assert "chrome" in cookies_check.detail
    assert "cookiesfrombrowser" in cookies_check.detail
    assert cookies_check.hint == warning_code_remediation("browser_cookie_locked")
    assert ffmpeg_check.ok is True
    assert ffmpeg_check.code == "ffmpeg_unavailable"
    assert "source=imageio-ffmpeg" in ffmpeg_check.detail
    assert selenium_check.ok is True
    assert selenium_check.code == "browser_driver_unavailable"
    assert "selenium=yes" in selenium_check.detail
    assert "webdriver-manager=yes" in selenium_check.detail
    assert selenium_check.hint == warning_code_remediation("browser_driver_unavailable")

    guidance = doctor_guidance(checks)
    assert any("browser_cookie_locked" in item for item in guidance)
    assert any("ffmpeg_unavailable" in item for item in guidance)


def test_doctor_command_prints_summary_provider(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "output_dir": str(tmp_path / "output"),
                "summary": {"provider": "deepseek"},
                "download": {"cookies_from_browser": "edge"},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "video_link_pipeline.cli.run_checks",
        lambda _: [
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="python",
                ok=True,
                detail="Python 3.11.0",
                section="runtime",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="ffmpeg",
                ok=True,
                detail="selected ffmpeg source=system path=C:/ffmpeg/bin/ffmpeg.exe",
                section="download_prerequisites",
                code="ffmpeg_unavailable",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="download_effective_summary",
                ok=True,
                detail=(
                    "effective download config summary: "
                    "selenium=off cookies_from_browser=edge cookie_file=none"
                ),
                section="effective_download_config",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="download_selenium",
                ok=True,
                detail="effective download.selenium=off",
                section="effective_download_config",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="download_cookies_from_browser",
                ok=True,
                detail="effective download.cookies_from_browser=edge",
                section="effective_download_config",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="download_cookie_file",
                ok=True,
                detail="effective download.cookie_file=none",
                section="effective_download_config",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="download_config",
                ok=True,
                detail="download selenium=off and no cookie source is configured",
                section="config_risks",
                code="primary_auth_required",
            ),
        ],
    )

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "summary provider=deepseek" in result.stdout
    assert "runtime:" in result.stdout
    assert "download prerequisites:" in result.stdout
    assert "effective download config:" in result.stdout
    assert "config risks:" in result.stdout
    assert (
        "[OK] download_effective_summary: effective download config summary: "
        "selenium=off cookies_from_browser=edge cookie_file=none"
    ) in result.stdout
    assert "[OK] download_selenium: effective download.selenium=off" in result.stdout
    assert "[OK] download_cookies_from_browser: effective download.cookies_from_browser=edge" in result.stdout
    assert "[OK] download_cookie_file: effective download.cookie_file=none" in result.stdout
    assert "[INFO] download_config: download selenium=off and no cookie source is configured" in result.stdout
    assert "doctor checks passed" in result.stdout


def test_doctor_command_prints_diagnostic_guidance(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "output_dir": str(tmp_path / "output"),
                "summary": {"provider": "claude"},
                "download": {"cookies_from_browser": "chrome"},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "video_link_pipeline.cli.run_checks",
        lambda _: [
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="ffmpeg",
                ok=False,
                detail="ffmpeg missing",
                code="ffmpeg_unavailable",
                hint="install ffmpeg",
            ),
            __import__("video_link_pipeline.doctor", fromlist=["DoctorCheck"]).DoctorCheck(
                name="cookies",
                ok=True,
                detail="configured browser cookies source: chrome",
                code="browser_cookie_locked",
                hint="close browser first",
            ),
        ],
    )

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "download prerequisites:" in result.stdout
    assert "common diagnostic guidance:" in result.stdout
    assert "ffmpeg_unavailable" in result.stdout
    assert "browser_cookie_locked" in result.stdout


def test_run_checks_reports_conflicting_cookie_sources(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks(
        {
            "download": {
                "cookies_from_browser": "chrome",
                "cookie_file": str(tmp_path / "cookies.txt"),
                "selenium": "auto",
            }
        }
    )
    risk_check = next(check for check in checks if check.name == "download_config" and check.section == "config_risks")

    assert risk_check.ok is False
    assert "both cookies_from_browser and cookie_file" in risk_check.detail
    assert "not both" in str(risk_check.hint)


def test_run_checks_reports_selenium_off_without_cookie_source(monkeypatch) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"selenium": "off"}})
    summary_check = next(check for check in checks if check.name == "download_effective_summary")
    selenium_mode_check = next(check for check in checks if check.name == "download_selenium")
    browser_check = next(check for check in checks if check.name == "download_cookies_from_browser")
    cookie_file_check = next(check for check in checks if check.name == "download_cookie_file")
    risk_check = next(check for check in checks if check.name == "download_config" and check.section == "config_risks")

    assert summary_check.section == "effective_download_config"
    assert (
        summary_check.detail
        == "effective download config summary: selenium=off cookies_from_browser=none cookie_file=none"
    )
    assert selenium_mode_check.ok is True
    assert selenium_mode_check.section == "effective_download_config"
    assert selenium_mode_check.detail == "effective download.selenium=off"
    assert browser_check.section == "effective_download_config"
    assert browser_check.detail == "effective download.cookies_from_browser=none"
    assert cookie_file_check.section == "effective_download_config"
    assert cookie_file_check.detail == "effective download.cookie_file=none"
    assert risk_check.ok is True
    assert risk_check.code == "primary_auth_required"
    assert risk_check.hint == warning_code_remediation("primary_auth_required")


def test_run_checks_reports_selenium_on_risk(monkeypatch) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"selenium": "on"}})
    summary_check = next(check for check in checks if check.name == "download_effective_summary")
    selenium_mode_check = next(check for check in checks if check.name == "download_selenium")
    browser_check = next(check for check in checks if check.name == "download_cookies_from_browser")
    cookie_file_check = next(check for check in checks if check.name == "download_cookie_file")
    risk_check = next(check for check in checks if check.name == "download_config" and check.section == "config_risks")

    assert (
        summary_check.detail
        == "effective download config summary: selenium=on cookies_from_browser=none cookie_file=none"
    )
    assert selenium_mode_check.ok is True
    assert selenium_mode_check.section == "effective_download_config"
    assert selenium_mode_check.detail == "effective download.selenium=on"
    assert browser_check.detail == "effective download.cookies_from_browser=none"
    assert cookie_file_check.detail == "effective download.cookie_file=none"
    assert risk_check.ok is True
    assert risk_check.code == "browser_driver_unavailable"
    assert risk_check.hint == warning_code_remediation("browser_driver_unavailable")


def test_run_checks_reports_missing_cookie_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"cookie_file": str(tmp_path / "missing-cookies.txt")}})
    summary_check = next(check for check in checks if check.name == "download_effective_summary")
    browser_check = next(check for check in checks if check.name == "download_cookies_from_browser")
    cookie_file_value_check = next(check for check in checks if check.name == "download_cookie_file")
    cookies_check = next(check for check in checks if check.name == "cookies")

    assert (
        summary_check.detail
        == f"effective download config summary: selenium=auto cookies_from_browser=none cookie_file={tmp_path / 'missing-cookies.txt'}"
    )
    assert browser_check.detail == "effective download.cookies_from_browser=none"
    assert cookie_file_value_check.detail == f"effective download.cookie_file={tmp_path / 'missing-cookies.txt'}"
    assert cookies_check.ok is False
    assert "exists=no" in cookies_check.detail
    assert "Netscape-format cookies.txt" in str(cookies_check.hint)


def test_run_checks_reports_unknown_browser_cookie_source(monkeypatch) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"cookies_from_browser": "unknown-browser"}})
    summary_check = next(check for check in checks if check.name == "download_effective_summary")
    browser_check = next(check for check in checks if check.name == "download_cookies_from_browser")
    cookie_file_check = next(check for check in checks if check.name == "download_cookie_file")
    cookies_check = next(check for check in checks if check.name == "cookies")

    assert (
        summary_check.detail
        == "effective download config summary: selenium=auto cookies_from_browser=unknown-browser cookie_file=none"
    )
    assert browser_check.detail == "effective download.cookies_from_browser=unknown-browser"
    assert cookie_file_check.detail == "effective download.cookie_file=none"
    assert cookies_check.ok is False
    assert "not recognized" in cookies_check.detail
    assert "supported browsers" in str(cookies_check.hint)


def test_run_checks_uses_shared_primary_auth_hint_when_cookies_not_configured(monkeypatch) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {}})
    cookies_check = next(check for check in checks if check.name == "cookies")

    assert cookies_check.code == "primary_auth_required"
    assert cookies_check.hint == warning_code_remediation("primary_auth_required")
