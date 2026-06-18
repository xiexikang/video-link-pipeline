"""Parse manifest execution blocks into UI stage summaries."""

from __future__ import annotations

from typing import Any, Literal

StageStatus = Literal["idle", "running", "done", "failed", "skipped"]
RuntimeStatus = Literal["queued", "running", "succeeded", "failed", "idle"]

STAGE_KEYS = ("download", "transcribe", "summarize")


def parse_stage(execution: dict[str, Any], stage: str) -> dict[str, Any]:
    """Map a manifest execution stage to a UI-friendly summary."""
    stage_data = execution.get(stage)
    if not isinstance(stage_data, dict) or not stage_data:
        return {"status": "idle", "success": None}

    success = stage_data.get("success")
    if success is True:
        status: StageStatus = "done"
    elif success is False:
        status = "failed"
    elif success is None and stage_data:
        status = "skipped"
    else:
        status = "idle"

    return {
        "status": status,
        "success": success if isinstance(success, bool) else None,
        "reused_existing": stage_data.get("reused_existing"),
        "error_code": stage_data.get("error_code"),
        "hint": stage_data.get("hint"),
    }


def parse_all_stages(execution: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    execution = execution if isinstance(execution, dict) else {}
    return {stage: parse_stage(execution, stage) for stage in STAGE_KEYS}


def derive_runtime_status(
    stages: dict[str, dict[str, Any]],
    *,
    memory_status: str | None = None,
) -> RuntimeStatus:
    """Derive overall runtime status from stage summaries and optional memory state."""
    if memory_status in {"queued", "running"}:
        return memory_status  # type: ignore[return-value]

    statuses = [stages[key]["status"] for key in STAGE_KEYS if key in stages]
    if any(status == "failed" for status in statuses):
        return "failed"
    if memory_status == "failed":
        return "failed"
    if memory_status == "succeeded":
        return "succeeded"

    active = [status for status in statuses if status != "idle"]
    if not active:
        return "idle"
    if all(status in {"done", "skipped"} for status in active):
        return "succeeded"
    return "idle"
