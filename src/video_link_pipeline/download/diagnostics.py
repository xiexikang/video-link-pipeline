from __future__ import annotations

WARNING_CODES = {
    "primary_download_failed": "Primary download failed without a more specific classification.",
    "primary_http_403": "Primary download hit 403/Forbidden, usually anti-bot, auth, or geo restriction.",
    "primary_captcha_required": "Primary download hit a captcha or human verification page.",
    "primary_auth_required": "Primary download requires login or account access.",
    "browser_cookie_locked": "Browser cookies database is locked or could not be copied.",
    "browser_driver_unavailable": "Selenium browser driver or optional dependency is unavailable.",
    "ffmpeg_unavailable": "FFmpeg is unavailable and media merge or conversion may fail.",
    "fallback_context_prepared": "Selenium fallback prepared a usable browser context.",
    "fallback_media_hint_missing": "No explicit media URL was extracted, so retry falls back to the page URL.",
    "fallback_dependency_hint": "Additional hint emitted when fallback dependencies are missing.",
    "fallback_prepare_hint": "Additional hint emitted when fallback browser-context preparation fails.",
    "fallback_retry_hint": "Additional hint emitted when fallback retry fails.",
    "fallback_retry_unhandled_exception": "Fallback retry raised an unclassified exception.",
}

WARNING_REMEDIATIONS = {
    "browser_cookie_locked": (
        "Close the target browser completely, then retry --cookies-from-browser. "
        "On Windows, this often happens when the cookies database is still locked by the browser process."
    ),
    "browser_driver_unavailable": (
        "Install the Selenium extra with `pip install \"video-link-pipeline[selenium]\"` "
        "and make sure Chrome can start normally."
    ),
    "ffmpeg_unavailable": (
        "Install system ffmpeg or keep `imageio-ffmpeg` available in the environment."
    ),
    "primary_http_403": (
        "Try browser cookies, wait before retrying, or switch to Selenium fallback if the site is anti-bot protected."
    ),
    "primary_captcha_required": (
        "Open the page in a browser, complete verification if needed, then retry with browser cookies or Selenium fallback."
    ),
    "primary_auth_required": (
        "Log in with the target account and retry with `--cookies-from-browser` or a Netscape cookie file."
    ),
    "fallback_media_hint_missing": (
        "The page did not expose a direct media URL. Retrying with the resolved page URL may still work, but site-specific extraction may need to be improved."
    ),
}


def warning_code_description(code: str) -> str | None:
    return WARNING_CODES.get(code)


def warning_code_remediation(code: str) -> str | None:
    return WARNING_REMEDIATIONS.get(code)


def preferred_warning_hint(code: str, fallback_hint: str | None = None) -> str | None:
    remediation = warning_code_remediation(code)
    normalized_fallback = str(fallback_hint or "").strip() or None
    if remediation:
        return remediation
    return normalized_fallback
