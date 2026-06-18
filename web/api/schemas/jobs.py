"""Job-related API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StageStatus = Literal["idle", "running", "done", "failed", "skipped"]
RuntimeStatus = Literal["queued", "running", "succeeded", "failed", "idle"]


class StageSummary(BaseModel):
    status: StageStatus
    success: bool | None = None
    reused_existing: bool | None = None
    error_code: str | None = None
    hint: str | None = None


class JobListItem(BaseModel):
    id: str
    job_dir: str
    title: str
    source_url: str | None = None
    source_path: str | None = None
    command: str | None = None
    updated_at: str | None = None
    stages: dict[str, StageSummary]
    runtime_status: RuntimeStatus


class JobListResponse(BaseModel):
    jobs: list[JobListItem]
    total: int


class JobDetailResponse(BaseModel):
    id: str
    job_dir: str
    manifest: dict[str, Any]
    stages: dict[str, StageSummary]
    runtime_status: RuntimeStatus
    log: str | None = None


class WarningDetail(BaseModel):
    code: str | None = None
    stage: str | None = None
    message: str | None = None
    description: str | None = None


class CreateJobRequest(BaseModel):
    type: Literal["download", "download-subs", "transcribe", "summarize", "run"] = Field(
        description="Pipeline command type aligned with vlp CLI."
    )
    url: str | None = None
    input_path: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class CreateJobResponse(BaseModel):
    id: str
    job_dir: str | None = None
    runtime_status: RuntimeStatus = "queued"
    message: str = "任务已加入队列"


class JobStatusResponse(BaseModel):
    id: str
    runtime_status: RuntimeStatus
    job_dir: str | None = None
    error: str | None = None
    error_code: str | None = None
    hint: str | None = None
    log: str | None = None
    stages: dict[str, StageSummary]


class ArtifactPreviewResponse(BaseModel):
    artifact_key: str
    kind: Literal["text", "markdown", "json", "subtitle", "media"]
    content: str | None = None
    filename: str | None = None
    media_url: str | None = None
