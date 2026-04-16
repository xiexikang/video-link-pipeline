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
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:03Z",
            "elapsed_ms": 3000,
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
            "started_at": "2026-04-16T10:00:03Z",
            "finished_at": "2026-04-16T10:00:04Z",
            "elapsed_ms": 1000,
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
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 3000
    assert manifest["execution"]["summarize"]["elapsed_ms"] == 1000
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
            "started_at": "2026-04-16T10:00:00Z",
            "finished_at": "2026-04-16T10:00:02Z",
            "elapsed_ms": 2000,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert calls["transcribe"] == 1
    assert manifest["command"] == "vlp run"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 2000
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
                "extraction_kind": "jsonld",
            },
            "error_code": None,
            "error_stage": None,
            "hint": None,
            "warnings": [
                "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                "selenium fallback context prepared via jsonld:contentUrl (kind=jsonld)",
            ],
            "warning_details": [
                {
                    "code": "primary_http_403",
                    "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                    "stage": "primary_download",
                },
                {
                    "code": "fallback_context_prepared",
                    "message": "selenium fallback context prepared via jsonld:contentUrl (kind=jsonld)",
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
    assert download_execution["fallback_context"]["extraction_kind"] == "jsonld"
    assert download_execution["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert "transcribe" not in manifest["execution"]
    assert "summarize" not in manifest["execution"]


def test_run_command_download_only_renders_extraction_kind_and_missing_hint_code(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-cli-diagnostics-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-cli-diagnostics-demo",
            "video": "video-cli-diagnostics-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": True,
            "fallback_status": "succeeded",
            "fallback_context": {
                "resolved_url": "https://example.com/watch/demo",
                "canonical_url": "https://example.com/watch/demo",
                "media_hint_url": "https://example.com/watch/demo",
                "site_name": "example.com",
                "extraction_source": "window.__DATA__:playAddr",
                "extraction_kind": "window_state",
            },
            "error_code": None,
            "error_stage": None,
            "hint": None,
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
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    download_execution = manifest["execution"]["download"]
    assert download_execution["fallback_context"]["extraction_kind"] == "window_state"
    codes = [item["code"] for item in download_execution["warning_details"]]
    assert "fallback_media_hint_missing_structured" in codes
    assert "download fallback_context.extraction_kind=window_state" in result.stdout
    assert "download warning_code=fallback_media_hint_missing_structured stage=fallback_prepare" in result.stdout


def test_run_command_transcribe_failure_preserves_download_and_failure_state(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-888-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-888-demo",
            "video": "video-888-demo/video.mp4",
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
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp transcribe"
    assert manifest["input"]["input_path"] == str(job_dir)
    assert manifest["artifacts"]["folder"] == "video-888-demo"
    assert manifest["artifacts"]["video"] == "video-888-demo/video.mp4"
    assert manifest["artifacts"]["transcript_txt"] == "video-888-demo/transcript.txt"
    assert manifest["execution"]["download"]["success"] is True
    assert manifest["execution"]["transcribe"]["success"] is False
    assert manifest["execution"]["transcribe"]["engine"] == "faster"
    assert manifest["execution"]["transcribe"]["error_code"] == "TRANSCRIBE_FAILED"
    assert manifest["execution"]["transcribe"]["error"] == "ffmpeg decode failed"
    assert "summarize" not in manifest["execution"]
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "TRANSCRIBE_FAILED"
    assert str(result.exception) == "ffmpeg decode failed"


def test_run_command_summary_failure_preserves_prior_success_state(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-999-summary-demo"
    job_dir.mkdir(parents=True)
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-999-summary-demo",
            "video": "video-999-summary-demo/video.mp4",
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
            "detected_language": "en",
            "engine": "faster",
            "error": None,
        }

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
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)
    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["run", "https://example.com/video", "--do-summary", "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp summarize"
    assert manifest["input"]["input_path"] == str(job_dir / "transcript.txt")
    assert manifest["artifacts"]["folder"] == "video-999-summary-demo"
    assert manifest["artifacts"]["video"] == "video-999-summary-demo/video.mp4"
    assert manifest["artifacts"]["transcript_txt"] == "video-999-summary-demo/transcript.txt"
    assert manifest["artifacts"]["summary_md"] == "video-999-summary-demo/summary.md"
    assert manifest["execution"]["download"]["success"] is True
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["summarize"]["success"] is False
    assert manifest["execution"]["summarize"]["provider"] == "claude"
    assert manifest["execution"]["summarize"]["error_code"] == "SUMMARY_FAILED"
    assert manifest["execution"]["summarize"]["error"] == "provider rate limited"
    assert result.exception is not None
    assert getattr(result.exception, "error_code", None) == "SUMMARY_FAILED"
    assert str(result.exception) == "provider rate limited"


def test_run_command_reuses_existing_transcript_and_records_manifest_state(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-reuse-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    transcript.write_text("existing transcript", encoding="utf-8")
    srt_file = job_dir / "subtitle_whisper.srt"
    vtt_file = job_dir / "subtitle_whisper.vtt"
    json_file = job_dir / "transcript.json"
    srt_file.write_text("", encoding="utf-8")
    vtt_file.write_text("WEBVTT\n", encoding="utf-8")
    json_file.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-reuse-demo",
            "video": "video-reuse-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error": None,
        }

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)

    result = runner.invoke(app, ["run", "https://example.com/video", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp run"
    assert manifest["artifacts"]["transcript_txt"] == "video-reuse-demo/transcript.txt"
    assert manifest["artifacts"]["subtitle_srt"] == "video-reuse-demo/subtitle_whisper.srt"
    assert manifest["artifacts"]["subtitle_vtt"] == "video-reuse-demo/subtitle_whisper.vtt"
    assert manifest["artifacts"]["transcript_json"] == "video-reuse-demo/transcript.json"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["reused_existing"] is True
    assert manifest["execution"]["transcribe"]["engine"] is None
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 0
    assert manifest["execution"]["transcribe"]["warnings"] == ["reused existing transcript"]
    assert "summarize" not in manifest["execution"]


def test_run_command_do_summary_reuses_existing_transcript_without_retranscribing(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-reuse-summary-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    transcript.write_text("existing transcript", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)
    calls = {"transcribe": 0}

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-reuse-summary-demo",
            "video": "video-reuse-summary-demo/video.mp4",
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
        calls["transcribe"] += 1
        raise AssertionError("transcribe should not be called when transcript.txt already exists")

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
    assert calls["transcribe"] == 0
    assert manifest["command"] == "vlp run"
    assert manifest["artifacts"]["transcript_txt"] == "video-reuse-summary-demo/transcript.txt"
    assert manifest["artifacts"]["summary_md"] == "video-reuse-summary-demo/summary.md"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["reused_existing"] is True
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 0
    assert manifest["execution"]["summarize"]["success"] is True


def test_run_command_do_summary_reuses_existing_summary_without_resummarizing(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-reuse-existing-summary-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    summary = job_dir / "summary.md"
    keywords = job_dir / "keywords.json"
    transcript.write_text("existing transcript", encoding="utf-8")
    summary.write_text("# Existing Summary", encoding="utf-8")
    keywords.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)
    calls = {"summarize": 0}

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-reuse-existing-summary-demo",
            "video": "video-reuse-existing-summary-demo/video.mp4",
            "audio": None,
            "subtitle": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info": None,
            "needs_whisper": False,
            "used_selenium_fallback": False,
            "error": None,
        }

    def fake_summarize(**_: object) -> dict[str, object]:
        calls["summarize"] += 1
        raise AssertionError("summarize should not be called when summary.md already exists")

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["run", "https://example.com/video", "--do-summary", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert calls["summarize"] == 0
    assert manifest["command"] == "vlp run"
    assert manifest["artifacts"]["transcript_txt"] == "video-reuse-existing-summary-demo/transcript.txt"
    assert manifest["artifacts"]["summary_md"] == "video-reuse-existing-summary-demo/summary.md"
    assert manifest["artifacts"]["keywords_json"] == "video-reuse-existing-summary-demo/keywords.json"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["reused_existing"] is True
    assert manifest["execution"]["summarize"]["success"] is True
    assert manifest["execution"]["summarize"]["reused_existing"] is True
    assert manifest["execution"]["summarize"]["elapsed_ms"] == 0
    assert manifest["execution"]["summarize"]["provider"] is None
    assert manifest["execution"]["summarize"]["warnings"] == ["reused existing summary"]


def test_run_command_do_summary_reuses_existing_transcript_and_summary(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-reuse-both-demo"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    summary = job_dir / "summary.md"
    keywords = job_dir / "keywords.json"
    transcript_json = job_dir / "transcript.json"
    transcript.write_text("existing transcript", encoding="utf-8")
    summary.write_text("# Existing Summary", encoding="utf-8")
    keywords.write_text("{}", encoding="utf-8")
    transcript_json.write_text("{}", encoding="utf-8")
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, output_root)
    calls = {"transcribe": 0, "summarize": 0}

    def fake_download(**_: object) -> dict[str, object]:
        (job_dir / "video.mp4").write_text("video", encoding="utf-8")
        return {
            "success": True,
            "folder": "video-reuse-both-demo",
            "video": "video-reuse-both-demo/video.mp4",
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
        calls["transcribe"] += 1
        raise AssertionError("transcribe should not be called when transcript.txt already exists")

    def fake_summarize(**_: object) -> dict[str, object]:
        calls["summarize"] += 1
        raise AssertionError("summarize should not be called when summary.md already exists")

    monkeypatch.setattr("video_link_pipeline.cli.execute_download", fake_download)
    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)
    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["run", "https://example.com/video", "--do-summary", "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert calls["transcribe"] == 0
    assert calls["summarize"] == 0
    assert manifest["command"] == "vlp run"
    assert manifest["artifacts"]["transcript_txt"] == "video-reuse-both-demo/transcript.txt"
    assert manifest["artifacts"]["transcript_json"] == "video-reuse-both-demo/transcript.json"
    assert manifest["artifacts"]["summary_md"] == "video-reuse-both-demo/summary.md"
    assert manifest["artifacts"]["keywords_json"] == "video-reuse-both-demo/keywords.json"
    assert manifest["execution"]["download"]["success"] is True
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["reused_existing"] is True
    assert manifest["execution"]["transcribe"]["elapsed_ms"] == 0
    assert manifest["execution"]["transcribe"]["warnings"] == ["reused existing transcript"]
    assert manifest["execution"]["summarize"]["success"] is True
    assert manifest["execution"]["summarize"]["reused_existing"] is True
    assert manifest["execution"]["summarize"]["elapsed_ms"] == 0
    assert manifest["execution"]["summarize"]["warnings"] == ["reused existing summary"]
