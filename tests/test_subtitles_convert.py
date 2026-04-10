from __future__ import annotations

from pathlib import Path

from video_link_pipeline.subtitles.convert import (
    batch_convert_subtitles,
    convert_subtitle_file,
    detect_subtitle_format,
)


def test_detect_subtitle_format_handles_utf8_bom() -> None:
    content = "\ufeffWEBVTT\n\n00:00:00.000 --> 00:00:01.000\nhello"
    assert detect_subtitle_format(content) == "vtt"


def test_convert_subtitle_file_vtt_to_srt(tmp_path: Path) -> None:
    input_file = tmp_path / "sample.vtt"
    input_file.write_text(
        "\ufeffWEBVTT\n\n00:00:00.000 --> 00:00:01.500\n<v Speaker>你好，世界\n",
        encoding="utf-8",
    )

    result = convert_subtitle_file(input_file, output_format="srt")

    assert result["success"] is True
    assert result["input_format"] == "vtt"
    assert result["output_format"] == "srt"
    assert result["changed"] is True

    output_file = Path(str(result["output_path"]))
    assert output_file.exists()
    output_text = output_file.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:01,500" in output_text
    assert "你好，世界" in output_text
    assert "<v Speaker>" not in output_text


def test_batch_convert_subtitles_srt_to_vtt(tmp_path: Path) -> None:
    subs_dir = tmp_path / "subs"
    subs_dir.mkdir()
    (subs_dir / "a.srt").write_text(
        "1\n00:00:00,000 --> 00:00:02,000\nhello world\n",
        encoding="utf-8",
    )
    (subs_dir / "b.srt").write_text(
        "1\n00:00:03,000 --> 00:00:05,000\nanother line\n",
        encoding="utf-8",
    )

    result = batch_convert_subtitles(subs_dir, output_format="vtt")

    assert result["success"] is True
    assert result["matched_files"] == 2
    assert result["converted_files"] == 2
    assert (subs_dir / "a.vtt").exists()
    assert (subs_dir / "b.vtt").exists()
    assert (subs_dir / "a.vtt").read_text(encoding="utf-8").startswith("WEBVTT")
