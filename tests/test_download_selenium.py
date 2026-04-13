from __future__ import annotations

from pathlib import Path

from video_link_pipeline.download.selenium_fallback import SeleniumContext, should_attempt_selenium_fallback
from video_link_pipeline.download.service import execute_download


def test_should_attempt_selenium_fallback_auto_only_for_anti_crawl_errors() -> None:
    assert should_attempt_selenium_fallback("auto", "ERROR: HTTP Error 403: Forbidden") is True
    assert should_attempt_selenium_fallback("auto", "network timeout") is False
    assert should_attempt_selenium_fallback("off", "403 forbidden") is False
    assert should_attempt_selenium_fallback("on", "anything") is True


def test_execute_download_returns_install_hint_when_selenium_extra_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: (_ for _ in ()).throw(Exception("HTTP Error 403: Forbidden")),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service.run_selenium_browser_context",
        lambda **_: (_ for _ in ()).throw(
            __import__("video_link_pipeline.errors", fromlist=["DependencyMissingError"]).DependencyMissingError(
                "selenium fallback requested but optional dependencies are not installed",
                hint="install with: pip install 'video-link-pipeline[selenium]'",
            )
        ),
    )

    result = execute_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        selenium_mode="auto",
    )

    assert result["success"] is False
    assert result["used_selenium_fallback"] is False
    assert "optional dependencies are not installed" in str(result["error"])


def test_execute_download_marks_used_selenium_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: (_ for _ in ()).throw(Exception("captcha required")),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service.run_selenium_browser_context",
        lambda **_: SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/resolved",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/resolved",
            cookie_file=tmp_path / "cookies.txt",
        ),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._retry_with_selenium_context",
        lambda **kwargs: {
            **kwargs["result"],
            "success": False,
            "used_selenium_fallback": True,
            "error": "selenium fallback retry failed",
        },
    )

    result = execute_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        selenium_mode="auto",
    )

    assert result["success"] is False
    assert result["used_selenium_fallback"] is True
    assert "retry failed" in str(result["error"])


def test_execute_download_can_succeed_after_selenium_retry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: (_ for _ in ()).throw(Exception("verification required")),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service.run_selenium_browser_context",
        lambda **_: SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/resolved",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/resolved",
            cookie_file=tmp_path / "cookies.txt",
        ),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._retry_with_selenium_context",
        lambda **kwargs: {
            **kwargs["result"],
            "success": True,
            "folder": "job",
            "video": "job/video.mp4",
            "used_selenium_fallback": True,
            "error": None,
        },
    )

    result = execute_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        selenium_mode="auto",
    )

    assert result["success"] is True
    assert result["used_selenium_fallback"] is True
    assert result["video"] == "job/video.mp4"
