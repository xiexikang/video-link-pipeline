"""Unified job query helpers merging disk scan and runtime registry."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from video_link_pipeline.manifest import load_manifest

from .job_registry import RegistryEntry, get_registry
from .job_scanner import find_job_by_id, scan_jobs
from .stage_parser import derive_runtime_status, parse_all_stages


def _registry_stages(entry: RegistryEntry) -> dict[str, dict[str, Any]]:
    idle = {"status": "idle", "success": None}
    stages = {
        "download": dict(idle),
        "transcribe": dict(idle),
        "summarize": dict(idle),
    }
    if entry.status == "failed":
        failed_stage = {
            "status": "failed",
            "success": False,
            "error_code": entry.error_code,
            "hint": entry.hint,
        }
        if entry.job_type in {"download", "download-subs", "run"}:
            stages["download"] = failed_stage
        elif entry.job_type == "transcribe":
            stages["transcribe"] = failed_stage
        elif entry.job_type == "summarize":
            stages["summarize"] = failed_stage
    return stages


def _registry_list_item(entry: RegistryEntry) -> dict[str, Any]:
    title = entry.job_dir.split("/")[-1] if entry.job_dir else f"Web job ({entry.job_type})"
    return {
        "id": entry.id,
        "job_dir": entry.job_dir or "",
        "title": title,
        "source_url": entry.source_url,
        "source_path": entry.source_path,
        "command": f"vlp {entry.job_type}",
        "updated_at": entry.updated_at,
        "stages": _registry_stages(entry),
        "runtime_status": entry.status,
        "_sort_key": entry.updated_at,
    }


def _synthetic_manifest(entry: RegistryEntry) -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "command": f"vlp {entry.job_type}",
        "input": {"url": entry.source_url, "input_path": entry.source_path},
        "artifacts": {},
        "execution": {},
        "config_effective": {},
    }
    if entry.status == "failed" and entry.error:
        stage_key = {
            "download": "download",
            "download-subs": "download",
            "run": "download",
            "transcribe": "transcribe",
            "summarize": "summarize",
        }.get(entry.job_type, "download")
        manifest["execution"] = {
            stage_key: {
                "success": False,
                "error": entry.error,
                "error_code": entry.error_code,
                "hint": entry.hint,
            }
        }
    return manifest


def _merge_runtime_status(registry_status: str, manifest_status: str) -> str:
    if registry_status in {"queued", "running"}:
        return registry_status
    if registry_status == "failed":
        return "failed"
    if registry_status == "succeeded":
        return manifest_status if manifest_status != "idle" else "succeeded"
    return manifest_status


def list_jobs(output_root: Path) -> list[dict[str, Any]]:
    registry = get_registry()
    scanned = scan_jobs(output_root)
    by_dir = {job["job_dir"]: job for job in scanned if job.get("job_dir")}
    merged: dict[str, dict[str, Any]] = {}
    sort_keys: dict[str, str] = {}

    for entry in registry.list_entries():
        if entry.job_dir and entry.job_dir in by_dir:
            job = dict(by_dir[entry.job_dir])
            job["id"] = entry.id
            job["runtime_status"] = _merge_runtime_status(entry.status, job["runtime_status"])
            merged[entry.id] = job
            sort_keys[entry.id] = job.get("updated_at") or entry.updated_at
        elif entry.status in {"queued", "running"} or not entry.job_dir:
            item = _registry_list_item(entry)
            merged[entry.id] = item
            sort_keys[entry.id] = entry.updated_at

    for job in scanned:
        registry_entry = registry.entry_by_job_dir(job["job_dir"])
        if registry_entry and registry_entry.id in merged:
            continue
        merged[job["id"]] = job
        sort_keys[job["id"]] = job.get("updated_at") or ""

    result = list(merged.values())
    result.sort(key=lambda item: sort_keys.get(item["id"], ""), reverse=True)
    return result


def get_job_summary(output_root: Path, job_id: str) -> dict[str, Any] | None:
    registry = get_registry()
    entry = registry.get(job_id)

    if entry and entry.job_dir:
        scanned = find_job_by_id(output_root, job_id)
        if scanned is None:
            scanned = next(
                (job for job in scan_jobs(output_root) if job["job_dir"] == entry.job_dir),
                None,
            )
        if scanned:
            job = dict(scanned)
            job["id"] = entry.id
            job["runtime_status"] = _merge_runtime_status(entry.status, job["runtime_status"])
            return job

    if entry:
        return _registry_list_item(entry)

    return find_job_by_id(output_root, job_id)


def load_job_detail(output_root: Path, job_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    summary = get_job_summary(output_root, job_id)
    if summary is None:
        return None

    registry = get_registry()
    entry = registry.get(job_id)
    if not summary.get("job_dir"):
        if entry:
            return summary, _synthetic_manifest(entry)
        return None

    manifest_path = output_root / summary["job_dir"] / "manifest.json"
    if not manifest_path.exists():
        if entry:
            return summary, _synthetic_manifest(entry)
        return None

    manifest = load_manifest(manifest_path)
    execution = manifest.data.get("execution")
    stages = parse_all_stages(execution if isinstance(execution, dict) else {})
    runtime_status = derive_runtime_status(
        stages,
        memory_status=entry.status if entry else None,
    )
    return {**summary, "stages": stages, "runtime_status": runtime_status}, manifest.data


def get_job_status(output_root: Path, job_id: str) -> dict[str, Any] | None:
    loaded = load_job_detail(output_root, job_id)
    if loaded is None:
        registry = get_registry()
        entry = registry.get(job_id)
        if entry is None:
            return None
        return {
            "id": entry.id,
            "runtime_status": entry.status,
            "job_dir": entry.job_dir,
            "error": entry.error,
            "error_code": entry.error_code,
            "hint": entry.hint,
            "log": entry.log or None,
            "stages": {
                "download": {"status": "idle", "success": None},
                "transcribe": {"status": "idle", "success": None},
                "summarize": {"status": "idle", "success": None},
            },
        }

    summary, _manifest = loaded
    registry = get_registry()
    entry = registry.get(job_id)
    return {
        "id": summary["id"],
        "runtime_status": summary["runtime_status"],
        "job_dir": summary.get("job_dir"),
        "error": entry.error if entry else None,
        "error_code": entry.error_code if entry else None,
        "hint": entry.hint if entry else None,
        "log": entry.log if entry and entry.log else None,
        "stages": summary.get("stages", {}),
    }
