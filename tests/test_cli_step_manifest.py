from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from video_link_pipeline.cli import app

runner = CliRunner()


def _write_config(config_path: Path, output_dir: Path) -> None:
    config_path.write_text(
        yaml.safe_dump(
            {
                "output_dir": str(output_dir),
                "summary": {"enabled": True, "provider": "claude"},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_transcribe_failure_still_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "transcribe-demo"
    job_dir.mkdir(parents=True)
    input_video = job_dir / "video.mp4"
    input_video.write_text("video", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_transcribe(**_: object) -> dict[str, object]:
        transcript = job_dir / "transcript.txt"
        transcript.write_text("partial transcript", encoding="utf-8")
        return {
            "success": False,
            "transcript_file": str(transcript),
            "srt_file": None,
            "vtt_file": None,
            "json_file": None,
            "detected_language": None,
            "engine": "faster",
            "error": "ffmpeg decode failed",
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:04Z",
            "elapsed_ms": 4000,
        }

    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(input_video), "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp transcribe"
    assert manifest["input"]["input_path"] == str(input_video)
    assert manifest["artifacts"]["transcript_txt"] == "transcript.txt"
    assert manifest["execution"]["transcribe"]["success"] is False
    assert manifest["execution"]["transcribe"]["engine"] == "faster"
    assert manifest["execution"]["transcribe"]["error_code"] == "TRANSCRIBE_FAILED"
    assert manifest["execution"]["transcribe"]["error"] == "ffmpeg decode failed"
    assert manifest["execution"]["transcribe"]["started_at"] == "2026-04-16T10:00:00Z"
    assert manifest["execution"]["transcribe"]["finished_at"] == "2026-04-16T10:00:04Z"
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 4000
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "TRANSCRIBE_FAILED"
    assert str(result.exception) == "ffmpeg decode failed"


def test_transcribe_success_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "transcribe-success-demo"
    job_dir.mkdir(parents=True)
    input_video = job_dir / "video.mp4"
    input_video.write_text("video", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_transcribe(**_: object) -> dict[str, object]:
        transcript = job_dir / "transcript.txt"
        srt_file = job_dir / "subtitle_whisper.srt"
        vtt_file = job_dir / "subtitle_whisper.vtt"
        json_file = job_dir / "transcript.json"
        transcript.write_text("hello world", encoding="utf-8")
        srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nhello world\n", encoding="utf-8")
        vtt_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello world\n", encoding="utf-8")
        json_file.write_text("{}", encoding="utf-8")
        return {
            "success": True,
            "transcript_file": str(transcript),
            "srt_file": str(srt_file),
            "vtt_file": str(vtt_file),
            "json_file": str(json_file),
            "detected_language": "en",
            "engine": "faster",
            "error": None,
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:03Z",
            "elapsed_ms": 3000,
        }

    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(input_video), "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp transcribe"
    assert manifest["input"]["input_path"] == str(input_video)
    assert manifest["artifacts"]["transcript_txt"] == "transcript.txt"
    assert manifest["artifacts"]["subtitle_srt"] == "subtitle_whisper.srt"
    assert manifest["artifacts"]["subtitle_vtt"] == "subtitle_whisper.vtt"
    assert manifest["artifacts"]["transcript_json"] == "transcript.json"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["detected_language"] == "en"
    assert manifest["execution"]["transcribe"]["engine"] == "faster"
    assert manifest["execution"]["transcribe"]["error_code"] is None
    assert manifest["execution"]["transcribe"]["error"] is None
    assert manifest["execution"]["transcribe"]["started_at"] == "2026-04-16T10:00:00Z"
    assert manifest["execution"]["transcribe"]["finished_at"] == "2026-04-16T10:00:03Z"
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 3000


def test_summarize_failure_still_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "summary-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    transcript.write_text("hello world", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_summarize(**_: object) -> dict[str, object]:
        summary = job_dir / "summary.md"
        summary.write_text("# partial", encoding="utf-8")
        return {
            "success": False,
            "provider": "claude",
            "summary_file": str(summary),
            "keywords_file": None,
            "one_sentence_summary": None,
            "error": "provider rate limited",
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:02Z",
            "elapsed_ms": 2000,
        }

    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["summarize", str(transcript), "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp summarize"
    assert manifest["input"]["input_path"] == str(transcript)
    assert manifest["artifacts"]["summary_md"] == "summary.md"
    assert manifest["execution"]["summarize"]["success"] is False
    assert manifest["execution"]["summarize"]["provider"] == "claude"
    assert manifest["execution"]["summarize"]["error_code"] == "SUMMARY_FAILED"
    assert manifest["execution"]["summarize"]["error"] == "provider rate limited"
    assert manifest["execution"]["summarize"]["started_at"] == "2026-04-16T10:00:00Z"
    assert manifest["execution"]["summarize"]["finished_at"] == "2026-04-16T10:00:02Z"
    assert manifest["execution"]["summarize"]["elapsed_ms"] == 2000
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "SUMMARY_FAILED"
    assert str(result.exception) == "provider rate limited"


def test_summarize_success_writes_manifest(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "summary-success-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    transcript.write_text("hello world", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_summarize(**_: object) -> dict[str, object]:
        summary = job_dir / "summary.md"
        keywords = job_dir / "keywords.json"
        summary.write_text("# Summary", encoding="utf-8")
        keywords.write_text("{}", encoding="utf-8")
        return {
            "success": True,
            "provider": "claude",
            "summary_file": str(summary),
            "keywords_file": str(keywords),
            "one_sentence_summary": "A short summary.",
            "error": None,
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:01Z",
            "elapsed_ms": 1000,
        }

    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["summarize", str(transcript), "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp summarize"
    assert manifest["input"]["input_path"] == str(transcript)
    assert manifest["artifacts"]["summary_md"] == "summary.md"
    assert manifest["artifacts"]["keywords_json"] == "keywords.json"
    assert manifest["execution"]["summarize"]["success"] is True
    assert manifest["execution"]["summarize"]["provider"] == "claude"
    assert manifest["execution"]["summarize"]["error_code"] is None
    assert manifest["execution"]["summarize"]["error"] is None
    assert manifest["execution"]["summarize"]["started_at"] == "2026-04-16T10:00:00Z"
    assert manifest["execution"]["summarize"]["finished_at"] == "2026-04-16T10:00:01Z"
    assert manifest["execution"]["summarize"]["elapsed_ms"] == 1000


def test_download_failure_still_writes_manifest_with_diagnostics(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "download-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        return {
            "success": False,
            "folder": "download-demo",
            "video": None,
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "fallback_status": "retry_failed",
            "fallback_context": {
                "resolved_url": "https://example.com/watch/demo",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://example.com/watch/demo",
                "site_name": "example.com",
                "extraction_source": "window.__DATA__:playAddr",
                "extraction_kind": "window_state",
            },
            "error_code": "DOWNLOAD_FALLBACK_RETRY_FAILED",
            "error_stage": "fallback_retry",
            "error": "retry download failed",
            "hint": "structured cues still did not expose a direct media URL",
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via window.__DATA__:playAddr (kind=window_state)",
                "selenium fallback did not extract an explicit media URL (kind=window_state) and will retry with the resolved page URL",
            ],
            "warning_details": [
                {
                    "code": "primary_http_403",
                    "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                    "stage": "primary_download",
                },
                {
                    "code": "fallback_context_prepared",
                    "message": "selenium fallback context prepared via window.__DATA__:playAddr (kind=window_state)",
                    "stage": "fallback_prepare",
                },
                {
                    "code": "fallback_media_hint_missing_structured",
                    "message": "selenium fallback did not extract an explicit media URL (kind=window_state) and will retry with the resolved page URL",
                    "stage": "fallback_prepare",
                },
            ],
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["download", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp download"
    assert manifest["input"]["url"] == "https://example.com/video"
    download_execution = manifest["execution"]["download"]
    assert download_execution["success"] is False
    assert download_execution["fallback_status"] == "retry_failed"
    assert download_execution["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert download_execution["error"] == "retry download failed"
    assert download_execution["hint"] == "structured cues still did not expose a direct media URL"
    assert download_execution["fallback_context"]["extraction_source"] == "window.__DATA__:playAddr"
    assert download_execution["fallback_context"]["extraction_kind"] == "window_state"
    codes = [item["code"] for item in download_execution["warning_details"]]
    assert "primary_http_403" in codes
    assert "fallback_context_prepared" in codes
    assert "fallback_media_hint_missing_structured" in codes
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert str(result.exception) == "retry download failed"
