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
