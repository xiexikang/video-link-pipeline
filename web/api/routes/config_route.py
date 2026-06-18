"""Configuration summary routes."""

from __future__ import annotations

from fastapi import APIRouter

from web.api.deps import get_config_bundle, get_redacted_config

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/effective")
def effective_config() -> dict:
    bundle = get_config_bundle()
    return {
        "source_path": str(bundle.source_path) if bundle.source_path else None,
        "effective": get_redacted_config(),
        "warnings": bundle.warnings,
    }
