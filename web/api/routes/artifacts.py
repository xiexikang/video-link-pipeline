"""Artifact preview routes."""

from __future__ import annotations

import mimetypes

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from web.api.deps import get_output_dir
from web.api.schemas.jobs import ArtifactPreviewResponse
from web.api.services.artifact_resolver import resolve_artifact_file

router = APIRouter(prefix="/api/jobs", tags=["artifacts"])

MEDIA_MIME = {
    ".mp4": "video/mp4",
    ".m4a": "audio/mp4",
    ".webm": "video/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
}


@router.get("/{job_id}/artifacts/{artifact_key}", response_model=ArtifactPreviewResponse)
def preview_artifact(job_id: str, artifact_key: str) -> ArtifactPreviewResponse:
    output_root = get_output_dir()
    resolved = resolve_artifact_file(output_root, job_id, artifact_key)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path, kind = resolved
    if kind == "media":
        return ArtifactPreviewResponse(
            artifact_key=artifact_key,
            kind="media",
            filename=file_path.name,
            media_url=f"/api/jobs/{job_id}/artifacts/{artifact_key}/stream",
        )

    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=415, detail="Artifact is not text-encodable") from exc

    preview_kind = kind
    if artifact_key.startswith("subtitle"):
        preview_kind = "subtitle"

    return ArtifactPreviewResponse(
        artifact_key=artifact_key,
        kind=preview_kind,  # type: ignore[arg-type]
        content=content,
        filename=file_path.name,
    )


@router.get("/{job_id}/artifacts/{artifact_key}/stream")
def stream_artifact(job_id: str, artifact_key: str) -> FileResponse:
    output_root = get_output_dir()
    resolved = resolve_artifact_file(output_root, job_id, artifact_key)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Artifact not found")

    file_path, kind = resolved
    if kind != "media" and file_path.suffix.lower() not in {".mp4", ".m4a", ".webm", ".mp3", ".wav"}:
        media_type = "application/octet-stream"
    else:
        media_type = MEDIA_MIME.get(file_path.suffix.lower()) or mimetypes.guess_type(file_path.name)[0]
        media_type = media_type or "application/octet-stream"

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=file_path.name,
    )
