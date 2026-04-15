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
                "summary": {"enabled": False},
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


def test_run_command_do_summary_also_generates_transcript(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-123-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-123-demo",
            "video": "video-123-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error": None,
        }

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
        }

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
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)
    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["run", "https://example.com/video", "--do-summary", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp run"
    assert manifest["input"]["url"] == "https://example.com/video"
    assert manifest["execution"]["download"]["success"] is True
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["summarize"]["success"] is True
    assert manifest["artifacts"]["folder"] == "video-123-demo"
    assert manifest["artifacts"]["transcript_txt"] == "video-123-demo/transcript.txt"
    assert manifest["artifacts"]["summary_md"] == "video-123-demo/summary.md"


def test_run_command_missing_subtitles_triggers_transcribe(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-456-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)
    calls = {"transcribe": 0}

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-456-demo",
            "video": "video-456-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": True,
            "used_selenium_fallback": False,
            "error": None,
        }

    def fake_transcribe(**_: object) -> dict[str, object]:
        calls["transcribe"] += 1
        transcript = job_dir / "transcript.txt"
        srt_file = job_dir / "subtitle_whisper.srt"
        vtt_file = job_dir / "subtitle_whisper.vtt"
        json_file = job_dir / "transcript.json"
        transcript.write_text("hello world", encoding="utf-8")
        srt_file.write_text("", encoding="utf-8")
        vtt_file.write_text("WEBVTT\n", encoding="utf-8")
        json_file.write_text("{}", encoding="utf-8")
        return {
            "success": True,
            "transcript_file": str(transcript),
            "srt_file": str(srt_file),
            "vtt_file": str(vtt_file),
            "json_file": str(json_file),
            "detected_language": "zh",
            "engine": "faster",
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert calls["transcribe"] == 1
    assert manifest["command"] == "vlp run"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["artifacts"]["transcript_txt"] == "video-456-demo/transcript.txt"


def test_run_command_download_only_preserves_download_diagnostics(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-777-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        (job_dir / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-777-demo",
            "video": "video-777-demo/video.mp4",
            "audio": None,
            "subtitle": "video-777-demo/subtitle.srt",
            "subtitle_vtt": None,
            "subtitle_srt": "video-777-demo/subtitle.srt",
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "fallback_status": "succeeded",
            "fallback_context": {
                "resolved_url": "https://example.com/resolved",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://cdn.example.com/media.m3u8",
                "site_name": "example.com",
                "extraction_source": "jsonld:contentUrl",
            },
            "error_code": None,
            "error_stage": None,
            "hint": None,
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
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp run"
    assert manifest["input"]["url"] == "https://example.com/video"
    assert manifest["artifacts"]["folder"] == "video-777-demo"
    assert manifest["artifacts"]["video"] == "video-777-demo/video.mp4"
    assert manifest["artifacts"]["subtitle_srt"] == "video-777-demo/subtitle.srt"

    download_execution = manifest["execution"]["download"]
    assert download_execution["success"] is True
    assert download_execution["used_selenium_fallback"] is True
    assert download_execution["fallback_status"] == "succeeded"
    assert download_execution["warning_details"][0]["code"] == "primary_http_403"
    assert download_execution["warning_details"][1]["code"] == "fallback_context_prepared"
    assert download_execution["fallback_context"]["extraction_source"] == "jsonld:contentUrl"
    assert download_execution["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert "transcribe" not in manifest["execution"]
    assert "summarize" not in manifest["execution"]
