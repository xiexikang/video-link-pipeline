from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from video_link_pipeline.cli import app
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
    assert "could not copy database" in str(cookies_check.hint)
    assert ffmpeg_check.ok is True
    assert ffmpeg_check.code == "ffmpeg_unavailable"
    assert "imageio-ffmpeg" in ffmpeg_check.detail
    assert selenium_check.ok is True
    assert selenium_check.code == "browser_driver_unavailable"

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
    monkeypatch.setattr("video_link_pipeline.cli.run_checks", lambda _: [])

    result = runner.invoke(app, ["doctor", "--config", str(config_path)])

    assert result.exit_code == 0
    assert "summary provider=deepseek" in result.stdout
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
    assert "common diagnostic guidance:" in result.stdout
    assert "ffmpeg_unavailable" in result.stdout
    assert "browser_cookie_locked" in result.stdout
