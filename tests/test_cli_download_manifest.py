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
            "media_duration_seconds": 95.0,
            "media_duration_human": "1:35",
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "started_at": "2026-04-16T10:00:00Z",
            "started_at_local": "2026-04-16T18:00:00+08:00",
            "finished_at": "2026-04-16T10:00:05Z",
            "finished_at_local": "2026-04-16T18:00:05+08:00",
            "elapsed_seconds": 5.0,
            "error_code": None,
            "error_stage": None,
            "fallback_status": "succeeded",
            "hint": None,
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via next-data:playAddr",
            ],
            "warning_details": [
                {
                    "code": "primary_http_403",
                    "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                    "stage": "primary_download",
                },
                {
                    "code": "fallback_context_prepared",
                    "message": "selenium fallback context prepared via next-data:playAddr",
                    "stage": "fallback_prepare",
                },
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
    assert "created_at_local" in manifest
    assert "updated_at_local" in manifest
    assert manifest["media"]["duration_seconds"] == 95.0
    assert manifest["media"]["duration_human"] == "1:35"
    assert download_execution["used_selenium_fallback"] is True
    assert download_execution["error_code"] is None
    assert download_execution["hint"] is None
    assert download_execution["fallback_status"] == "succeeded"
    assert download_execution["started_at"] == "2026-04-16T10:00:00Z"
    assert download_execution["started_at_local"] == "2026-04-16T18:00:00+08:00"
    assert download_execution["finished_at"] == "2026-04-16T10:00:05Z"
    assert download_execution["finished_at_local"] == "2026-04-16T18:00:05+08:00"
    assert download_execution["elapsed_seconds"] == 5.0
    assert download_execution["warning_details"][0]["code"] == "primary_http_403"
    assert download_execution["warning_details"][1]["code"] == "fallback_context_prepared"
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
            "hint": "Try browser cookies, wait before retrying, or switch to Selenium fallback if the site is anti-bot protected.",
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via jsonld:contentUrl",
            ],
            "warning_details": [
                {
                    "code": "primary_http_403",
                    "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                    "stage": "primary_download",
                },
                {
                    "code": "fallback_context_prepared",
                    "message": "selenium fallback context prepared via jsonld:contentUrl",
                    "stage": "fallback_prepare",
                },
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
    assert "download fallback_status=triggered" in result.stdout
    assert "download error_code=DOWNLOAD_PRIMARY_FAILED" in result.stdout
    assert "download error_stage=primary_download" in result.stdout
    assert "download hint=Try browser cookies, wait before retrying, or switch to Selenium fallback if the site is anti-bot protected." in result.stdout
    assert "download warning_code=primary_http_403 stage=primary_download" in result.stdout
    assert "download fallback_context.extraction_source=jsonld:contentUrl" in result.stdout
    assert "download fallback_context.media_hint_url=https://cdn.example.com/media.m3u8" in result.stdout
    assert "download fallback_context.canonical_url=https://example.com/watch/demo" in result.stdout
    assert "download fallback_context.resolved_url=https://example.com/resolved" in result.stdout


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
            "hint": "Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` and make sure Chrome can start normally.",
            "warnings": ["selenium fallback prepared but yt-dlp retry still failed"],
            "warning_details": [
                {
                    "code": "fallback_retry_hint",
                    "message": "selenium fallback prepared but yt-dlp retry still failed",
                    "stage": "fallback_retry",
                }
            ],
            "fallback_context": None,
            "error": "final retry failed",
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    assert "download error_code=DOWNLOAD_FALLBACK_RETRY_FAILED" in result.stdout
    assert "download fallback_status=retry_failed" in result.stdout
    assert "download error_stage=fallback_retry" in result.stdout
    assert "download hint=Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` and make sure Chrome can start normally." in result.stdout
    assert "download warning_code=fallback_retry_hint stage=fallback_retry" in result.stdout
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert getattr(result.exception, "hint", None) == "Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` and make sure Chrome can start normally."


def test_download_manifest_records_grouped_site_folder(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "bilibili" / "video-789-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "output_dir": str(output_root),
                "group_output_by_site": True,
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        return {
            "success": True,
            "folder": str(job_dir),
            "video": None,
            "audio": None,
            "subtitle": "bilibili/video-789-demo/subtitle.srt",
            "subtitle_vtt": None,
            "subtitle_srt": "bilibili/video-789-demo/subtitle.srt",
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error_code": None,
            "error_stage": None,
            "fallback_status": "not_attempted",
            "hint": None,
            "warnings": [],
            "warning_details": [],
            "fallback_context": None,
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download-subs", "https://www.bilibili.com/video/BV1demo", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config_effective"]["group_output_by_site"] is True
    assert manifest["artifacts"]["folder"] == "bilibili/video-789-demo"
    assert manifest["artifacts"]["subtitle_srt"] == "bilibili/video-789-demo/subtitle.srt"


def test_download_failure_with_job_dir_still_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-failed-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "folder": "video-failed-demo",
            "video": None,
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "media_duration_seconds": 95.0,
            "media_duration_human": "1:35",
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "started_at": "2026-04-16T10:00:00Z",
            "started_at_local": "2026-04-16T18:00:00+08:00",
            "finished_at": "2026-04-16T10:00:07Z",
            "finished_at_local": "2026-04-16T18:00:07+08:00",
            "elapsed_seconds": 7.0,
            "error_code": "DOWNLOAD_FALLBACK_RETRY_FAILED",
            "error_stage": "fallback_retry",
            "fallback_status": "retry_failed",
            "hint": "Install the Selenium extra and verify the browser driver can start normally.",
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback prepared but yt-dlp retry still failed",
            ],
            "warning_details": [
                {
                    "code": "primary_http_403",
                    "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                    "stage": "primary_download",
                },
                {
                    "code": "fallback_retry_hint",
                    "message": "selenium fallback prepared but yt-dlp retry still failed",
                    "stage": "fallback_retry",
                },
            ],
            "fallback_context": {
                "resolved_url": "https://example.com/resolved",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://cdn.example.com/media.m3u8",
                "site_name": "example.com",
                "extraction_source": "jsonld:contentUrl",
            },
            "error": "final retry failed",
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    download_execution = manifest["execution"]["download"]
    assert manifest["command"] == "vlp download"
    assert manifest["input"]["url"] == "https://example.com/video"
    assert manifest["artifacts"]["folder"] == "video-failed-demo"
    assert manifest["media"]["duration_seconds"] == 95.0
    assert manifest["media"]["duration_human"] == "1:35"
    assert download_execution["success"] is False
    assert download_execution["used_selenium_fallback"] is True
    assert download_execution["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert download_execution["error"] == "final retry failed"
    assert download_execution["hint"] == "Install the Selenium extra and verify the browser driver can start normally."
    assert download_execution["fallback_status"] == "retry_failed"
    assert download_execution["started_at"] == "2026-04-16T10:00:00Z"
    assert download_execution["started_at_local"] == "2026-04-16T18:00:00+08:00"
    assert download_execution["finished_at"] == "2026-04-16T10:00:07Z"
    assert download_execution["finished_at_local"] == "2026-04-16T18:00:07+08:00"
    assert download_execution["elapsed_seconds"] == 7.0
    assert download_execution["warning_details"][0]["code"] == "primary_http_403"
    assert download_execution["warning_details"][1]["code"] == "fallback_retry_hint"
    assert download_execution["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "DOWNLOAD_FALLBACK_RETRY_FAILED"


def test_download_failure_manifest_defaults_error_code_when_missing(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-default-error-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    def fake_download(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "folder": "video-default-error-demo",
            "video": None,
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error_code": None,
            "error_stage": "primary_download",
            "fallback_status": "not_attempted",
            "hint": None,
            "warnings": ["primary download failed without a more specific classification"],
            "warning_details": [
                {
                    "code": "primary_download_failed",
                    "message": "primary download failed without a more specific classification",
                    "stage": "primary_download",
                }
            ],
            "fallback_context": None,
            "error": "download failed",
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    download_execution = manifest["execution"]["download"]
    assert download_execution["success"] is False
    assert download_execution["used_selenium_fallback"] is False
    assert download_execution["error_code"] == "DOWNLOAD_FAILED"
    assert download_execution["fallback_status"] == "not_attempted"
    assert download_execution["warning_details"][0]["code"] == "primary_download_failed"
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "DOWNLOAD_FAILED"


def test_download_subs_command_records_subtitle_only_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-subs-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump({"output_dir": str(output_root)}, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def fake_download(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        (job_dir / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-subs-demo",
            "video": None,
            "audio": None,
            "subtitle": "video-subs-demo/subtitle.srt",
            "subtitle_vtt": None,
            "subtitle_srt": "video-subs-demo/subtitle.srt",
            "info": None,
            "media_duration_seconds": 42.0,
            "media_duration_human": "0:42",
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "started_at": "2026-04-16T10:00:00Z",
            "started_at_local": "2026-04-16T18:00:00+08:00",
            "finished_at": "2026-04-16T10:00:03Z",
            "finished_at_local": "2026-04-16T18:00:03+08:00",
            "elapsed_seconds": 3.0,
            "error_code": None,
            "error_stage": None,
            "fallback_status": "not_attempted",
            "hint": None,
            "warnings": [],
            "warning_details": [],
            "fallback_context": None,
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(
        app,
        ["download-subs", "https://example.com/video", "--config", str(config_path)],
    )

    assert result.exit_code == 0, result.stdout
    assert captured["subtitle_only"] is True
    assert captured["languages"] == ["all"]
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp download-subs"
    assert manifest["media"]["duration_seconds"] == 42.0
    assert manifest["media"]["duration_human"] == "0:42"
    assert manifest["artifacts"]["subtitle_srt"] == "video-subs-demo/subtitle.srt"
    assert manifest["config_effective"]["download"]["subtitle_only"] is True
    assert manifest["execution"]["download"]["started_at_local"] == "2026-04-16T18:00:00+08:00"
    assert manifest["execution"]["download"]["finished_at_local"] == "2026-04-16T18:00:03+08:00"
    assert manifest["execution"]["download"]["elapsed_seconds"] == 3.0
    assert "subtitle download completed" in result.stdout
