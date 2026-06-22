"""Safe artifact path resolution for job previews."""

from __future__ import annotations

from pathlib import Path

from video_link_pipeline.manifest import load_manifest

from .job_registry import get_registry
from .job_scanner import find_job_by_id, job_id_from_dir

TEXT_ARTIFACTS = {
    "transcript_txt",
    "summary_md",
    "subtitle_srt",
    "subtitle_vtt",
    "info_json",
}
JSON_ARTIFACTS = {"keywords_json", "transcript_json"}
MEDIA_ARTIFACTS = {"video", "audio"}


def resolve_job_dir(output_root: Path, job_id: str) -> tuple[str, Path] | None:
    """Resolve a job id to (relative_job_dir, absolute_job_dir)."""
    registry = get_registry()
    entry = registry.get(job_id)
    if entry and entry.job_dir:
        relative = entry.job_dir.replace("\\", "/")
        absolute = (output_root / relative).resolve()
        if absolute.exists():
            return relative, absolute

    scanned = find_job_by_id(output_root, job_id)
    if scanned:
        relative = scanned["job_dir"]
        absolute = (output_root / relative).resolve()
        if absolute.exists():
            return relative, absolute

    if entry and entry.job_dir:
        relative = entry.job_dir.replace("\\", "/")
        return relative, (output_root / relative).resolve()

    return None


def _safe_child_path(base_dir: Path, relative_path: str) -> Path | None:
    if not relative_path or relative_path.startswith(("/", "\\")):
        return None
    if ".." in Path(relative_path).parts:
        return None

    candidate = (base_dir / relative_path).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate


def resolve_artifact_file(
    output_root: Path,
    job_id: str,
    artifact_key: str,
) -> tuple[Path, str] | None:
    """Return (absolute_file_path, preview_kind) for an artifact key."""
    resolved = resolve_job_dir(output_root, job_id)
    if resolved is None:
        return None

    _relative_dir, job_dir = resolved
    manifest_path = job_dir / "manifest.json"
    if not manifest_path.exists():
        return None

    manifest = load_manifest(manifest_path)
    artifacts = manifest.data.get("artifacts")
    if not isinstance(artifacts, dict):
        return None

    raw_path = artifacts.get(artifact_key)
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None

    normalized_path = raw_path.replace("\\", "/")
    file_path = _safe_child_path(job_dir, normalized_path)
    if file_path is None or not file_path.exists() or not file_path.is_file():
        # Backward compatibility: some manifests store paths relative to output_root
        # instead of the current job directory.
        file_path = _safe_child_path(output_root, normalized_path)
    if file_path is None or not file_path.exists() or not file_path.is_file():
        absolute_candidate = Path(raw_path)
        if absolute_candidate.is_file():
            try:
                absolute_candidate.resolve().relative_to(job_dir.resolve())
                file_path = absolute_candidate.resolve()
            except ValueError:
                return None
        else:
            return None

    if artifact_key in MEDIA_ARTIFACTS:
        kind = "media"
    elif artifact_key in JSON_ARTIFACTS:
        kind = "json"
    elif artifact_key == "summary_md":
        kind = "markdown"
    elif artifact_key in TEXT_ARTIFACTS:
        kind = "text"
    else:
        kind = "text"

    return file_path, kind


def list_artifact_keys(output_root: Path, job_id: str) -> list[str]:
    resolved = resolve_job_dir(output_root, job_id)
    if resolved is None:
        return []
    _relative_dir, job_dir = resolved
    manifest_path = job_dir / "manifest.json"
    if not manifest_path.exists():
        return []
    manifest = load_manifest(manifest_path)
    artifacts = manifest.data.get("artifacts")
    if not isinstance(artifacts, dict):
        return []
    return [
        key
        for key, value in artifacts.items()
        if key != "folder" and isinstance(value, str) and value.strip()
    ]
