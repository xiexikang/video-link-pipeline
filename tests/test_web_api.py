"""Integration tests for the web API."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web.api.deps import get_config_bundle, get_output_dir
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


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_jobs_empty(client: TestClient) -> None:
    response = client.get("/api/jobs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 0
    assert payload["jobs"] == []


def test_preview_artifact(client: TestClient, tmp_path: Path) -> None:
    output_dir = get_output_dir()
    job_dir = output_dir / "preview-job"
    job_dir.mkdir(parents=True)
    (job_dir / "summary.md").write_text("# Title\n\nBody", encoding="utf-8")
    manifest = {
        "updated_at": "2026-06-10T12:00:00Z",
        "input": {"url": None, "input_path": None},
        "artifacts": {"summary_md": "summary.md"},
        "execution": {},
    }
    (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    list_response = client.get("/api/jobs")
    job_id = list_response.json()["jobs"][0]["id"]
    preview = client.get(f"/api/jobs/{job_id}/artifacts/summary_md")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload["kind"] == "markdown"
    assert "Title" in payload["content"]


def test_list_and_get_job(client: TestClient, tmp_path: Path) -> None:
    output_dir = get_output_dir()
    job_dir = output_dir / "sample-job"
    job_dir.mkdir(parents=True)
    manifest = {
        "updated_at": "2026-06-10T12:00:00Z",
        "command": "vlp download-subs",
        "input": {"url": "https://www.bilibili.com/video/BV1test", "input_path": None},
        "artifacts": {"subtitle_srt": "subtitle.srt"},
        "execution": {
            "download": {"success": True},
            "transcribe": {"success": None},
            "summarize": {"success": None},
        },
    }
    (job_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    list_response = client.get("/api/jobs")
    assert list_response.status_code == 200
    jobs = list_response.json()["jobs"]
    assert len(jobs) == 1
    job_id = jobs[0]["id"]

    detail_response = client.get(f"/api/jobs/{job_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["manifest"]["command"] == "vlp download-subs"
    assert detail["stages"]["download"]["status"] == "done"


def test_doctor_endpoint(client: TestClient) -> None:
    response = client.get("/api/doctor")
    assert response.status_code == 200
    payload = response.json()
    assert "checks" in payload
    assert isinstance(payload["checks"], list)
    assert "output_dir" in payload


def test_cookie_login_routes(client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cookie_file = tmp_path / "youtube-cookies.txt"

    class FakeCookieRegistry:
        def start(self, *, url: str, cookie_file: str | Path | None = None) -> tuple[str, Path]:
            assert url == "https://www.youtube.com"
            assert cookie_file == str(cookie_file_path)
            return "session-1", Path(str(cookie_file))

        def export(self, session_id: str) -> Path | None:
            assert session_id == "session-1"
            cookie_file.write_text("# Netscape HTTP Cookie File\n", encoding="utf-8")
            return cookie_file

        def cancel(self, session_id: str) -> bool:
            return session_id == "session-1"

    cookie_file_path = cookie_file
    monkeypatch.setattr(
        "web.api.routes.cookies.get_cookie_login_registry",
        lambda: FakeCookieRegistry(),
    )

    start_response = client.post(
        "/api/cookies/login/start",
        json={
            "url": "https://www.youtube.com",
            "cookie_file": str(cookie_file),
        },
    )

    assert start_response.status_code == 200
    start_payload = start_response.json()
    assert start_payload["session_id"] == "session-1"
    assert start_payload["cookie_file"] == str(cookie_file)

    export_response = client.post("/api/cookies/login/session-1/export")

    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["cookie_file"] == str(cookie_file)
