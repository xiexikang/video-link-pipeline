"""Shared pipeline orchestration for CLI and web."""

from .orchestrator import PipelineResult, run_job

__all__ = ["PipelineResult", "run_job"]
