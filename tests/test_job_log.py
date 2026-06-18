"""Tests for web job log capture."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video_link_pipeline.pipeline.orchestrator import PipelineResult
from web.api.main import app
from web.api.services.job_registry import RegistryEntry, get_registry


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    config_path = tmp_path / "config.yaml"
    config_path.write_text(f'output_dir: "{output_dir.as_posix()}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    get_registry()._entries.clear()  # noqa: SLF001
    return TestClient(app)


def test_job_detail_includes_execution_log(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run_job(**_kwargs):  # noqa: ANN003
        print("line one")
        print("line two")
        return PipelineResult(success=True, job_dir="mock-job")

    monkeypatch.setattr("web.api.services.job_runner.pipeline_orchestrator.run_job", fake_run_job)
    monkeypatch.setattr(
        "web.api.services.job_runner._executor.submit",
        lambda fn, *args, **kwargs: fn(*args, **kwargs),
    )

    response = client.post(
        "/api/jobs",
        json={
            "type": "download",
            "url": "https://www.youtube.com/watch?v=RGG3OStcRnI",
            "options": {"cookies_from_browser": "firefox"},
        },
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    entry = get_registry().get(job_id)
    assert isinstance(entry, RegistryEntry)
    assert entry.status == "succeeded", entry.log

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["runtime_status"] == "succeeded"
    assert "[vlp] command=vlp download" in detail["log"]
    assert "cookies_from_browser='firefox'" in detail["log"]
    assert "line one" in detail["log"]
    assert "line two" in detail["log"]
