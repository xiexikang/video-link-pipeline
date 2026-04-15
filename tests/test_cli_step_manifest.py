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
        }

    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(input_video), "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp transcribe"
    assert manifest["input"]["input_path"] == str(input_video)
    assert manifest["artifacts"]["transcript_txt"] == "transcribe-demo/transcript.txt"
    assert manifest["execution"]["transcribe"]["success"] is False
    assert manifest["execution"]["transcribe"]["engine"] == "faster"
    assert manifest["execution"]["transcribe"]["error_code"] == "TRANSCRIBE_FAILED"
    assert manifest["execution"]["transcribe"]["error"] == "ffmpeg decode failed"
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
        }

    monkeypatch.setattr("video_link_pipeline.cli.transcribe_path", fake_transcribe)

    result = runner.invoke(app, ["transcribe", str(input_video), "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp transcribe"
    assert manifest["input"]["input_path"] == str(input_video)
    assert manifest["artifacts"]["transcript_txt"] == "transcribe-success-demo/transcript.txt"
    assert manifest["artifacts"]["subtitle_srt"] == "transcribe-success-demo/subtitle_whisper.srt"
    assert manifest["artifacts"]["subtitle_vtt"] == "transcribe-success-demo/subtitle_whisper.vtt"
    assert manifest["artifacts"]["transcript_json"] == "transcribe-success-demo/transcript.json"
    assert manifest["execution"]["transcribe"]["success"] is True
    assert manifest["execution"]["transcribe"]["detected_language"] == "en"
    assert manifest["execution"]["transcribe"]["engine"] == "faster"
    assert manifest["execution"]["transcribe"]["error_code"] is None
    assert manifest["execution"]["transcribe"]["error"] is None


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
        }

    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["summarize", str(transcript), "--config", str(config_path)])

    assert result.exit_code != 0
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp summarize"
    assert manifest["input"]["input_path"] == str(transcript)
    assert manifest["artifacts"]["summary_md"] == "summary-demo/summary.md"
    assert manifest["execution"]["summarize"]["success"] is False
    assert manifest["execution"]["summarize"]["provider"] == "claude"
    assert manifest["execution"]["summarize"]["error_code"] == "SUMMARY_FAILED"
    assert manifest["execution"]["summarize"]["error"] == "provider rate limited"
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
        }

    monkeypatch.setattr("video_link_pipeline.cli.summarize_transcript", fake_summarize)

    result = runner.invoke(app, ["summarize", str(transcript), "--config", str(config_path)])

    assert result.exit_code == 0, result.stdout
    manifest = json.loads((job_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["command"] == "vlp summarize"
    assert manifest["input"]["input_path"] == str(transcript)
    assert manifest["artifacts"]["summary_md"] == "summary-success-demo/summary.md"
    assert manifest["artifacts"]["keywords_json"] == "summary-success-demo/keywords.json"
    assert manifest["execution"]["summarize"]["success"] is True
    assert manifest["execution"]["summarize"]["provider"] == "claude"
    assert manifest["execution"]["summarize"]["error_code"] is None
    assert manifest["execution"]["summarize"]["error"] is None
