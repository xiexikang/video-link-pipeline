# Diagnostics Reference

Use this reference to interpret pipeline diagnostics, especially download failures, fallback behavior, and environment-related problems.

Prefer the repository's structured diagnostics over ad hoc guesses from console text.

## Primary Sources

When diagnosing a problem, prefer these sources in order:

1. `manifest.json`
2. `vlp doctor`
3. CLI output

## Main Diagnostic Areas

The repository's most important diagnostic areas are:

- download failure classification
- Selenium fallback state
- browser cookies availability
- browser driver or Selenium extra availability
- FFmpeg availability
- configuration conflicts or risky settings

## Structured Download Diagnostics

Download diagnostics are primarily represented in:

- `execution.download.error_code`
- `execution.download.hint`
- `execution.download.warnings`
- `execution.download.warning_details`
- `execution.download.fallback_status`
- `execution.download.fallback_context`

Prefer `warning_details` over plain warning strings when available.

## Common Warning Codes

### `primary_http_403`

- The primary download path hit HTTP 403.
- Common causes include anti-bot protection, auth requirements, geo restriction, or missing cookies.
- Try browser cookies, retry after verification in a real browser, or consider Selenium fallback.

### `primary_captcha_required`

- The page likely requires human verification or captcha completion.
- Open the page in a browser, complete verification, then retry with browser cookies or Selenium-enabled workflow.

### `primary_auth_required`

- The site likely requires login or account access.
- Log into the target site in a browser, then retry with `--cookies-from-browser` or `--cookie-file`.

### `browser_cookie_locked`

- The browser cookies database could not be copied or is locked.
- This often happens because the browser is still running, especially on Windows.
- Fully close the target browser, then retry cookie extraction.

### `browser_driver_unavailable`

- Selenium fallback could not run because required dependencies or browser driver support are unavailable.
- Install the Selenium extra, confirm Chrome can launch normally, and rerun `vlp doctor`.

### `ffmpeg_unavailable`

- FFmpeg is missing and download merge, audio extraction, or conversion may fail.
- Install system FFmpeg or ensure `imageio-ffmpeg` remains available in the environment.

### `fallback_context_prepared`

- The Selenium fallback successfully prepared a browser-derived context.
- Inspect whether retry succeeded and whether a useful media hint was extracted.

### `fallback_media_hint_missing_page_only`

- Almost no structured media cue was extracted.
- Fallback may retry with the resolved page URL instead of a direct media URL.

### `fallback_media_hint_missing_inline_only`

- Only inline script or raw HTML cues were detected.
- The page may require deeper parsing of inline state or embedded script data.

### `fallback_media_hint_missing_structured`

- Structured signals such as JSON-LD, meta tags, or window state were detected, but they still did not expose a direct media URL.
- This usually points to incomplete site-specific extraction logic.

### `fallback_dependency_hint`, `fallback_prepare_hint`, `fallback_retry_hint`

- These are supplemental hints attached to different fallback phases.
- Dependency hint means check Selenium and browser requirements.
- Prepare hint means inspect browser launch, cookies, and page-state extraction.
- Retry hint means inspect the final retry attempt, headers, cookies, or extracted media hint quality.

## Fallback Status Interpretation

The most useful `fallback_status` values include:

- `not_attempted`
- `triggered`
- `dependency_missing`
- `prepare_failed`
- `prepared`
- `retry_failed`
- `succeeded`

Read them like this:

- `not_attempted`: fallback did not run.
- `triggered`: fallback logic was entered.
- `dependency_missing`: fallback could not proceed because required dependencies were missing.
- `prepare_failed`: fallback started but failed while preparing browser context.
- `prepared`: browser context was successfully prepared.
- `retry_failed`: fallback reached retry but still failed.
- `succeeded`: fallback recovered the download through browser-assisted retry.

## How To Use `fallback_context`

Use `fallback_context` to understand how much useful information the browser-assisted path actually extracted.

Important fields:

- `resolved_url`
- `canonical_url`
- `media_hint_url`
- `site_name`
- `extraction_source`
- `extraction_kind`

Interpretation patterns:

- `media_hint_url` present means retry had a stronger candidate than the plain page URL.
- `media_hint_url` missing means fallback likely retried with a weaker page-level URL.
- `extraction_kind=jsonld`, `meta`, `next_data`, or `window_state` means structured page cues were found.

## Using `vlp doctor`

Use `vlp doctor` when:

- download errors are ambiguous
- environment setup may be incomplete
- FFmpeg may be missing
- Selenium extra may be missing
- cookies settings may be conflicting
- browser-based auth access may be needed

## Config Risk Interpretation

Some issues are not runtime failures but risky configurations.

Common examples:

- both browser cookies and cookie file configured at once
- Selenium turned off while no cookie source is configured
- browser cookie source configured but the browser is unsupported or unavailable

## Final Rule

Prefer acting on stable fields:

- warning codes
- fallback status
- fallback context
- doctor checks
- effective config

Avoid making important decisions from vague console wording alone.
