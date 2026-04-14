# video-link-pipeline

`video-link-pipeline` is a local CLI toolchain for video downloading, transcription, summarization, and subtitle conversion.

This repository is being migrated from a collection of standalone scripts to a publishable Python package with a unified CLI. The recommended entry point is now `vlp`. Legacy scripts such as `download_video.py`, `parallel_transcribe.py`, `generate_summary.py`, and `convert_subtitle.py` are still kept as compatibility wrappers.

## Current Commands

- `vlp download <url>`: download video, audio, and subtitles into a normalized job folder
- `vlp transcribe <path>`: run Whisper transcription and write `transcript.txt`, `subtitle_whisper.srt`, and `subtitle_whisper.vtt`
- `vlp summarize <transcript.txt>`: generate `summary.md` and `keywords.json`
- `vlp convert-subtitle <file-or-dir>`: convert between `srt` and `vtt`
- `vlp run <url>`: orchestrate download, transcription, and summary while updating `manifest.json`
- `vlp doctor`: inspect Python, FFmpeg, Selenium extra, and cookies-related setup

## Installation

Requirements:

- Python 3.10+
- Windows, Linux, and macOS are supported, with Windows being the primary focus right now

Recommended installation:

```bash
git clone <repository_url>
cd video-link-pipeline
pip install -e .
```

To enable Selenium fallback support:

```bash
pip install -e .[selenium]
```

To install development dependencies:

```bash
pip install -e .[dev]
```

`vlp doctor` now also surfaces common download diagnostics and suggested fixes, especially for Windows-oriented issues:

- `browser_cookie_locked`: close Chrome / Edge / Firefox completely before retrying browser-cookie extraction
- `browser_driver_unavailable`: install the Selenium extra with `pip install "video-link-pipeline[selenium]"`
- `ffmpeg_unavailable`: install system ffmpeg or keep `imageio-ffmpeg` available in the environment

`vlp doctor` currently highlights:

- grouped output sections such as `runtime`, `download prerequisites`, `effective download config`, `config risks`, and `common diagnostic guidance`
- a `known diagnostic codes` section that only supplements common codes not already shown in `common diagnostic guidance`, reducing duplicate output
- the final FFmpeg selection source and path, such as system `ffmpeg` or `imageio-ffmpeg`
- whether the Selenium extra is fully available
- the current effective `download.selenium` mode, such as `auto`, `on`, or `off`
- the current effective `download.cookies_from_browser` and `download.cookie_file` values
- a compact effective download config summary line so the final `selenium` and cookies combination is visible at a glance
- whether cookies are configured via browser extraction or file path
- combination risks or conflicts between `download.selenium`, `cookies_from_browser`, and `cookie_file`
- focused remediation hints for common Windows issues such as locked cookie databases, missing drivers, and missing FFmpeg

Within the `config risks` section, the output levels mean:

- `WARN`: a real conflict, invalid configuration, or something that may directly block the workflow
- `INFO`: the current configuration is still usable, but the item is worth attention and should not be treated as a hard failure

Quick verification:

```bash
vlp --help
vlp doctor
```

## Local Dev Checks

If you are contributing locally, install the dev extra:

```bash
pip install -e .[dev]
```

The minimum validation commands aligned with CI are:

```bash
python -m ruff check .
python -m pytest
```

If `pytest` is not installed yet, `python -m pytest` will fail with an error similar to `No module named pytest`. In that case, run:

```bash
pip install -e .[dev]
```

To run only a smaller subset first:

```bash
python -m pytest tests/test_doctor.py
python -m pytest tests/test_download_diagnostics.py
```

## Configuration

The default config file is `config.yaml` in the repository root.

Configuration precedence:

1. CLI arguments
2. Environment variables and `.env`
3. `config.yaml`
4. Built-in defaults

Example config:

```yaml
output_dir: ./output
temp_dir: ./temp

download:
  quality: best
  format: mp4
  subtitles_langs: [zh, en]
  write_subtitles: true
  write_auto_subs: true
  cookies_from_browser: null
  cookie_file: null
  selenium: auto

whisper:
  model: small
  engine: auto
  language: auto
  device: auto
  compute_type: int8

summary:
  enabled: true
  provider: claude
  model: claude-3-5-sonnet-20241022
  base_url: null
  max_tokens: 4096
  temperature: 0.3

api_keys:
  claude: null
  openai: null
  gemini: null
  deepseek: null
  kimi: null
  moonshot: null
  minimax: null
  glm: null
  zhipu: null
```

Common environment variables:

```bash
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
GEMINI_API_KEY=...
DEEPSEEK_API_KEY=...
VLP_OUTPUT_DIR=./output
VLP_DOWNLOAD_COOKIES_FROM_BROWSER=chrome
VLP_WHISPER_MODEL=small
VLP_SUMMARY_PROVIDER=claude
```

Notes:

- Legacy `summary.api_keys.*` is still read for compatibility, but it now emits a migration warning
- `vlp doctor` reports the selected FFmpeg source and highlights Selenium/cookies issues
- `--selenium auto|on|off` is wired into `download` and `run`

## Usage

### Download

```bash
vlp download "https://www.bilibili.com/video/BV..."
vlp download "https://..." --output-dir ./output --sub-lang zh --sub-lang en
vlp download "https://..." --audio-only
vlp download "https://..." --cookies-from-browser chrome
vlp download "https://..." --cookie-file ./cookies.txt
vlp download "https://..." --selenium auto
```

### Transcribe

```bash
vlp transcribe ./output/demo/video.mp4
vlp transcribe ./output/demo --model small --language auto
vlp transcribe ./output/demo/video.mp4 --engine faster --device cpu --compute-type int8
```

### Summarize

```bash
vlp summarize ./output/demo/transcript.txt --provider claude
vlp summarize ./output/demo/transcript.txt --provider deepseek --base-url https://api.deepseek.com --model deepseek-chat
```

### Convert subtitles

```bash
vlp convert-subtitle ./subtitle.vtt --format srt
vlp convert-subtitle ./subs --batch --format srt
```

### Run the pipeline

```bash
vlp run "https://..."
vlp run "https://..." --do-transcribe
vlp run "https://..." --do-transcribe --do-summary
```

### Doctor

```bash
vlp doctor
vlp doctor --config ./config.yaml
```

## Output Contract

`output_dir` is the output root. Each task writes into its own job directory.

A typical output tree looks like this:

```text
output/
└─ BVxxxx-demo-title/
   ├─ video.mp4
   ├─ audio.m4a
   ├─ subtitle.vtt
   ├─ subtitle.srt
   ├─ transcript.txt
   ├─ subtitle_whisper.srt
   ├─ subtitle_whisper.vtt
   ├─ transcript.json
   ├─ summary.md
   ├─ keywords.json
   └─ manifest.json
```

`manifest.json` is the stable machine-readable output and is incrementally updated by `download`, `transcribe`, `summarize`, and `run`.

When Selenium fallback is triggered during download, `execution.download` also carries extra diagnostics:

- `used_selenium_fallback`: whether browser fallback was used
- `error_code`: categorized download failure code, such as `DOWNLOAD_PRIMARY_FAILED`, `DOWNLOAD_FALLBACK_PREPARE_FAILED`, or `DOWNLOAD_FALLBACK_RETRY_FAILED`
- `hint`: user-facing remediation advice, preferably aligned with doctor guidance and warning-code remediation
- `fallback_status`: fallback lifecycle status, such as `triggered`, `dependency_missing`, `prepare_failed`, `retry_failed`, or `succeeded`
- `warnings`: trigger reason, dependency hints, and context-preparation notes
- `warning_details`: structured warning records with `code`, `message`, and `stage`, useful for batch analytics, for example `primary_http_403`, `browser_cookie_locked`, or `fallback_media_hint_missing`
- `fallback_context.resolved_url`: the final browser URL
- `fallback_context.canonical_url`: the canonical page URL when available
- `fallback_context.media_hint_url`: the preferred media URL extracted from page signals
- `fallback_context.site_name`: the detected site name
- `fallback_context.extraction_source`: where the media hint came from, such as `next-data:playAddr` or `jsonld:contentUrl`

Common `warning_details.code` values:

- `primary_http_403`: the primary download hit a 403/Forbidden, usually anti-bot, auth, or geo restriction
- `primary_captcha_required`: the primary download hit a captcha or human verification page
- `primary_auth_required`: the primary download requires login or account access
- `browser_cookie_locked`: the browser cookies database is locked or could not be copied
- `browser_driver_unavailable`: the Selenium browser driver is unavailable
- `fallback_context_prepared`: fallback successfully extracted a usable browser context
- `fallback_media_hint_missing`: no explicit media URL was extracted, so retry falls back to the page URL
- `fallback_dependency_hint` / `fallback_prepare_hint` / `fallback_retry_hint`: stage-specific fallback hints

A typical download diagnostics fragment looks like this:

```json
{
  "execution": {
    "download": {
      "success": false,
      "used_selenium_fallback": false,
      "fallback_status": "dependency_missing",
      "error_code": "DEPENDENCY_MISSING",
      "error": "selenium fallback requested but optional dependencies are not installed",
      "hint": "install with: pip install 'video-link-pipeline[selenium]'",
      "warnings": [
        "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
        "install with: pip install \"video-link-pipeline[selenium]\""
      ],
      "warning_details": [
        {
          "code": "primary_http_403",
          "stage": "primary_download",
          "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
          "description": "Primary download hit 403/Forbidden, usually anti-bot, auth, or geo restriction."
        },
        {
          "code": "fallback_dependency_hint",
          "stage": "fallback_dependency",
          "message": "install with: pip install \"video-link-pipeline[selenium]\"",
          "description": "Additional hint emitted when fallback dependencies are missing."
        }
      ],
      "fallback_context": null
    }
  }
}
```

If fallback successfully prepares a browser context, the common signals become:

- `fallback_status = "prepared"` or `"succeeded"`
- `warning_details.code` contains `fallback_context_prepared`
- `fallback_context.media_hint_url` and `fallback_context.extraction_source` can be used to analyze extractor quality per site

The CLI download diagnostics now mirrors the same field names where practical so console output lines up with `manifest.json` and `vlp doctor` terminology:

- `download fallback_status=...`
- `download error_code=...`
- `download error_stage=...`
- `download hint=...`
- `download warning_code=<code> stage=<stage>: ...`
- `download fallback_context.extraction_source=...`
- `download fallback_context.media_hint_url=...`
- `download fallback_context.canonical_url=...`
- `download fallback_context.resolved_url=...`

These `warning_details.code` values and `vlp doctor` guidance are backed by the same shared diagnostics catalog in `video_link_pipeline.download.diagnostics`. New warning codes should be added there first so doctor, manifest output, and docs stay aligned.

## Compatibility Wrappers

These script entry points are still available:

- `python download_video.py ...`
- `python parallel_transcribe.py ...`
- `python generate_summary.py ...`
- `python convert_subtitle.py ...`

New usage should prefer `vlp`. The wrapper scripts now act as compatibility layers over the package implementation and are no longer the long-term primary interface.

## Current Status

- `vlp run` and `vlp doctor` are implemented
- Basic tests and a Windows CI workflow have been added
- If `pytest` is not installed in the local environment, tests cannot be executed directly
- Selenium fallback is still being refined; `doctor` currently focuses on install and diagnosis guidance

## License

MIT License
