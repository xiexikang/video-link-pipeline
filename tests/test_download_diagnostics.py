from __future__ import annotations

from video_link_pipeline.download.diagnostics import (
    preferred_warning_hint,
    warning_catalog,
    warning_catalog_codes,
    warning_code_description,
    warning_code_remediation,
)
from video_link_pipeline.doctor import DoctorCheck, doctor_guidance


def test_warning_code_description_and_remediation_for_known_code() -> None:
    description = warning_code_description("browser_cookie_locked")
    remediation = warning_code_remediation("browser_cookie_locked")

    assert description is not None
    assert "cookies database" in description
    assert remediation is not None
    assert "Close the target browser completely" in remediation


def test_warning_code_lookup_returns_none_for_unknown_code() -> None:
    assert warning_code_description("unknown-warning-code") is None
    assert warning_code_remediation("unknown-warning-code") is None


def test_warning_catalog_exposes_sorted_shared_index() -> None:
    catalog = warning_catalog()
    codes = [entry.code for entry in catalog]

    assert codes == sorted(codes)
    assert "browser_cookie_locked" in codes
    assert "ffmpeg_unavailable" in codes
    cookie_entry = next(entry for entry in catalog if entry.code == "browser_cookie_locked")
    assert "cookies database" in cookie_entry.description
    assert cookie_entry.remediation is not None
    assert "Close the target browser completely" in cookie_entry.remediation


def test_warning_catalog_codes_matches_catalog_entries() -> None:
    assert warning_catalog_codes() == [entry.code for entry in warning_catalog()]


def test_preferred_warning_hint_prefers_shared_remediation() -> None:
    hint = preferred_warning_hint("browser_driver_unavailable", "install selenium")

    assert hint is not None
    assert "Install the Selenium extra" in hint


def test_preferred_warning_hint_falls_back_to_custom_hint() -> None:
    hint = preferred_warning_hint("fallback_dependency_hint", "install selenium")

    assert hint == "install selenium"


def test_doctor_guidance_deduplicates_codes_and_skips_missing_metadata() -> None:
    checks = [
        DoctorCheck(
            name="cookies",
            ok=True,
            detail="configured browser cookies source: chrome",
            code="browser_cookie_locked",
            hint="close browser first",
        ),
        DoctorCheck(
            name="cookies-duplicate",
            ok=False,
            detail="cookie db is locked",
            code="browser_cookie_locked",
            hint="close browser first",
        ),
        DoctorCheck(
            name="cookie-file",
            ok=False,
            detail="configured cookie file does not exist",
            code=None,
            hint="export a Netscape cookie file",
        ),
    ]

    guidance = doctor_guidance(checks)

    assert len(guidance) == 2
    assert guidance[0].startswith("browser_cookie_locked:")
    assert guidance[1].startswith("browser_cookie_locked fix:")


def test_doctor_guidance_includes_description_without_forcing_fix_line() -> None:
    checks = [
        DoctorCheck(
            name="cookies",
            ok=True,
            detail="no cookie source configured",
            code="fallback_dependency_hint",
            hint="install selenium extra",
        )
    ]

    guidance = doctor_guidance(checks)

    assert len(guidance) == 1
    assert guidance[0].startswith("fallback_dependency_hint:")
