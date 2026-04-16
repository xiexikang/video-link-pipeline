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
    assert "created_at_local" in payload
    assert "updated_at_local" in payload
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
    assert "created_at_local" in payload
    assert "updated_at_local" in payload
    assert payload["artifacts"]["report"] == "doctor.txt"
    assert "stale" not in payload
    assert list(tmp_path.glob(".manifest.*.tmp")) == []


def test_upsert_manifest_preserves_nested_download_execution_fields_on_finalize(tmp_path: Path) -> None:
    manifest_path = tmp_path / "job" / "manifest.json"

    upsert_manifest(
        manifest_path,
        command="vlp download",
        input_data={"url": "https://example.com/video", "input_path": None},
        artifacts={"folder": "job", "video": "job/video.mp4"},
        execution={
            "download": {
                "success": True,
                "used_selenium_fallback": True,
                "fallback_status": "succeeded",
                "fallback_context": {
                    "media_hint_url": "https://cdn.example.com/media.m3u8",
                    "extraction_source": "jsonld:contentUrl",
                },
                "warning_details": [
                    {
                        "code": "primary_http_403",
                        "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
                        "stage": "primary_download",
                    }
                ],
            }
        },
    )

    upsert_manifest(
        manifest_path,
        command="vlp run",
        config_effective={"output_dir": "./output"},
    )

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["command"] == "vlp run"
    assert payload["config_effective"]["output_dir"] == "./output"
    assert payload["artifacts"]["video"] == "job/video.mp4"
    assert payload["execution"]["download"]["success"] is True
    assert payload["execution"]["download"]["used_selenium_fallback"] is True
    assert payload["execution"]["download"]["fallback_status"] == "succeeded"
    assert payload["execution"]["download"]["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert payload["execution"]["download"]["warning_details"][0]["code"] == "primary_http_403"
