from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from video_link_pipeline.cli import app

runner = CliRunner()


def test_cookies_login_command_exports_cookie_file_hint(monkeypatch, tmp_path: Path) -> None:
    cookie_file = tmp_path / "cookies.txt"
    profile_dir = tmp_path / "profile"

    def fake_export(**kwargs: object) -> Path:
        assert kwargs["url"] == "https://example.com/login"
        assert kwargs["cookie_file"] == cookie_file
        assert kwargs["profile_dir"] == profile_dir
        assert callable(kwargs["prompt"])
        cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
        return cookie_file

    monkeypatch.setattr("video_link_pipeline.cli.export_cookies_after_login", fake_export)

    result = runner.invoke(
        app,
        [
            "cookies-login",
            "https://example.com/login",
            "--cookie-file",
            str(cookie_file),
            "--profile-dir",
            str(profile_dir),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert "cookies exported" in result.stdout
    assert f"--cookie-file {cookie_file}" in result.stdout
