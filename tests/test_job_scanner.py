"""Tests for web job scanner."""

from __future__ import annotations

import json
from pathlib import Path

from web.api.services.job_scanner import find_job_by_id, job_id_from_dir, scan_jobs
from web.api.services.stage_parser import derive_runtime_status, parse_all_stages


def _write_manifest(job_dir: Path, payload: dict) -> None:
    job_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = job_dir / "manifest.json"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_scan_jobs_discovers_manifests(tmp_path: Path) -> None:
    _write_manifest(
        tmp_path / "demo-job",
        {
            "schema_version": "1.0",
            "created_at": "2026-06-10T10:00:00Z",
            "updated_at": "2026-06-10T12:00:00Z",
            "command": "vlp run",
            "input": {"url": "https://example.com/video", "input_path": None},
            "execution": {
                "download": {"success": True},
                "transcribe": {"success": True, "reused_existing": False},
                "summarize": {"success": None},
            },
        },
    )

    jobs = scan_jobs(tmp_path)
    assert len(jobs) == 1
    assert jobs[0]["title"] == "demo-job"
    assert jobs[0]["source_url"] == "https://example.com/video"
    assert jobs[0]["runtime_status"] == "succeeded"


def test_find_job_by_id_is_stable(tmp_path: Path) -> None:
    job_dir = tmp_path / "nested" / "bv-demo"
    _write_manifest(
        job_dir,
        {
            "updated_at": "2026-06-10T12:00:00Z",
            "input": {"url": None, "input_path": None},
            "execution": {"download": {"success": False, "error_code": "primary_http_403"}},
        },
    )

    relative = "nested/bv-demo"
    job_id = job_id_from_dir(relative)
    found = find_job_by_id(tmp_path, job_id)
    assert found is not None
    assert found["job_dir"] == relative
    assert found["runtime_status"] == "failed"


def test_parse_all_stages_handles_skipped_transcribe() -> None:
    stages = parse_all_stages(
        {
            "download": {"success": True},
            "transcribe": {"success": None, "reused_existing": True},
        }
    )
    assert stages["download"]["status"] == "done"
    assert stages["transcribe"]["status"] == "skipped"
    assert stages["summarize"]["status"] == "idle"
    assert derive_runtime_status(stages) == "succeeded"
