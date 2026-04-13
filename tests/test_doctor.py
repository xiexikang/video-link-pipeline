from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from video_link_pipeline.cli import app
from video_link_pipeline.doctor import run_checks

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
    assert "chrome" in cookies_check.detail
    assert "could not copy database" in str(cookies_check.hint)
    assert ffmpeg_check.ok is True
    assert "imageio-ffmpeg" in ffmpeg_check.detail
    assert selenium_check.ok is True


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
