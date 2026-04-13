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
    assert "fallback extraction_source=jsonld:contentUrl" in result.stdout
    assert "fallback media_hint_url=https://cdn.example.com/media.m3u8" in result.stdout
