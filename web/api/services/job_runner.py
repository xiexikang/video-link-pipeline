"""Background execution for web-submitted pipeline jobs."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from video_link_pipeline.config import load_config
from video_link_pipeline.download.service import _resolve_node_executable, _youtube_js_challenge_options
from video_link_pipeline.errors import VlpError
from video_link_pipeline.pipeline import orchestrator as pipeline_orchestrator

from .job_log import JobLogBuffer, capture_job_output
from .job_registry import RegistryEntry, get_registry

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vlp-job")
_runner_lock = threading.Lock()


def submit_job(entry: RegistryEntry, *, options: dict[str, Any]) -> None:
    """Queue a registry entry for background execution."""
    registry = get_registry()
    registry.update(entry.id, status="queued", log="")
    _executor.submit(_execute, entry.id, options)


def _log_job_context(entry: RegistryEntry, options: dict[str, Any], buffer: JobLogBuffer) -> None:
    bundle = load_config(overrides=pipeline_orchestrator._build_overrides(options))
    download_config = bundle.effective_config.get("download", {})
    node_path = _resolve_node_executable()
    js_options = _youtube_js_challenge_options()
    buffer.append(f"[vlp] command=vlp {entry.job_type}")
    if entry.source_url:
        buffer.append(f"[vlp] url={entry.source_url}")
    if entry.source_path:
        buffer.append(f"[vlp] input_path={entry.source_path}")
    buffer.append(
        "[vlp] download.cookies_from_browser="
        f"{download_config.get('cookies_from_browser')!r}"
    )
    buffer.append(f"[vlp] node_runtime={node_path!r}")
    buffer.append(f"[vlp] js_challenge_enabled={bool(js_options)}")
    if js_options:
        buffer.append(f"[vlp] js_runtimes={js_options.get('js_runtimes')!r}")


def _execute(job_id: str, options: dict[str, Any]) -> None:
    registry = get_registry()
    entry = registry.get(job_id)
    if entry is None:
        return

    buffer = JobLogBuffer()

    def publish_log() -> None:
        registry.update(job_id, log=buffer.text())

    registry.update(job_id, status="running", log="")
    _log_job_context(entry, options, buffer)
    publish_log()

    try:
        with capture_job_output(buffer):
            result = pipeline_orchestrator.run_job(
                job_type=entry.job_type,
                url=entry.source_url,
                input_path=entry.source_path,
                options=options,
            )
        publish_log()
        if result.success:
            registry.update(
                job_id,
                status="succeeded",
                job_dir=result.job_dir,
                log=buffer.text(),
            )
        else:
            registry.update(
                job_id,
                status="failed",
                job_dir=result.job_dir,
                error=result.error,
                error_code=result.error_code,
                hint=result.hint,
                log=buffer.text(),
            )
    except VlpError as exc:
        publish_log()
        registry.update(
            job_id,
            status="failed",
            error=exc.message,
            error_code=exc.error_code,
            hint=exc.hint,
            log=buffer.text(),
        )
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures to registry
        buffer.append(f"[vlp] unexpected error: {exc}")
        publish_log()
        registry.update(
            job_id,
            status="failed",
            error=str(exc),
            error_code="VLP_ERROR",
            log=buffer.text(),
        )


def shutdown_runner() -> None:
    with _runner_lock:
        _executor.shutdown(wait=False, cancel_futures=True)
