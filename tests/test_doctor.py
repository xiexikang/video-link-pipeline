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
        ],
    )

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "summary provider=deepseek" in result.stdout
    assert "runtime:" in result.stdout
    assert "download prerequisites:" in result.stdout
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


def test_run_checks_reports_missing_cookie_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("video_link_pipeline.doctor.resolve_ffmpeg_executable", lambda: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr("video_link_pipeline.doctor.shutil.which", lambda _: "C:/ffmpeg/bin/ffmpeg.exe")
    monkeypatch.setattr(
        "video_link_pipeline.doctor.importlib.util.find_spec",
        lambda name: object() if name in {"selenium", "webdriver_manager"} else None,
    )

    checks = run_checks({"download": {"cookie_file": str(tmp_path / "missing-cookies.txt")}})
    cookies_check = next(check for check in checks if check.name == "cookies")

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
    cookies_check = next(check for check in checks if check.name == "cookies")

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
