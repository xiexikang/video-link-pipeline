from __future__ import annotations

import json
from pathlib import Path

from video_link_pipeline.manifest import create_manifest, upsert_manifest, write_manifest


def test_upsert_manifest_merges_incremental_sections(tmp_path: Path) -> None:
    manifest_path = tmp_path / "job" / "manifest.json"

    upsert_manifest(
        manifest_path,
        command="vlp download",
        input_data={"url": "https://example.com/video", "input_path": None},
        artifacts={"video": "job/video.mp4"},
        execution={"download": {"success": True, "error": None}},
    )
    upsert_manifest(
        manifest_path,
        command="vlp transcribe",
        artifacts={"transcript_txt": "job/transcript.txt"},
        execution={"transcribe": {"success": True, "error": None}},
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["command"] == "vlp transcribe"
    assert payload["artifacts"]["video"] == "job/video.mp4"
    assert payload["artifacts"]["transcript_txt"] == "job/transcript.txt"
    assert payload["execution"]["download"]["success"] is True
    assert payload["execution"]["transcribe"]["success"] is True


def test_write_manifest_is_atomic_and_replaces_existing_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"stale": true}\n', encoding="utf-8")

    manifest = create_manifest(
        manifest_path,
        command="vlp doctor",
        input_data={"url": None, "input_path": None},
    )
    manifest.data["artifacts"] = {"report": "doctor.txt"}

    written_path = write_manifest(manifest)

    assert written_path == manifest_path
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["command"] == "vlp doctor"
    assert payload["artifacts"]["report"] == "doctor.txt"
    assert "stale" not in payload
    assert list(tmp_path.glob(".manifest.*.tmp")) == []
