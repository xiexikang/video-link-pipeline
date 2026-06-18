"""Tests for web job submission."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_link_pipeline.pipeline.orchestrator import PipelineResult
from web.api.deps import get_config_bundle
from web.api.main import app
from web.api.services.job_registry import get_registry


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f'output_dir: "{output_dir.as_posix()}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    get_registry()._entries.clear()  # noqa: SLF001
    return TestClient(app)


def test_create_job_returns_queued(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_submit(entry, *, options):  # noqa: ANN001, ARG001
        get_registry().update(entry.id, status="running")

    monkeypatch.setattr("web.api.routes.jobs.submit_job", fake_submit)

    response = client.post(
        "/api/jobs",
        json={
            "type": "download-subs",
            "url": "https://www.bilibili.com/video/BV1test",
            "options": {"cookies_from_browser": "chrome"},
        },
    )
    assert response.status_code == 202
    payload = response.json()
    assert payload["runtime_status"] == "queued"
    job_id = payload["id"]

    status_response = client.get(f"/api/jobs/{job_id}/status")
    assert status_response.status_code == 200


def test_create_job_requires_url(client: TestClient) -> None:
    response = client.post("/api/jobs", json={"type": "run", "options": {}})
    assert response.status_code == 400


def test_run_job_integration_mock(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_job(**kwargs):  # noqa: ANN003
        return PipelineResult(success=True, job_dir="mock-job")

    monkeypatch.setattr("web.api.services.job_runner.pipeline_orchestrator.run_job", fake_run_job)

    response = client.post(
        "/api/jobs",
        json={"type": "download-subs", "url": "https://example.com/v"},
    )
    job_id = response.json()["id"]

    import time

    time.sleep(0.3)
    status = client.get(f"/api/jobs/{job_id}/status").json()
    assert status["runtime_status"] in {"succeeded", "running", "queued"}


def test_failed_registry_job_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_job(**kwargs):  # noqa: ANN003
        raise RuntimeError("Sign in to confirm you're not a bot")

    monkeypatch.setattr("web.api.services.job_runner.pipeline_orchestrator.run_job", fake_run_job)
    monkeypatch.setattr(
        "web.api.services.job_runner._executor.submit",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    response = client.post(
        "/api/jobs",
        json={"type": "download-subs", "url": "https://www.youtube.com/watch?v=test"},
    )
    job_id = response.json()["id"]

    detail = client.get(f"/api/jobs/{job_id}")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["runtime_status"] == "failed"
    assert payload["manifest"]["execution"]["download"]["error"]
