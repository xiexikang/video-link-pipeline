"""Environment diagnostics routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from video_link_pipeline.doctor import run_checks

from web.api.deps import get_config_bundle, get_output_dir

router = APIRouter(prefix="/api", tags=["doctor"])


@router.get("/doctor")
def doctor_summary() -> dict[str, Any]:
    bundle = get_config_bundle()
    checks = run_checks(bundle.effective_config)
    output_dir = get_output_dir()
    return {
        "checks": [
            {
                "name": check.name,
                "ok": check.ok,
                "detail": check.detail,
                "section": check.section,
                "code": check.code,
                "hint": check.hint,
            }
            for check in checks
        ],
        "output_dir": str(output_dir),
        "config_source": str(bundle.source_path) if bundle.source_path else None,
    }
