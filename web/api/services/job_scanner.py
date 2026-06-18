"""Scan output directories for pipeline jobs."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from video_link_pipeline.manifest import load_manifest

from .stage_parser import derive_runtime_status, parse_all_stages

JOB_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def job_id_from_dir(job_dir: str) -> str:
    """Return a stable UUID for a job directory path."""
    return str(uuid.uuid5(JOB_NAMESPACE, job_dir.replace("\\", "/")))


def _job_title(job_dir: Path, manifest_data: dict[str, Any]) -> str:
    media = manifest_data.get("media")
    if isinstance(media, dict):
        for key in ("title", "name", "id"):
            value = media.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return job_dir.name


def _relative_job_dir(job_dir: Path, output_root: Path) -> str:
    try:
        return job_dir.resolve().relative_to(output_root.resolve()).as_posix()
    except ValueError:
        return job_dir.resolve().as_posix()


def scan_jobs(output_root: Path) -> list[dict[str, Any]]:
    """Discover jobs by finding manifest.json files under output_root."""
    if not output_root.exists():
        return []

    output_root = output_root.resolve()
    jobs: list[dict[str, Any]] = []

    for manifest_path in output_root.rglob("manifest.json"):
        job_dir = manifest_path.parent
        try:
            manifest = load_manifest(manifest_path)
        except Exception:
            continue

        data = manifest.data
        relative_dir = _relative_job_dir(job_dir, output_root)
        job_id = job_id_from_dir(relative_dir)
        execution = data.get("execution") if isinstance(data.get("execution"), dict) else {}
        stages = parse_all_stages(execution)
        runtime_status = derive_runtime_status(stages)

        input_data = data.get("input") if isinstance(data.get("input"), dict) else {}
        source_url = input_data.get("url") if isinstance(input_data.get("url"), str) else None
        source_path = (
            input_data.get("input_path") if isinstance(input_data.get("input_path"), str) else None
        )

        jobs.append(
            {
                "id": job_id,
                "job_dir": relative_dir,
                "title": _job_title(job_dir, data),
                "source_url": source_url,
                "source_path": source_path,
                "command": data.get("command") if isinstance(data.get("command"), str) else None,
                "updated_at": data.get("updated_at")
                if isinstance(data.get("updated_at"), str)
                else None,
                "stages": stages,
                "runtime_status": runtime_status,
                "_sort_key": data.get("updated_at") or data.get("created_at") or "",
            }
        )

    jobs.sort(key=lambda item: item["_sort_key"], reverse=True)
    for job in jobs:
        job.pop("_sort_key", None)
    return jobs


def find_job_by_id(output_root: Path, job_id: str) -> dict[str, Any] | None:
    """Locate a scanned job by its stable id."""
    for job in scan_jobs(output_root):
        if job["id"] == job_id:
            return job
    return None


def load_job_manifest(output_root: Path, job_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return (job summary, full manifest data) for a job id."""
    job = find_job_by_id(output_root, job_id)
    if job is None:
        return None

    manifest_path = output_root / job["job_dir"] / "manifest.json"
    manifest = load_manifest(manifest_path)
    execution = manifest.data.get("execution")
    stages = parse_all_stages(execution if isinstance(execution, dict) else {})
    runtime_status = derive_runtime_status(stages)
    return {**job, "stages": stages, "runtime_status": runtime_status}, manifest.data
