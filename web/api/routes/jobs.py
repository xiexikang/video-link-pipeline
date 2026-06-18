"""Job listing, submission, and detail routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.api.deps import get_output_dir
from web.api.schemas.jobs import (
    CreateJobRequest,
    CreateJobResponse,
    JobDetailResponse,
    JobListItem,
    JobListResponse,
    JobStatusResponse,
    StageSummary,
)
from web.api.services.job_queries import get_job_status, list_jobs, load_job_detail
from web.api.services.job_registry import get_registry
from web.api.services.job_runner import submit_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_stage_summary(stage: dict) -> StageSummary:
    return StageSummary(**stage)


def _validate_create_request(request: CreateJobRequest) -> None:
    if request.type in {"download", "download-subs", "run"} and not request.url:
        raise HTTPException(status_code=400, detail=f"{request.type} 需要 url")
    if request.type in {"transcribe", "summarize"} and not request.input_path:
        raise HTTPException(status_code=400, detail=f"{request.type} 需要 input_path")


@router.get("", response_model=JobListResponse)
def list_all_jobs() -> JobListResponse:
    output_root = get_output_dir()
    jobs = list_jobs(output_root)
    items = [
        JobListItem(
            id=job["id"],
            job_dir=job.get("job_dir") or "",
            title=job["title"],
            source_url=job.get("source_url"),
            source_path=job.get("source_path"),
            command=job.get("command"),
            updated_at=job.get("updated_at"),
            stages={key: _to_stage_summary(value) for key, value in job["stages"].items()},
            runtime_status=job["runtime_status"],
        )
        for job in jobs
    ]
    return JobListResponse(jobs=items, total=len(items))


@router.post("", response_model=CreateJobResponse, status_code=202)
def create_job(request: CreateJobRequest) -> CreateJobResponse:
    _validate_create_request(request)
    registry = get_registry()
    entry = registry.create(
        job_type=request.type,
        source_url=request.url,
        source_path=request.input_path,
    )
    submit_job(entry, options=request.options)
    return CreateJobResponse(
        id=entry.id,
        runtime_status="queued",
        message="任务已加入队列",
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def job_status(job_id: str) -> JobStatusResponse:
    output_root = get_output_dir()
    status = get_job_status(output_root, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return JobStatusResponse(
        id=status["id"],
        runtime_status=status["runtime_status"],
        job_dir=status.get("job_dir"),
        error=status.get("error"),
        error_code=status.get("error_code"),
        hint=status.get("hint"),
        log=status.get("log"),
        stages={key: _to_stage_summary(value) for key, value in status["stages"].items()},
    )


@router.get("/{job_id}", response_model=JobDetailResponse)
def get_job(job_id: str) -> JobDetailResponse:
    output_root = get_output_dir()
    loaded = load_job_detail(output_root, job_id)
    if loaded is None:
        raise HTTPException(status_code=404, detail="任务不存在")

    job, manifest = loaded
    entry = get_registry().get(job_id)
    runtime_status = entry.status if entry and entry.status in {"queued", "running"} else job["runtime_status"]
    if entry and entry.status in {"succeeded", "failed"}:
        runtime_status = entry.status
    return JobDetailResponse(
        id=job["id"],
        job_dir=job.get("job_dir") or "",
        manifest=manifest,
        stages={key: _to_stage_summary(value) for key, value in job["stages"].items()},
        runtime_status=runtime_status,
        log=entry.log if entry and entry.log else None,
    )
