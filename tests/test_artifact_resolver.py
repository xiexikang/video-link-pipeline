"""Tests for artifact path resolution."""

from __future__ import annotations

import json
from pathlib import Path

from web.api.services.artifact_resolver import resolve_artifact_file
from web.api.services.job_scanner import job_id_from_dir


def _setup_job(tmp_path: Path) -> tuple[Path, str]:
    output_root = tmp_path / "output"
    job_dir = output_root / "demo-job"
    job_dir.mkdir(parents=True)
    transcript = job_dir / "transcript.txt"
    transcript.write_text("hello transcript", encoding="utf-8")
    manifest = {
        "artifacts": {
            "folder": "demo-job",
            "transcript_txt": "transcript.txt",
        }
    }
    (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    job_id = job_id_from_dir("demo-job")
    return output_root, job_id


def test_resolve_artifact_file(tmp_path: Path) -> None:
    output_root, job_id = _setup_job(tmp_path)
    resolved = resolve_artifact_file(output_root, job_id, "transcript_txt")
    assert resolved is not None
    file_path, kind = resolved
    assert file_path.name == "transcript.txt"
    assert kind == "text"
    assert file_path.read_text(encoding="utf-8") == "hello transcript"


def test_resolve_artifact_file_supports_output_relative_manifest_paths(tmp_path: Path) -> None:
    output_root, job_id = _setup_job(tmp_path)
    manifest_path = output_root / "demo-job" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["transcript_txt"] = "demo-job/transcript.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    resolved = resolve_artifact_file(output_root, job_id, "transcript_txt")

    assert resolved is not None
    file_path, kind = resolved
    assert file_path.name == "transcript.txt"
    assert kind == "text"
    assert file_path.read_text(encoding="utf-8") == "hello transcript"


def test_resolve_artifact_rejects_path_traversal(tmp_path: Path) -> None:
    output_root, job_id = _setup_job(tmp_path)
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")
    manifest_path = output_root / "demo-job" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["transcript_txt"] = "../../secret.txt"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert resolve_artifact_file(output_root, job_id, "transcript_txt") is None
