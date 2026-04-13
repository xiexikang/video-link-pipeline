from __future__ import annotations

from pathlib import Path

from video_link_pipeline.download.selenium_fallback import (
    SeleniumContext,
    choose_best_media_hint,
    extract_page_signals_from_html,
    should_attempt_selenium_fallback,
)
from video_link_pipeline.download.service import _origin_from_url, _retry_with_selenium_context, execute_download


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
    assert result["error_code"] == "DEPENDENCY_MISSING"
    assert result["error_stage"] == "fallback_dependency"
    assert result["fallback_status"] == "dependency_missing"
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
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/media.m3u8",
            site_name="example.com",
            extraction_source="meta:og:video",
        ),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._retry_with_selenium_context",
        lambda **kwargs: {
            **kwargs["result"],
            "success": False,
            "used_selenium_fallback": True,
            "error_code": "DOWNLOAD_FALLBACK_RETRY_FAILED",
            "error_stage": "fallback_retry",
            "fallback_status": "retry_failed",
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
    assert result["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert result["error_stage"] == "fallback_retry"
    assert result["fallback_status"] == "retry_failed"
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
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/media.m3u8",
            site_name="example.com",
            extraction_source="meta:og:video",
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
            "error_code": None,
            "error_stage": None,
            "fallback_status": "succeeded",
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
    assert result["fallback_status"] == "succeeded"
    assert result["video"] == "job/video.mp4"


def test_origin_from_url_handles_missing_values() -> None:
    assert _origin_from_url("https://www.example.com/watch?v=1") == "https://www.example.com"
    assert _origin_from_url(None) is None
    assert _origin_from_url("not-a-url") is None


def test_retry_with_selenium_context_uses_media_hint_headers(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakePreparation:
        def __init__(self) -> None:
            self.output_root = tmp_path
            self.output_dir = tmp_path / "job"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.title_hint = "demo"
            self.ffmpeg_path = "ffmpeg"
            self.url = "https://cdn.example.com/media.m3u8"
            self.ydl_options = {}

    def fake_probe_download(**kwargs):
        captured["probe_url"] = kwargs["url"]
        captured["cookie_file"] = kwargs["cookie_file"]
        return FakePreparation()

    monkeypatch.setattr("video_link_pipeline.download.service.probe_download", fake_probe_download)

    def fake_execute_ydl_download(preparation):
        captured["headers"] = dict(preparation.ydl_options.get("http_headers", {}))
        return {
            "video": "video.mp4",
            "audio_mp3": None,
            "audio_m4a": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info_json": None,
        }

    monkeypatch.setattr(
        "video_link_pipeline.download.service._execute_ydl_download",
        fake_execute_ydl_download,
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._validate_downloaded_files",
        lambda *args, **kwargs: None,
    )

    result = _retry_with_selenium_context(
        context=SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/resolved",
            page_title="demo",
            user_agent="mobile-ua",
            referer="https://example.com/resolved",
            cookie_file=tmp_path / "cookies.txt",
            page_description="page description",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://cdn.example.com/media.m3u8",
            site_name="example.com",
            extraction_source="jsonld:contentUrl",
        ),
        output_dir=tmp_path,
        languages=["zh"],
        quality="best",
        audio_only=False,
        result={"success": False, "url": "https://example.com/video", "subtitle": None},
    )

    assert captured["probe_url"] == "https://cdn.example.com/media.m3u8"
    assert Path(str(captured["cookie_file"])) == tmp_path / "cookies.txt"
    headers = captured["headers"]
    assert headers["User-Agent"] == "mobile-ua"
    assert headers["Referer"] == "https://example.com/watch/demo"
    assert headers["Origin"] == "https://example.com"
    assert result["success"] is True
    assert result["used_selenium_fallback"] is True
    assert result["fallback_context"]["media_hint_url"] == "https://cdn.example.com/media.m3u8"
    assert result["fallback_context"]["extraction_source"] == "jsonld:contentUrl"
    assert any("selenium fallback context prepared" in item for item in result["warnings"])


def test_choose_best_media_hint_prefers_streamable_urls() -> None:
    url, source = choose_best_media_hint(
        [
            {"url": "https://example.com/video.mp4", "source": "jsonld"},
            {"url": "https://example.com/master.m3u8", "source": "next-data"},
            {"url": "https://example.com/dash.mpd", "source": "inline-script"},
        ]
    )

    assert url == "https://example.com/master.m3u8"
    assert source == "next-data"


def test_extract_page_signals_from_html_reads_jsonld_and_next_data() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@context":"https://schema.org","contentUrl":"https://cdn.example.com/from-jsonld.mp4"}
        </script>
        <script id="__NEXT_DATA__" type="application/json">
          {"props":{"pageProps":{"video":{"playAddr":"https://cdn.example.com/from-next-data.m3u8"}}}}
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/123",
        canonical_url="https://example.com/watch/123",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-next-data.m3u8"
    assert signals["extraction_source"] == "next-data:playAddr"
