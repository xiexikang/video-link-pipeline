from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from video_link_pipeline.cli import app

runner = CliRunner()


def test_download_manifest_records_fallback_diagnostics(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-789-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-789-demo",
            "video": "video-789-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "error_code": None,
            "error_stage": None,
            "fallback_status": "succeeded",
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via next-data:playAddr",
            ],
            "fallback_context": {
                "resolved_url": "https://example.com/resolved",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://cdn.example.com/media.m3u8",
                "site_name": "example.com",
                "extraction_source": "next-data:playAddr",
            },
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    download_execution = manifest["execution"]["download"]
    assert download_execution["used_selenium_fallback"] is True
    assert download_execution["error_code"] is None
    assert download_execution["fallback_status"] == "succeeded"
    assert download_execution["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert download_execution["fallback_context"]["extraction_source"] == "next-data:playAddr"
    assert any("triggered selenium fallback" in item for item in download_execution["warnings"])


def test_download_cli_prints_fallback_diagnostics(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-999-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-999-demo",
            "video": "video-999-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "error_code": "DOWNLOAD_PRIMARY_FAILED",
            "error_stage": "primary_download",
            "fallback_status": "triggered",
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via jsonld:contentUrl",
            ],
            "fallback_context": {
                "resolved_url": "https://example.com/resolved",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://cdn.example.com/media.m3u8",
                "site_name": "example.com",
                "extraction_source": "jsonld:contentUrl",
            },
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    assert "download used selenium fallback" in result.stdout
    assert "fallback status=triggered" in result.stdout
    assert "download error_code=DOWNLOAD_PRIMARY_FAILED" in result.stdout
    assert "fallback extraction_source=jsonld:contentUrl" in result.stdout
    assert "fallback media_hint_url=https://cdn.example.com/media.m3u8" in result.stdout


def test_download_cli_uses_detailed_error_code_on_failure(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    output_root.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "folder": None,
            "video": None,
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error_code": "DOWNLOAD_FALLBACK_RETRY_FAILED",
            "error_stage": "fallback_retry",
            "fallback_status": "retry_failed",
            "warnings": ["selenium fallback prepared but yt-dlp retry still failed"],
            "fallback_context": None,
            "error": "final retry failed",
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "download error_code=DOWNLOAD_FALLBACK_RETRY_FAILED" in result.stdout
    assert "fallback status=retry_failed" in result.stdout
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert str(result.exception) == "final retry failed"
