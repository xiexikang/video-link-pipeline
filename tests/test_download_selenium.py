from __future__ import annotations

from pathlib import Path

from video_link_pipeline.download.cookies import CookieSource
from video_link_pipeline.download.selenium_fallback import (
    SeleniumContext,
    SeleniumFallbackError,
    classify_extraction_kind,
    choose_best_media_hint,
    extract_page_signals_from_html,
    should_attempt_selenium_fallback,
)
from video_link_pipeline.download.service import (
    _append_hint_warning,
    _append_warning_with_hint,
    _apply_page_description,
    _apply_preparation_metadata,
    _build_fallback_context,
    _build_retry_headers,
    _continue_after_primary_failure,
    _execute_primary_download,
    _handle_fallback_vlp_error,
    _handle_unexpected_fallback_exception,
    _prepare_retry_download,
    _record_primary_exception,
    _record_primary_failure,
    _record_retry_context_state,
    _fallback_exception_warning_code,
    _classify_hint_warning,
    _classify_primary_warning,
    _missing_explicit_media_hint,
    _missing_media_hint_warning_code,
    _origin_from_url,
    _record_fallback_prepare_warnings,
    _record_primary_download_warning,
    _retry_with_selenium_context,
    _set_failure_state,
    _set_prepared_fallback_context,
    _validate_downloaded_files,
    DownloadPreparation,
    DownloadError,
    execute_download,
    new_download_result,
    resolve_job_directory,
    resolve_site_bucket,
)
from video_link_pipeline.errors import DependencyMissingError


def test_should_attempt_selenium_fallback_auto_only_for_anti_crawl_errors() -> None:
    assert should_attempt_selenium_fallback("auto", "ERROR: HTTP Error 403: Forbidden") is True
    assert should_attempt_selenium_fallback("auto", "network timeout") is False
    assert should_attempt_selenium_fallback("off", "403 forbidden") is False
    assert should_attempt_selenium_fallback("on", "anything") is True


def test_classify_extraction_kind_covers_common_signal_families() -> None:
    assert classify_extraction_kind("meta:itemprop:contentUrl") == "meta"
    assert classify_extraction_kind("jsonld:contentUrl") == "jsonld"
    assert classify_extraction_kind("next-data:playAddr") == "next_data"
    assert classify_extraction_kind("window.__DATA__:playAddr") == "window_state"
    assert classify_extraction_kind("dom:video") == "dom"
    assert classify_extraction_kind("inline-script") == "inline_script"
    assert classify_extraction_kind("inline-html") == "inline_html"
    assert classify_extraction_kind(None) == "unknown"


def test_new_download_result_provides_stable_default_shape() -> None:
    result = new_download_result("https://example.com/video")

    assert result["success"] is False
    assert result["url"] == "https://example.com/video"
    assert result["fallback_status"] == "not_attempted"
    assert result["error_code"] is None
    assert result["error_stage"] is None
    assert result["warnings"] == []
    assert result["warning_details"] == []
    assert result["fallback_context"] is None
    assert result["hint"] is None
    assert result["media_duration_seconds"] is None
    assert result["media_duration_human"] is None
    assert result["started_at"] is None
    assert result["started_at_local"] is None
    assert result["finished_at"] is None
    assert result["finished_at_local"] is None
    assert result["elapsed_seconds"] is None


def test_resolve_site_bucket_normalizes_common_platforms() -> None:
    assert resolve_site_bucket("https://www.bilibili.com/video/BV1TYzsBLEds/") == "bilibili"
    assert resolve_site_bucket("https://youtu.be/demo") == "youtube"
    assert resolve_site_bucket("https://v.douyin.com/demo/") == "douyin"
    assert resolve_site_bucket("https://sub.example.com/watch/1") == "sub.example.com"


def test_resolve_job_directory_can_group_by_site_bucket(tmp_path: Path) -> None:
    job_dir = resolve_job_directory(tmp_path, "Demo Title", "video-123", site_bucket="bilibili")

    assert job_dir == tmp_path / "bilibili" / "video-123-Demo_Title"


def test_classify_primary_warning_covers_common_cases() -> None:
    assert _classify_primary_warning("HTTP Error 403: Forbidden") == "primary_http_403"
    assert _classify_primary_warning("please verify you are human before continuing") == "primary_captcha_required"
    assert _classify_primary_warning("could not copy database because cookies are locked") == "browser_cookie_locked"
    assert _classify_primary_warning("sign in to confirm your age") == "primary_auth_required"
    assert _classify_primary_warning("unexpected extractor failure") == "primary_download_failed"


def test_classify_hint_warning_covers_shared_dependency_cases() -> None:
    assert _classify_hint_warning("could not copy database because the database is locked", default_code="fallback_retry_hint") == "browser_cookie_locked"
    assert _classify_hint_warning("chromedriver could not be found", default_code="fallback_retry_hint") == "browser_driver_unavailable"
    assert _classify_hint_warning("ffmpeg is required for merge", default_code="fallback_retry_hint") == "ffmpeg_unavailable"
    assert _classify_hint_warning("some custom retry hint", default_code="fallback_retry_hint") == "fallback_retry_hint"


def test_classify_hint_warning_recognizes_account_access_cases() -> None:
    assert _classify_hint_warning("account access is required for this content", default_code="fallback_retry_hint") == "primary_auth_required"


def test_fallback_exception_warning_code_maps_exception_types() -> None:
    assert _fallback_exception_warning_code(DependencyMissingError("missing", hint="install selenium")) == "fallback_dependency_hint"
    assert _fallback_exception_warning_code(__import__("video_link_pipeline.download.selenium_fallback", fromlist=["SeleniumFallbackError"]).SeleniumFallbackError("prepare failed")) == "fallback_prepare_hint"
    assert _fallback_exception_warning_code(__import__("video_link_pipeline.download.service", fromlist=["DownloadError"]).DownloadError("retry failed")) == "fallback_retry_hint"
    assert _fallback_exception_warning_code(RuntimeError("unexpected")) == "fallback_retry_unhandled_exception"


def test_set_failure_state_updates_result_consistently() -> None:
    result = {
        "error": None,
        "error_code": None,
        "error_stage": None,
        "fallback_status": "triggered",
    }

    _set_failure_state(
        result,
        error="final retry failed",
        error_code="DOWNLOAD_FALLBACK_RETRY_FAILED",
        error_stage="fallback_retry",
        fallback_status="retry_failed",
    )

    assert result["error"] == "final retry failed"
    assert result["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert result["error_stage"] == "fallback_retry"
    assert result["fallback_status"] == "retry_failed"


def test_record_primary_download_warning_sets_warning_details_and_hint() -> None:
    result = {"warnings": [], "warning_details": [], "hint": None}

    warning_code = _record_primary_download_warning(result, "HTTP Error 403: Forbidden")

    assert warning_code == "primary_http_403"
    assert result["warning_details"][0]["code"] == "primary_http_403"
    assert result["warning_details"][0]["stage"] == "primary_download"
    assert "triggered selenium fallback" in result["warning_details"][0]["message"]
    assert "Try browser cookies" in str(result["hint"])


def test_record_primary_failure_sets_primary_download_error_state() -> None:
    result = new_download_result("https://example.com/video")

    _record_primary_failure(result, "primary extractor failed")

    assert result["error"] == "primary extractor failed"
    assert result["error_code"] == "DOWNLOAD_PRIMARY_FAILED"
    assert result["error_stage"] == "primary_download"


def test_record_primary_exception_normalizes_download_and_generic_errors() -> None:
    result = new_download_result("https://example.com/video")
    _record_primary_exception(result, DownloadError("download path failed"))

    assert result["error"] == "download path failed"
    assert result["error_code"] == "DOWNLOAD_PRIMARY_FAILED"
    assert result["error_stage"] == "primary_download"

    generic_result = new_download_result("https://example.com/video")
    _record_primary_exception(generic_result, RuntimeError("unexpected primary failure"))

    assert generic_result["error"] == "unexpected primary failure"
    assert generic_result["error_code"] == "DOWNLOAD_PRIMARY_FAILED"
    assert generic_result["error_stage"] == "primary_download"


def test_build_fallback_context_returns_stable_manifest_shape(tmp_path: Path) -> None:
    context = SeleniumContext(
        original_url="https://example.com/video",
        resolved_url="https://example.com/resolved",
        page_title="demo",
        user_agent="ua",
        referer="https://example.com/resolved",
        cookie_file=tmp_path / "cookies.txt",
        page_description="page description",
        canonical_url="https://example.com/watch/demo",
        media_hint_url="https://cdn.example.com/media.m3u8",
        site_name="example.com",
        extraction_source="jsonld:contentUrl",
    )

    fallback_context = _build_fallback_context(context)

    assert fallback_context == {
        "resolved_url": "https://example.com/resolved",
        "canonical_url": "https://example.com/watch/demo",
        "media_hint_url": "https://cdn.example.com/media.m3u8",
        "site_name": "example.com",
        "extraction_source": "jsonld:contentUrl",
        "extraction_kind": "jsonld",
    }


def test_missing_explicit_media_hint_detects_page_url_fallbacks(tmp_path: Path) -> None:
    assert _missing_explicit_media_hint(
        SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="dom",
        )
    ) is True
    assert _missing_explicit_media_hint(
        SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://cdn.example.com/video.m3u8",
            site_name="example.com",
            extraction_source="jsonld",
        )
    ) is False


def test_missing_media_hint_warning_code_distinguishes_signal_families(tmp_path: Path) -> None:
    assert _missing_media_hint_warning_code(
        SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="window.__DATA__:playAddr",
        )
    ) == "fallback_media_hint_missing_structured"
    assert _missing_media_hint_warning_code(
        SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="inline-html",
        )
    ) == "fallback_media_hint_missing_inline_only"
    assert _missing_media_hint_warning_code(
        SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="dom",
        )
    ) == "fallback_media_hint_missing_page_only"


def test_apply_preparation_metadata_updates_core_result_fields(tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")
    preparation = DownloadPreparation(
        url="https://example.com/video",
        output_root=tmp_path,
        output_dir=tmp_path / "job",
        title_hint="demo-title",
        cookie_source=CookieSource(browser=None, cookie_file=None),
        ffmpeg_path="C:/ffmpeg/bin/ffmpeg.exe",
        video_id="demo-id",
        duration_seconds=95.0,
        duration_human="1:35",
        ydl_options={},
    )

    _apply_preparation_metadata(result, preparation)

    assert result["title"] == "demo-title"
    assert result["folder"] == str(tmp_path / "job")
    assert result["ffmpeg_path"] == "C:/ffmpeg/bin/ffmpeg.exe"
    assert result["media_duration_seconds"] == 95.0
    assert result["media_duration_human"] == "1:35"


def test_apply_page_description_and_set_prepared_fallback_context(tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")
    context = SeleniumContext(
        original_url="https://example.com/video",
        resolved_url="https://example.com/resolved",
        page_title="demo",
        user_agent="ua",
        referer="https://example.com/resolved",
        cookie_file=tmp_path / "cookies.txt",
        page_description="page description",
        canonical_url="https://example.com/watch/demo",
        media_hint_url="https://cdn.example.com/video.m3u8",
        site_name="example.com",
        extraction_source="jsonld",
    )

    _apply_page_description(result, context.page_description)
    _set_prepared_fallback_context(result, context)

    assert result["error"] == "page description"
    assert result["fallback_status"] == "prepared"
    assert result["fallback_context"]["media_hint_url"] == "https://cdn.example.com/video.m3u8"


def test_build_retry_headers_prefers_canonical_url_and_origin(tmp_path: Path) -> None:
    context = SeleniumContext(
        original_url="https://example.com/video",
        resolved_url="https://example.com/resolved",
        page_title="demo",
        user_agent="mobile-ua",
        referer="https://example.com/fallback-referrer",
        cookie_file=tmp_path / "cookies.txt",
        page_description="page description",
        canonical_url="https://example.com/watch/demo",
        media_hint_url="https://cdn.example.com/media.m3u8",
        site_name="example.com",
        extraction_source="jsonld:contentUrl",
    )

    headers = _build_retry_headers(context)

    assert headers["User-Agent"] == "mobile-ua"
    assert headers["Referer"] == "https://example.com/watch/demo"
    assert headers["Origin"] == "https://example.com"


def test_prepare_retry_download_applies_probe_headers_and_metadata(monkeypatch, tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")

    class FakePreparation:
        def __init__(self) -> None:
            self.url = "https://cdn.example.com/media.m3u8"
            self.output_root = tmp_path
            self.output_dir = tmp_path / "job"
            self.title_hint = "demo"
            self.ffmpeg_path = "ffmpeg"
            self.video_id = "demo-id"
            self.duration_seconds = 95.0
            self.duration_human = "1:35"
            self.ydl_options = {}

    captured: dict[str, object] = {}

    def fake_probe_download(**kwargs):
        captured["probe_url"] = kwargs["url"]
        captured["cookie_file"] = kwargs["cookie_file"]
        return FakePreparation()

    monkeypatch.setattr("video_link_pipeline.download.service.probe_download", fake_probe_download)

    preparation = _prepare_retry_download(
        context=SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/resolved",
            page_title="demo",
            user_agent="mobile-ua",
            referer="https://example.com/fallback-referrer",
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
        subtitle_only=False,
        result=result,
    )

    assert captured["probe_url"] == "https://cdn.example.com/media.m3u8"
    assert Path(str(captured["cookie_file"])) == tmp_path / "cookies.txt"
    assert preparation.ydl_options["http_headers"]["User-Agent"] == "mobile-ua"
    assert preparation.ydl_options["http_headers"]["Referer"] == "https://example.com/watch/demo"
    assert preparation.ydl_options["http_headers"]["Origin"] == "https://example.com"
    assert result["title"] == "demo"
    assert result["folder"] == str(tmp_path / "job")
    assert result["ffmpeg_path"] == "ffmpeg"


def test_execute_primary_download_applies_metadata_and_artifacts(monkeypatch, tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")

    class FakePreparation:
        def __init__(self) -> None:
            self.url = "https://example.com/video"
            self.output_root = tmp_path
            self.output_dir = tmp_path / "job"
            self.title_hint = "demo"
            self.ffmpeg_path = "ffmpeg"
            self.video_id = "demo-id"
            self.duration_seconds = 95.0
            self.duration_human = "1:35"
            self.ydl_options = {}

    monkeypatch.setattr("video_link_pipeline.download.service.probe_download", lambda **kwargs: FakePreparation())
    monkeypatch.setattr(
        "video_link_pipeline.download.service._execute_ydl_download",
        lambda preparation: {
            "video": "video.mp4",
            "audio_mp3": None,
            "audio_m4a": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info_json": None,
        },
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._validate_downloaded_files",
        lambda *args, **kwargs: None,
    )

    updated = _execute_primary_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        languages=["zh"],
        quality="best",
        audio_only=False,
        subtitle_only=False,
        cookies_from_browser=None,
        cookie_file=None,
        result=result,
    )

    assert updated["success"] is True
    assert updated["title"] == "demo"
    assert updated["folder"] == str(tmp_path / "job")
    assert updated["ffmpeg_path"] == "ffmpeg"
    assert updated["video"] == "job/video.mp4"


def test_record_retry_context_state_updates_description_context_and_status(tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")
    context = SeleniumContext(
        original_url="https://example.com/video",
        resolved_url="https://example.com/resolved",
        page_title="demo",
        user_agent="mobile-ua",
        referer="https://example.com/fallback-referrer",
        cookie_file=tmp_path / "cookies.txt",
        page_description="page description",
        canonical_url="https://example.com/watch/demo",
        media_hint_url="https://cdn.example.com/media.m3u8",
        site_name="example.com",
        extraction_source="jsonld:contentUrl",
    )

    _record_retry_context_state(result, context)

    assert result["error"] == "page description"
    assert result["fallback_status"] == "prepared"
    assert result["fallback_context"] == {
        "resolved_url": "https://example.com/resolved",
        "canonical_url": "https://example.com/watch/demo",
        "media_hint_url": "https://cdn.example.com/media.m3u8",
        "site_name": "example.com",
        "extraction_source": "jsonld:contentUrl",
        "extraction_kind": "jsonld",
    }
    assert result["warning_details"][0]["code"] == "fallback_context_prepared"
    assert "kind=jsonld" in result["warning_details"][0]["message"]


def test_handle_fallback_vlp_error_records_dependency_failure_and_hint() -> None:
    result = new_download_result("https://example.com/video")

    _handle_fallback_vlp_error(
        result,
        DependencyMissingError(
            "selenium fallback requested but optional dependencies are not installed",
            hint="install with: pip install 'video-link-pipeline[selenium]'",
        ),
    )

    assert result["error_code"] == "DEPENDENCY_MISSING"
    assert result["error_stage"] == "fallback_dependency"
    assert result["fallback_status"] == "dependency_missing"
    assert result["warning_details"][0]["code"] == "fallback_dependency_hint"
    assert "Install the Selenium extra" in str(result["hint"])


def test_handle_fallback_vlp_error_uses_dependency_state_mapping() -> None:
    result = new_download_result("https://example.com/video")

    _handle_fallback_vlp_error(
        result,
        DependencyMissingError(
            "selenium fallback requested but optional dependencies are not installed",
            hint="missing webdriver",
        ),
    )

    assert result["error_stage"] == "fallback_dependency"
    assert result["fallback_status"] == "dependency_missing"
    assert result["warning_details"][0]["stage"] == "fallback_dependency"


def test_handle_fallback_vlp_error_records_prepare_failure_with_stage_hint() -> None:
    result = new_download_result("https://example.com/video")

    _handle_fallback_vlp_error(
        result,
        SeleniumFallbackError(
            "selenium fallback could not prepare browser context",
            hint="chromedriver could not be found",
        ),
    )

    assert result["error_code"] == "DOWNLOAD_FALLBACK_PREPARE_FAILED"
    assert result["error_stage"] == "fallback_prepare"
    assert result["fallback_status"] == "prepare_failed"
    assert result["warning_details"][0]["code"] == "browser_driver_unavailable"
    assert "chromedriver" in result["warning_details"][0]["message"]
    assert result["hint"] == "Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` and make sure Chrome can start normally."


def test_handle_fallback_vlp_error_records_retry_failure_without_overriding_existing_hint() -> None:
    result = new_download_result("https://example.com/video")
    result["hint"] = "existing primary hint"

    _handle_fallback_vlp_error(
        result,
        DownloadError(
            "retry download failed",
            hint="ffmpeg is required for merge",
        ),
    )

    assert result["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert result["error_stage"] == "fallback_retry"
    assert result["fallback_status"] == "retry_failed"
    assert result["warning_details"][0]["code"] == "ffmpeg_unavailable"
    assert result["hint"] == "existing primary hint"


def test_handle_unexpected_fallback_exception_records_retry_failure() -> None:
    result = new_download_result("https://example.com/video")

    _handle_unexpected_fallback_exception(result, RuntimeError("unexpected fallback crash"))

    assert result["error_code"] == "DOWNLOAD_FALLBACK_RETRY_FAILED"
    assert result["error_stage"] == "fallback_retry"
    assert result["fallback_status"] == "retry_failed"
    assert result["warning_details"][0]["code"] == "fallback_retry_unhandled_exception"
    assert result["warning_details"][0]["stage"] == "fallback_retry"


def test_record_fallback_prepare_warnings_adds_expected_codes(tmp_path: Path) -> None:
    result = {"warnings": [], "warning_details": []}
    context = SeleniumContext(
        original_url="https://example.com/video",
        resolved_url="https://example.com/watch/demo",
        page_title="demo",
        user_agent="ua",
        referer="https://example.com/watch/demo",
        cookie_file=tmp_path / "cookies.txt",
        page_description="page description",
        canonical_url="https://example.com/watch/demo",
        media_hint_url="https://example.com/watch/demo",
        site_name="example.com",
        extraction_source="dom",
    )

    _record_fallback_prepare_warnings(result, context)

    codes = [item["code"] for item in result["warning_details"]]
    assert codes == ["fallback_context_prepared", "fallback_media_hint_missing_page_only"]


def test_append_hint_warning_does_not_override_existing_hint_by_default() -> None:
    result = {
        "warnings": [],
        "warning_details": [],
        "hint": "existing primary hint",
    }

    warning_code = _append_hint_warning(
        result,
        hint="ffmpeg is required for merge",
        default_code="fallback_retry_hint",
        stage="fallback_retry",
    )

    assert warning_code == "ffmpeg_unavailable"
    assert result["warning_details"][0]["code"] == "ffmpeg_unavailable"
    assert result["warning_details"][0]["stage"] == "fallback_retry"
    assert result["hint"] == "existing primary hint"


def test_append_warning_with_hint_prefers_shared_remediation() -> None:
    result = {
        "warnings": [],
        "warning_details": [],
        "hint": None,
    }

    _append_warning_with_hint(
        result,
        code="browser_driver_unavailable",
        message="chromedriver is missing",
        stage="fallback_prepare",
        fallback_hint="custom fallback hint",
    )

    assert result["warning_details"][0]["code"] == "browser_driver_unavailable"
    assert result["hint"] == "Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` and make sure Chrome can start normally."


def test_append_warning_with_hint_uses_fallback_hint_when_no_shared_remediation() -> None:
    result = {
        "warnings": [],
        "warning_details": [],
        "hint": "existing primary hint",
    }

    _append_warning_with_hint(
        result,
        code="fallback_retry_hint",
        message="custom retry hint",
        stage="fallback_retry",
        fallback_hint="custom retry hint",
        overwrite_hint=False,
    )
    assert result["hint"] == "existing primary hint"

    _append_warning_with_hint(
        result,
        code="fallback_retry_hint",
        message="custom retry hint override",
        stage="fallback_retry",
        fallback_hint="custom retry hint override",
        overwrite_hint=True,
    )

    assert result["hint"] == "custom retry hint override"


def test_append_hint_warning_can_override_hint_when_requested() -> None:
    result = {
        "warnings": [],
        "warning_details": [],
        "hint": "existing primary hint",
    }

    warning_code = _append_hint_warning(
        result,
        hint="chromedriver is missing",
        default_code="fallback_retry_hint",
        stage="fallback_prepare",
        overwrite_hint=True,
    )

    assert warning_code == "browser_driver_unavailable"
    assert result["warning_details"][0]["code"] == "browser_driver_unavailable"
    assert "Install the Selenium extra" in str(result["hint"])


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
    assert result["warning_details"][0]["code"] == "primary_http_403"
    assert result["warning_details"][0]["description"]
    assert result["warning_details"][1]["code"] == "fallback_dependency_hint"
    assert (
        str(result["hint"])
        == 'Install the Selenium extra with `pip install "video-link-pipeline[selenium]"` and make sure Chrome can start normally.'
    )
    assert "optional dependencies are not installed" in str(result["error"])


def test_validate_downloaded_files_accepts_subtitle_only_outputs(tmp_path: Path) -> None:
    job_dir = tmp_path / "subtitle-job"
    job_dir.mkdir()
    (job_dir / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    _validate_downloaded_files(job_dir, audio_only=False, subtitle_only=True)


def test_execute_download_subtitle_only_succeeds_without_video(monkeypatch, tmp_path: Path) -> None:
    output_root = tmp_path / "output"
    job_dir = output_root / "video-123-demo"
    job_dir.mkdir(parents=True)

    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: DownloadPreparation(
            url="https://example.com/video",
            output_root=output_root,
            output_dir=job_dir,
            title_hint="demo",
            cookie_source=CookieSource(),
            ffmpeg_path=None,
            video_id="video-123",
            duration_seconds=42.0,
            duration_human="0:42",
            ydl_options={"skip_download": True},
        ),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._execute_ydl_download",
        lambda preparation: {
            "video": None,
            "audio_m4a": None,
            "audio_mp3": None,
            "subtitle_vtt": None,
            "subtitle_srt": "subtitle.srt",
            "info_json": None,
        },
    )
    (job_dir / "subtitle.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nhello\n", encoding="utf-8")

    result = execute_download(
        url="https://example.com/video",
        output_dir=output_root,
        subtitle_only=True,
        selenium_mode="off",
    )

    assert result["success"] is True
    assert result["video"] is None
    assert result["subtitle"] == "video-123-demo/subtitle.srt"
    assert result["subtitle_srt"] == "video-123-demo/subtitle.srt"
    assert result["needs_whisper"] is False
    assert result["media_duration_seconds"] == 42.0
    assert result["media_duration_human"] == "0:42"
    assert isinstance(result["started_at"], str)
    assert isinstance(result["started_at_local"], str)
    assert isinstance(result["finished_at"], str)
    assert isinstance(result["finished_at_local"], str)
    assert isinstance(result["elapsed_seconds"], float)
    assert result["elapsed_seconds"] >= 0


def test_continue_after_primary_failure_delegates_to_download_failure(monkeypatch, tmp_path: Path) -> None:
    result = new_download_result("https://example.com/video")
    result["error"] = "HTTP Error 403: Forbidden"
    captured: dict[str, object] = {}

    def fake_handle_download_failure(**kwargs):
        captured.update(kwargs)
        return {"delegated": True}

    monkeypatch.setattr(
        "video_link_pipeline.download.service._handle_download_failure",
        fake_handle_download_failure,
    )

    delegated = _continue_after_primary_failure(
        result=result,
        output_dir=tmp_path,
        selenium_mode="auto",
        languages=["zh"],
        quality="best",
        audio_only=False,
        subtitle_only=False,
    )

    assert delegated == {"delegated": True}
    assert captured["result"] is result
    assert captured["output_dir"] == tmp_path
    assert captured["selenium_mode"] == "auto"


def test_execute_download_does_not_trigger_fallback_when_selenium_is_off(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: (_ for _ in ()).throw(Exception("HTTP Error 403: Forbidden")),
    )
    fallback_called = {"value": False}

    def fake_run_selenium_browser_context(**_: object):
        fallback_called["value"] = True
        raise AssertionError("fallback should not run when selenium=off")

    monkeypatch.setattr(
        "video_link_pipeline.download.service.run_selenium_browser_context",
        fake_run_selenium_browser_context,
    )

    result = execute_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        selenium_mode="off",
    )

    assert fallback_called["value"] is False
    assert result["success"] is False
    assert result["error_code"] == "DOWNLOAD_PRIMARY_FAILED"
    assert result["error_stage"] == "primary_download"
    assert result["fallback_status"] == "not_attempted"
    assert result["warning_details"] == []


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
    assert result["warning_details"][0]["code"] == "primary_captcha_required"
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
            self.video_id = "demo-id"
            self.duration_seconds = 95.0
            self.duration_human = "1:35"
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
            subtitle_only=False,
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
    assert result["fallback_context"]["extraction_kind"] == "jsonld"
    assert result["warning_details"][0]["code"] == "fallback_context_prepared"
    assert result["warning_details"][0]["description"]
    assert any("selenium fallback context prepared" in item for item in result["warnings"])


def test_retry_with_selenium_context_marks_missing_explicit_media_hint(monkeypatch, tmp_path: Path) -> None:
    class FakePreparation:
        def __init__(self) -> None:
            self.output_root = tmp_path
            self.output_dir = tmp_path / "job"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.title_hint = "demo"
            self.ffmpeg_path = "ffmpeg"
            self.url = "https://example.com/watch/demo"
            self.video_id = "demo-id"
            self.duration_seconds = 95.0
            self.duration_human = "1:35"
            self.ydl_options = {}

    monkeypatch.setattr("video_link_pipeline.download.service.probe_download", lambda **kwargs: FakePreparation())
    monkeypatch.setattr(
        "video_link_pipeline.download.service._execute_ydl_download",
        lambda preparation: {
            "video": "video.mp4",
            "audio_mp3": None,
            "audio_m4a": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info_json": None,
        },
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._validate_downloaded_files",
        lambda *args, **kwargs: None,
    )

    result = _retry_with_selenium_context(
        context=SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="mobile-ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="page description",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="dom",
        ),
            output_dir=tmp_path,
            languages=["zh"],
            quality="best",
            audio_only=False,
            subtitle_only=False,
            result={"success": False, "url": "https://example.com/video", "subtitle": None},
        )

    codes = [item["code"] for item in result["warning_details"]]
    assert "fallback_context_prepared" in codes
    assert "fallback_media_hint_missing_page_only" in codes


def test_retry_with_selenium_context_marks_structured_media_hint_missing(monkeypatch, tmp_path: Path) -> None:
    class FakePreparation:
        def __init__(self) -> None:
            self.output_root = tmp_path
            self.output_dir = tmp_path / "job"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.title_hint = "demo"
            self.ffmpeg_path = "ffmpeg"
            self.url = "https://example.com/watch/demo"
            self.video_id = "demo-id"
            self.duration_seconds = 95.0
            self.duration_human = "1:35"
            self.ydl_options = {}

    monkeypatch.setattr("video_link_pipeline.download.service.probe_download", lambda **kwargs: FakePreparation())
    monkeypatch.setattr(
        "video_link_pipeline.download.service._execute_ydl_download",
        lambda preparation: {
            "video": "video.mp4",
            "audio_mp3": None,
            "audio_m4a": None,
            "subtitle_vtt": None,
            "subtitle_srt": None,
            "info_json": None,
        },
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service._validate_downloaded_files",
        lambda *args, **kwargs: None,
    )

    result = _retry_with_selenium_context(
        context=SeleniumContext(
            original_url="https://example.com/video",
            resolved_url="https://example.com/watch/demo",
            page_title="demo",
            user_agent="mobile-ua",
            referer="https://example.com/watch/demo",
            cookie_file=tmp_path / "cookies.txt",
            page_description="page description",
            canonical_url="https://example.com/watch/demo",
            media_hint_url="https://example.com/watch/demo",
            site_name="example.com",
            extraction_source="window.__DATA__:playAddr",
        ),
            output_dir=tmp_path,
            languages=["zh"],
            quality="best",
            audio_only=False,
            subtitle_only=False,
            result={"success": False, "url": "https://example.com/video", "subtitle": None},
        )

    codes = [item["code"] for item in result["warning_details"]]
    assert "fallback_media_hint_missing_structured" in codes


def test_execute_download_classifies_cookie_lock_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "video_link_pipeline.download.service.probe_download",
        lambda **_: (_ for _ in ()).throw(
            Exception("could not copy database because the browser cookie database is locked")
        ),
    )
    monkeypatch.setattr(
        "video_link_pipeline.download.service.run_selenium_browser_context",
        lambda **_: (_ for _ in ()).throw(
            __import__("video_link_pipeline.errors", fromlist=["DependencyMissingError"]).DependencyMissingError(
                "selenium fallback requested but optional dependencies are not installed",
                hint="could not copy database because the browser cookie database is locked",
            )
        ),
    )

    result = execute_download(
        url="https://example.com/video",
        output_dir=tmp_path,
        selenium_mode="auto",
    )

    codes = [item["code"] for item in result["warning_details"]]
    assert "browser_cookie_locked" in codes
    assert "Close the target browser completely" in str(result["hint"])


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


def test_extract_page_signals_from_html_reads_inline_initial_state() -> None:
    html = """
    <html>
      <head>
        <script>
          window.__INITIAL_STATE__ = {
            "detail": {
              "video": {
                "playAddr": "https://cdn.example.com/from-initial-state.m3u8"
              }
            }
          };
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/456",
        canonical_url="https://example.com/watch/456",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-initial-state.m3u8"
    assert signals["extraction_source"] == "window.__INITIAL_STATE__:playAddr"


def test_extract_page_signals_from_html_reads_meta_content_url() -> None:
    html = """
    <html>
      <head>
        <meta itemprop="contentUrl" content="https://cdn.example.com/from-meta.mp4" />
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/789",
        canonical_url="https://example.com/watch/789",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-meta.mp4"
    assert signals["extraction_source"] == "meta:itemprop:contentUrl"


def test_extract_page_signals_from_html_reads_inline_nuxt_without_semicolon() -> None:
    html = """
    <html>
      <head>
        <script>
          window.__NUXT__ = {
            "state": {
              "video": {
                "dash": {
                  "url": "https://cdn.example.com/from-nuxt.mpd"
                }
              }
            }
          }
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/nuxt",
        canonical_url="https://example.com/watch/nuxt",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-nuxt.mpd"
    assert signals["extraction_source"] == "window.__NUXT__:dash:url"


def test_extract_page_signals_from_html_reads_inline_data_json_parse() -> None:
    html = r"""
    <html>
      <head>
        <script>
          window.__DATA__ = JSON.parse("{\"detail\":{\"video\":{\"playAddr\":\"https://cdn.example.com/from-json-parse.m3u8\"}}}");
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/json-parse",
        canonical_url="https://example.com/watch/json-parse",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-json-parse.m3u8"
    assert signals["extraction_source"] == "window.__DATA__:playAddr"


def test_extract_page_signals_from_html_reads_state_assignment_without_window_prefix() -> None:
    html = """
    <html>
      <head>
        <script>
          __STATE__ = {
            "detail": {
              "video": {
                "contentUrl": "https://cdn.example.com/from-state.mp4"
              }
            }
          };
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/state",
        canonical_url="https://example.com/watch/state",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-state.mp4"
    assert signals["extraction_source"] == "window.__STATE__:contentUrl"


def test_extract_page_signals_from_html_reads_json_parse_with_single_quotes() -> None:
    html = r"""
    <html>
      <head>
        <script>
          __APP_DATA__ = JSON.parse('{"detail":{"video":{"dash":{"url":"https://cdn.example.com/from-single-quote.mpd"}}}}')
        </script>
      </head>
      <body></body>
    </html>
    """

    signals = extract_page_signals_from_html(
        html=html,
        resolved_url="https://example.com/watch/app-data",
        canonical_url="https://example.com/watch/app-data",
        description="demo page",
        site_name="example.com",
    )

    assert signals["media_hint_url"] == "https://cdn.example.com/from-single-quote.mpd"
    assert signals["extraction_source"] == "window.__APP_DATA__:dash:url"
