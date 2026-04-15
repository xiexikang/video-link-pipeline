# video-link-pipeline Architecture

## Status

Draft v1

## Implementation Status

The refactor has moved beyond the initial design stage and most v1 foundations are now in place.

Current progress by milestone:

- `M1a` is effectively complete: package metadata, `src/` layout, shared config/errors/logging/manifest modules, and compatibility wrappers are in place
- `M1b` is effectively complete: `download`, `transcribe`, `summarize`, and `convert-subtitle` have been migrated behind the unified `vlp` CLI
- `M1c` is effectively complete: `manifest.json` is written incrementally, job-directory normalization is implemented, and the docs have largely been realigned with the live config schema
- `M2` is in progress but substantially delivered: `vlp doctor`, structured download diagnostics, warning classification, shared remediation guidance, baseline tests, Windows CI, and local dev-check scripts are already available
- `M3` has a usable baseline: `vlp run` exists and updates `manifest.json`, with follow-up work focused on edge-case stabilization rather than first implementation

What is still open:

- Run the full local validation flow in an environment with the `dev` extra installed, especially `pytest`, `ruff`, `pip check`, and package build verification
- Continue hardening Selenium fallback and site-specific media-hint extraction for harder platforms and anti-bot flows
- Expand regression coverage around download diagnostics, retry paths, and manifest updates across partial-success scenarios
- Optionally extend CI beyond Windows so pure Python paths are exercised on an additional platform

## Purpose

This document defines the v1 maintainability refactor for `video-link-pipeline` (`vlp`).
It is intended to turn the current script collection into a publishable Python package
with a stable CLI, consistent configuration model, machine-readable output contract,
clear Windows diagnostics, and a low-risk migration path for existing users.

## Current State

The current repository is centered on four standalone Python scripts:

- `download_video.py`
- `parallel_transcribe.py`
- `generate_summary.py`
- `convert_subtitle.py`

The scripts are functional, but the project currently has these structural issues:

- No package layout or release metadata
- No unified CLI entry point
- Repeated config loading logic across scripts
- Config schema drift between code and `README.md`
- Inconsistent parameter names and output conventions
- Optional dependencies are discovered at runtime instead of declared clearly
- No stable machine-readable execution result contract
- No automated tests or CI

## Goals

- Publish as a pip-installable package with the CLI command `vlp`
- Preserve existing script entry points as compatibility wrappers
- Introduce a unified configuration schema and deterministic precedence rules
- Introduce `manifest.json` as the stable output contract
- Improve Windows usability with `vlp doctor`
- Split code into maintainable modules with shared logging and error handling
- Add minimal tests and Windows CI

## Non-Goals

- No web service layer in v1
- No GUI in v1
- No guarantee that every video platform will always download successfully
- No attempt to solve every anti-crawling edge case in v1

## Design Principles

- Preserve existing value while reducing coupling
- Prefer explicit contracts over implicit conventions
- Separate core capabilities from optional platform-specific workarounds
- Keep the CLI friendly for humans and the manifest stable for machines
- Default to Windows-friendly behavior without making the design Windows-only

## Packaging And Layout

Adopt a `src/` layout:

```text
.
├─ pyproject.toml
├─ src/
│  └─ video_link_pipeline/
│     ├─ __init__.py
│     ├─ cli.py
│     ├─ config.py
│     ├─ manifest.py
│     ├─ logging.py
│     ├─ errors.py
│     ├─ doctor.py
│     ├─ download/
│     │  ├─ __init__.py
│     │  ├─ service.py
│     │  ├─ diagnostics.py
│     │  ├─ yt_dlp_backend.py
│     │  ├─ selenium_fallback.py
│     │  └─ cookies.py
│     ├─ transcribe/
│     │  ├─ __init__.py
│     │  ├─ service.py
│     │  ├─ ffmpeg.py
│     │  ├─ faster_engine.py
│     │  └─ openai_engine.py
│     ├─ summarize/
│     │  ├─ __init__.py
│     │  ├─ service.py
│     │  └─ providers.py
│     └─ subtitles/
│        ├─ __init__.py
│        └─ convert.py
├─ tests/
└─ docs/
   └─ ARCHITECTURE.md
```

## CLI Design

Primary command:

```bash
vlp <command> [options]
```

### Commands

- `vlp download <url>`
- `vlp transcribe <path>`
- `vlp summarize <transcript.txt>`
- `vlp convert-subtitle <file-or-dir>`
- `vlp run <url>`
- `vlp doctor`

### CLI Rules

- Each subcommand must be independently usable
- `vlp run` is an orchestration command, not a replacement for the step commands
- CLI parameters override all other config sources
- Human-readable output is default; `--json` may be added later as a transport-friendly mode

### Naming Normalization

Normalize legacy naming where current scripts drift:

- `--cookies-from-browser` for browser cookie extraction
- `--cookie-file` for Netscape cookie files
- `--engine {auto,faster,openai}` for transcription engine selection
- `convert-subtitle` instead of raw script naming

Compatibility wrappers may still accept older names such as `--cookies` and map them internally.

## Compatibility Strategy

The current script filenames remain in the repository for v1:

- `download_video.py`
- `parallel_transcribe.py`
- `generate_summary.py`
- `convert_subtitle.py`

Each wrapper will:

- Parse the legacy arguments or a compatible subset
- Translate them into the new package API or CLI
- Emit a concise deprecation warning
- Preserve the existing exit code behavior as much as practical

Compatibility scope:

- Preserve common flags and core workflows
- Preserve existing default output locations where feasible
- Preserve common output file names when low risk
- Do not guarantee byte-for-byte identical console output
- Treat `manifest.json` as the new stable automation contract

## Configuration Model

### Precedence

Configuration precedence is:

1. CLI arguments
2. Environment variables, including values loaded from `.env`
3. `config.yaml`
4. Built-in defaults

### Canonical Schema

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

### Environment Variable Mapping

Project-specific environment variables should be explicit where practical:

- `VLP_OUTPUT_DIR`
- `VLP_TEMP_DIR`
- `VLP_DOWNLOAD_QUALITY`
- `VLP_DOWNLOAD_COOKIES_FROM_BROWSER`
- `VLP_DOWNLOAD_COOKIE_FILE`
- `VLP_DOWNLOAD_SELENIUM`
- `VLP_WHISPER_MODEL`
- `VLP_WHISPER_ENGINE`
- `VLP_WHISPER_LANGUAGE`
- `VLP_WHISPER_DEVICE`
- `VLP_WHISPER_COMPUTE_TYPE`
- `VLP_SUMMARY_ENABLED`
- `VLP_SUMMARY_PROVIDER`
- `VLP_SUMMARY_MODEL`
- `VLP_SUMMARY_BASE_URL`
- `VLP_SUMMARY_MAX_TOKENS`
- `VLP_SUMMARY_TEMPERATURE`

Provider keys continue to support standard ecosystem variables:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`
- `KIMI_API_KEY`
- `MOONSHOT_API_KEY`
- `MINIMAX_API_KEY`
- `GLM_API_KEY`
- `ZHIPU_API_KEY`

### Backward Compatibility

If legacy config is detected under `summary.api_keys.*`, the loader should:

- Merge those values into top-level `api_keys`
- Emit a migration warning
- Prefer the new top-level structure if both are present

### Validation

The configuration layer should:

- Apply defaults
- Validate enums and types
- Resolve paths
- Produce a redacted effective config snapshot for logs and manifests

## Output Model

### Job Directory

`output_dir` is treated as the output root, not the single-job directory.
Each command that creates artifacts should write into a job-specific folder.

Examples:

- `./output/my-video-title/`
- `./output/BV1xxxyyyzzz-my-video-title/`

This avoids collisions and makes `manifest.json` scoped to a single run target.

### Manifest

The stable machine-readable contract is `manifest.json` stored in the job directory.

Example:

```json
{
  "schema_version": "1.0",
  "created_at": "2026-04-10T12:34:56Z",
  "updated_at": "2026-04-10T12:40:10Z",
  "command": "vlp run",
  "input": {
    "url": "https://...",
    "input_path": null
  },
  "config_effective": {
    "output_dir": "./output",
    "download": {
      "subtitles_langs": ["zh", "en"],
      "audio_only": false,
      "selenium": "auto"
    },
    "whisper": {
      "model": "small",
      "engine": "auto"
    },
    "summary": {
      "enabled": true,
      "provider": "claude",
      "model": "claude-3-5-sonnet-20241022"
    }
  },
  "artifacts": {
    "folder": "my-video-title/",
    "video": "my-video-title/video.mp4",
    "audio": "my-video-title/audio.m4a",
    "subtitle_vtt": "my-video-title/subtitle.vtt",
    "subtitle_srt": "my-video-title/subtitle.srt",
    "transcript_txt": "my-video-title/transcript.txt",
    "summary_md": "my-video-title/summary.md",
    "keywords_json": "my-video-title/keywords.json"
  },
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
    },
    "transcribe": {
      "success": true,
      "detected_language": "zh",
      "error_code": null,
      "error": null,
      "warnings": []
    },
    "summarize": {
      "success": true,
      "provider": "claude",
      "error_code": null,
      "error": null,
      "warnings": []
    }
  }
}
```

### Manifest Rules

- Artifact paths are relative to `output_dir`
- Sensitive values must never be written verbatim
- The manifest must be incrementally mergeable across commands
- Writes should be atomic to avoid partial or corrupted files
- `execution.download` should preserve both human-readable `warnings` and structured `warning_details`
- `warning_details` should carry stable `code`, `stage`, `message`, and `description` fields for batch processing
- `execution.download.hint` should carry the best user-facing remediation available for the current failure path
- Selenium retry diagnostics should be represented with `fallback_status` and `fallback_context` rather than requiring log scraping
- If a command step fails after a job directory has been established, the latest step should still flush its manifest state before the CLI raises the terminal error
- The same early-flush rule applies to single-step commands such as `vlp transcribe` and `vlp summarize` once their output path has been resolved
- `vlp run` should preserve partial-success state instead of collapsing everything into a generic final status; the last successful or failed step remains visible through `command` and `execution.*`
- If a failed download result omits a specific `error_code`, manifest serialization should normalize it to `DOWNLOAD_FAILED`

### Download Diagnostics Contract

For v1, the download execution section should standardize on these additional fields:

- `fallback_status`: lifecycle state such as `not_attempted`, `triggered`, `dependency_missing`, `prepare_failed`, `retry_failed`, `prepared`, or `succeeded`
- `warning_details`: structured warning records for machine consumption
- `fallback_context.resolved_url`: the final browser URL
- `fallback_context.canonical_url`: the canonical or equivalent watch URL
- `fallback_context.media_hint_url`: the extracted media retry URL when available
- `fallback_context.site_name`: detected site name
- `fallback_context.extraction_source`: the source of the media hint, such as `next-data:playAddr` or `jsonld:contentUrl`

Representative warning codes include:

- `primary_http_403`
- `primary_captcha_required`
- `primary_auth_required`
- `browser_cookie_locked`
- `browser_driver_unavailable`
- `ffmpeg_unavailable`
- `fallback_context_prepared`
- `fallback_media_hint_missing`
- `fallback_dependency_hint`
- `fallback_prepare_hint`
- `fallback_retry_hint`

The same diagnostic code should remain reusable across three presentation layers:

- download manifest fields such as `execution.download.warning_details[].code`
- CLI diagnostic lines such as `download warning_code=<code> stage=<stage>: ...`
- doctor guidance/reference output derived from the shared diagnostics catalog

Recommended interpretation split:

- manifest `warning_details.code` is the stable machine-oriented key
- manifest `hint` is the best user-facing remediation for the current failure path
- CLI renders near-manifest field names for easier correlation during debugging
- doctor renders the same code catalog as environment/config guidance, but should separate currently active codes from passive reference codes

This allows new diagnostic codes to be added once in `video_link_pipeline.download.diagnostics` and then consumed consistently by:

- runtime download execution
- manifest serialization
- CLI rendering
- doctor guidance
- README and architecture documentation

### Download Execution Phases

The internal download flow should remain split into a small number of explicit phases so that
diagnostics, manifests, and future refactors can evolve without reworking the whole service:

1. `primary path`
   Runs the normal `yt-dlp` download flow, writes common preparation metadata, validates produced artifacts,
   and returns the success result when no anti-crawling or download failure is encountered.
2. `fallback prepare`
   Runs Selenium only after a qualifying failure, exports browser cookies, resolves the browser-derived retry URL,
   captures `fallback_context`, and emits preparation warnings such as `fallback_context_prepared` or
   `fallback_media_hint_missing`.
3. `fallback retry`
   Re-runs `yt-dlp` with browser-derived headers and cookie state, then records either `succeeded`,
   `retry_failed`, or a more specific dependency / prepare failure state when retry cannot proceed.

Phase boundaries should stay visible in code through small helpers so the following concerns remain isolated:

- primary success path and artifact normalization
- primary failure classification and warning generation
- fallback preparation state and context serialization
- fallback retry request preparation, execution, and final failure mapping

## Module Responsibilities

### `video_link_pipeline.cli`

- Defines the public CLI
- Parses arguments
- Resolves config overrides
- Maps domain errors to exit codes
- Renders download diagnostics with field names aligned to the manifest contract where practical, such as `download fallback_status`, `download error_code`, `download error_stage`, and `download warning_code`

### `video_link_pipeline.config`

- Loads `.env`, environment, and YAML
- Applies precedence and defaults
- Validates schema
- Produces redacted effective config snapshots

### `video_link_pipeline.manifest`

- Creates, reads, merges, and atomically writes `manifest.json`
- Knows how to update only a command-specific execution section

### `video_link_pipeline.errors`

- Defines domain exceptions and error codes
- Separates user-facing errors from internal trace details

### `video_link_pipeline.logging`

- Provides consistent CLI-friendly logging helpers
- Supports concise warnings and troubleshooting hints

### `video_link_pipeline.download`

- Encapsulates `yt-dlp` orchestration
- Handles cookie source selection
- Normalizes file names and output structure
- Detects likely anti-crawling failures
- Optionally invokes Selenium fallback
- Emits structured download diagnostics for manifest and CLI output
- Maintains the shared warning-code catalog used by download results, doctor guidance, and documentation
- Keeps the implementation organized around `primary path`, `fallback prepare`, and `fallback retry` helper boundaries

### `video_link_pipeline.transcribe`

- Selects FFmpeg
- Extracts audio when the input is a video
- Adapts to `faster-whisper` or `openai-whisper`
- Writes transcript and subtitle artifacts

### `video_link_pipeline.summarize`

- Loads transcript input
- Resolves provider and credentials
- Calls provider adapters
- Writes `summary.md` and `keywords.json`

### `video_link_pipeline.subtitles`

- Handles format conversion and batch conversion
- Remains pure and testable

### `video_link_pipeline.doctor`

- Performs environment diagnostics
- Reports availability and selected executable paths
- Groups output into `runtime`, `download prerequisites`, `effective download config`, and `config risks`
- Provides a compact effective download config summary line for quick inspection of the final selenium and cookies combination
- Prints a small built-in reference of common diagnostic codes and remediations, while suppressing codes already covered by current-check guidance to reduce duplicate output
- Shows the effective `download.selenium` mode directly in doctor output
- Shows the effective `download.cookies_from_browser` and `download.cookie_file` values directly in doctor output
- Checks risky download config combinations such as conflicting cookie sources
- Provides actionable remediation guidance
- Uses `WARN` for blocking conflicts and `INFO` for non-blocking but noteworthy config-risk items

Doctor output contract for v1 should stay stable enough for both humans and lightweight log parsing:

- `runtime`, `download prerequisites`, `effective download config`, and `config risks` should be rendered as explicit section headers
- successful checks in normal sections should render as `OK`
- failed checks should render as `WARN`
- successful checks in `config risks` should render as `INFO` rather than `OK`, because they represent advisory risk notes instead of passed health checks
- `common diagnostic guidance` should render only active diagnostic codes gathered from the current checks
- `known diagnostic codes` should render only the remaining built-in reference codes that were not already emitted in `common diagnostic guidance`
- duplicate diagnostic codes should be deduplicated in rendered guidance/reference output even if multiple checks carry the same code

## Dependency Strategy

### Core Dependencies

Expected default install set for v1:

- `yt-dlp`
- `pyyaml`
- `python-dotenv`
- `requests`
- `openai`
- `anthropic`
- `tqdm`
- `faster-whisper`
- `imageio-ffmpeg`

Notes:

- `imageio-ffmpeg` should be declared explicitly because the current code already relies on it
- `faster-whisper` stays in the default dependency set for v1 to preserve current capability and avoid changing the primary transcription path during the same refactor

### Optional Extras

- `video-link-pipeline[selenium]`
- `video-link-pipeline[dev]`

Recommended contents:

- `selenium`
- `webdriver-manager`

Dev extra may include:

- `build`
- `pytest`
- `ruff`
- `mypy`
- `pre-commit`

## FFmpeg Strategy

Resolution order:

1. System `ffmpeg`
2. `imageio-ffmpeg` executable

Requirements:

- The selected executable path should be shown by `vlp doctor`
- The selected executable should be reused consistently across download and transcription
- Do not depend on hard-coded machine-local fallback paths

## Selenium Strategy

Default mode:

```text
--selenium auto
```

Behavior:

- First attempt normal `yt-dlp` download
- If the failure looks like anti-crawling, cookies, verification, or unsupported short-video extraction, evaluate fallback
- If Selenium extra is not installed, emit a short actionable hint instead of a confusing traceback
- If Selenium extra is installed and mode allows it, attempt fallback extraction
- `vlp doctor` should also flag risky combinations such as `selenium=off` with no cookie source or both `cookies_from_browser` and `cookie_file` being set

Recommended internal phase mapping:

- `primary path`: probe, prepare download, execute `yt-dlp`, normalize artifacts
- `fallback prepare`: launch browser, derive retry headers/cookies/context, emit preparation warnings
- `fallback retry`: retry `yt-dlp` with browser-derived state, then classify dependency / prepare / retry failures

Supported values:

- `auto`
- `on`
- `off`

## `vlp run` Orchestration

`vlp run` should remain intentionally small in v1:

1. Download the URL
2. If subtitles are missing or transcription is explicitly requested, run transcription
3. If summary is enabled or explicitly requested, run summarization
4. Update `manifest.json` after each step

Design constraint:

- `vlp run` must orchestrate existing services rather than implement parallel bespoke logic

Implementation note:

- This command should land after the step commands and manifest merge logic are stable

## Error Model

The project should define stable error codes for major failure classes, for example:

- `CONFIG_ERROR`
- `INPUT_NOT_FOUND`
- `DEPENDENCY_MISSING`
- `DOWNLOAD_FAILED`
- `PLATFORM_RESTRICTED`
- `COOKIE_ACCESS_FAILED`
- `FFMPEG_NOT_FOUND`
- `TRANSCRIBE_FAILED`
- `SUMMARY_FAILED`
- `PROVIDER_AUTH_FAILED`

Each execution block in the manifest should record:

- `success`
- `error_code`
- `error`
- `warnings`

## Logging

CLI logs should be:

- Short by default
- Actionable on failure
- Consistent across subcommands

Avoid:

- Repeated low-level trace output in normal mode
- Provider or dependency jargon without explanation

Include:

- What is being attempted
- Where outputs are being written
- What fallback was used
- How to recover when a known failure happens
- Diagnostic field names that stay reasonably aligned with the manifest contract, so console output and machine-readable output are easier to correlate

## Testing Strategy

v1 minimum pytest coverage:

- Config precedence merging
- Legacy config compatibility merge
- Manifest incremental merge behavior
- Manifest atomic write behavior
- Subtitle conversion between VTT and SRT
- Output naming normalization
- Doctor dependency resolution helpers

Testing guidelines:

- Mock network and provider calls
- Avoid real downloads in unit tests
- Keep subtitle conversion tests pure and file-light
- Local development should use the same baseline commands as CI: `python -m ruff check .` and `python -m pytest`
- Installing the `dev` extra should be the documented way to obtain `pytest`, `ruff`, and other local verification tools
- Doctor tests should cover both dependency availability and configuration-risk reporting

## CI Strategy

Minimum GitHub Actions coverage:

- Windows runner
- Python 3.10 and 3.11
- `ruff`
- `pytest`

Recommended command alignment:

- Install dependencies with `python -m pip install -e .[dev]`
- Run dependency validation with `python -m pip check`
- Run syntax smoke checks with `python -m compileall src tests`
- Run lint with `python -m ruff check .`
- Run tests with `python -m pytest`
- Run packaging smoke checks with `python -m build`

Local troubleshooting guidance should stay aligned with these commands:

- missing `pytest`, `ruff`, or `build` modules should be treated first as a missing `dev` extra installation problem
- `pip check` failures should be documented as environment consistency problems before they are treated as project-code regressions
- Windows-specific docs should encourage checking `sys.executable` when users may have multiple Python interpreters installed

For Windows-first developer experience, the repo may also provide a small PowerShell helper such as `scripts/check.ps1` that:

- runs the same validation sequence as CI in a predictable order
- prints the active Python executable before running checks
- allows heavier steps such as `pytest` or `build` to be skipped explicitly during local iteration

Recommended follow-up:

- Add Ubuntu for early regression detection in pure Python paths

## Delivery Plan

### M1a: Foundation

- Add `pyproject.toml`
- Add `src/` package layout
- Introduce shared config, errors, logging, and manifest modules
- Add compatibility wrappers

### M1b: Command Migration

- Migrate `download`
- Migrate `transcribe`
- Migrate `summarize`
- Migrate `convert-subtitle`

### M1c: Stable Output Contract

- Add incremental `manifest.json`
- Normalize job-directory behavior
- Align docs with the actual config schema

### M2: Stabilization

- Add `vlp doctor`
- Add tests
- Add GitHub Actions on Windows
- Improve error codes and remediation text

### M3: Orchestration

- Add `vlp run`
- Finalize skip rules and manifest update flow

## Open Questions

- Whether `faster-whisper` should remain core or become an extra in a later version
- Whether `--json` should be standardized across all commands in v1 or delayed
- How aggressively wrappers should preserve legacy argument names versus emitting migration warnings
- Whether job directory naming should prefer title-only, ID-only, or `id-title`

## Recommendation

Proceed with the refactor.

The design is justified by the current repository state, but v1 should stay disciplined:

- Keep `manifest.json` scoped to a job directory
- Treat compatibility wrappers as a transition layer, not a permanent public API
- Land step commands before a full `run` orchestration command
- Fix config and dependency drift early so documentation, code, and packaging converge

## Implementation Backlog

This section expands M1a, M1b, and M1c into a concrete delivery checklist.
Tasks are intentionally small enough to become GitHub issues or short-lived PRs.

### M1a: Foundation

#### M1a-1 Package metadata and install entry

Scope:

- Add `pyproject.toml`
- Define package metadata, Python version range, dependencies, and optional extras
- Register console entry point `vlp = video_link_pipeline.cli:app` or equivalent
- Keep `requirements.txt` only if needed temporarily during migration

Deliverables:

- `pyproject.toml`
- Installable local package via `pip install -e .`
- Working `vlp --help`

Acceptance criteria:

- `pip install -e .` succeeds on Windows
- `vlp --help` executes without import errors
- Core dependencies and extras are declared explicitly
- `imageio-ffmpeg` is declared in packaging metadata

Dependencies:

- None

#### M1a-2 Source tree scaffolding

Scope:

- Add `src/video_link_pipeline/`
- Add package modules and subpackages defined in this architecture doc
- Add empty or minimal `__init__.py` files
- Add a placeholder CLI skeleton with no-op subcommands or stub implementations

Deliverables:

- `src/video_link_pipeline/cli.py`
- `src/video_link_pipeline/config.py`
- `src/video_link_pipeline/manifest.py`
- `src/video_link_pipeline/errors.py`
- `src/video_link_pipeline/logging.py`
- Subpackage directories for `download`, `transcribe`, `summarize`, `subtitles`

Acceptance criteria:

- Package imports cleanly
- CLI command tree exists for all v1 subcommands
- The repository no longer depends on top-level scripts as the only execution path

Dependencies:

- M1a-1

#### M1a-3 Shared error model

Scope:

- Introduce domain exception classes
- Define stable error codes
- Add mapping from domain errors to CLI exit behavior
- Add helpers for user-facing messages versus internal detail

Deliverables:

- `video_link_pipeline.errors`
- Initial error code catalog

Acceptance criteria:

- At least the documented v1 error classes exist in code
- CLI can raise a domain error and print a concise, user-oriented message
- Internal callers can attach `error_code` and `message` to manifest updates

Dependencies:

- M1a-2

#### M1a-4 Shared logging helpers

Scope:

- Add consistent logging helpers for info, warning, success, and failure output
- Centralize formatting conventions for CLI output
- Avoid embedding ad hoc `print()` messaging in new modules

Deliverables:

- `video_link_pipeline.logging`
- Shared user-facing output helpers

Acceptance criteria:

- New CLI modules use shared logging helpers instead of custom message formatting
- A consistent format exists for warnings, remediation hints, and success output

Dependencies:

- M1a-2

#### M1a-5 Unified configuration loader

Scope:

- Implement config loading from defaults, YAML, `.env`, and environment variables
- Apply precedence rules
- Validate enums and value types
- Add backward compatibility merge for `summary.api_keys`
- Add redaction for secret-bearing config snapshots

Deliverables:

- `video_link_pipeline.config`
- Canonical config schema representation
- Effective-config serialization helper

Acceptance criteria:

- CLI overrides beat env and YAML
- `.env` values are loaded once centrally
- Legacy `summary.api_keys` is merged with a warning
- Invalid enum values fail fast with a clear error

Dependencies:

- M1a-2
- M1a-3

#### M1a-6 Manifest core

Scope:

- Implement manifest create, load, merge, and atomic write helpers
- Support step-wise updates from different commands
- Redact sensitive config from stored effective config

Deliverables:

- `video_link_pipeline.manifest`
- Atomic write helper
- Merge semantics for `input`, `artifacts`, and `execution`

Acceptance criteria:

- Repeated updates do not erase unrelated manifest sections
- Writes are atomic from the caller perspective
- Manifest file can be created before all artifacts exist

Dependencies:

- M1a-3
- M1a-5

#### M1a-7 Compatibility wrapper strategy

Scope:

- Convert top-level scripts into wrappers over package APIs or CLI dispatch
- Preserve common legacy flags and exit behavior where practical
- Emit concise deprecation warnings

Deliverables:

- Updated `download_video.py`
- Updated `parallel_transcribe.py`
- Updated `generate_summary.py`
- Updated `convert_subtitle.py`

Acceptance criteria:

- Existing script filenames still run
- Common legacy commands still work or fail with actionable migration messaging
- Wrapper logic is thin and does not duplicate business logic

Dependencies:

- M1a-2
- M1a-5

### M1b: Command Migration

#### M1b-1 Subtitle conversion module extraction

Scope:

- Move VTT/SRT logic into `video_link_pipeline.subtitles.convert`
- Keep behavior parity with current conversion rules
- Add clean service functions for single-file and batch conversion

Deliverables:

- New subtitles conversion module
- `vlp convert-subtitle`
- Wrapper delegation from `convert_subtitle.py`

Acceptance criteria:

- Single-file conversion works in both directions
- Batch conversion works on a directory
- CLI exit codes match success or failure status

Dependencies:

- M1a-2
- M1a-4
- M1a-7

#### M1b-2 Download service extraction

Scope:

- Move yt-dlp orchestration into `video_link_pipeline.download`
- Extract cookie argument normalization
- Preserve file standardization and output naming behavior
- Remove machine-local FFmpeg assumptions from the new path

Deliverables:

- `download/service.py`
- `download/yt_dlp_backend.py`
- `download/cookies.py`
- `vlp download`

Acceptance criteria:

- `vlp download <url>` produces the same core artifacts as the legacy script
- `--cookies-from-browser` and `--cookie-file` are supported explicitly
- Legacy `--cookies` is accepted by the wrapper and mapped internally
- Download result can be represented as structured data without scraping console output

Dependencies:

- M1a-5
- M1a-6
- M1a-7

#### M1b-3 Selenium fallback extraction

Scope:

- Move Selenium fallback into `download/selenium_fallback.py`
- Gate execution by `--selenium {auto,on,off}` and optional dependency availability
- Replace raw import failures with actionable hints

Deliverables:

- `download/selenium_fallback.py`
- Fallback decision helper
- Dependency detection helper for Selenium mode

Acceptance criteria:

- Fallback only runs when mode permits it
- Missing Selenium extras do not produce a raw traceback
- Fallback usage is exposed in structured execution results

Dependencies:

- M1b-2

#### M1b-4 Transcription service extraction

Scope:

- Move transcription logic into `video_link_pipeline.transcribe`
- Normalize engine names to `auto`, `faster`, `openai`
- Extract audio-from-video logic into a reusable helper
- Centralize FFmpeg resolution

Deliverables:

- `transcribe/service.py`
- `transcribe/ffmpeg.py`
- `transcribe/faster_engine.py`
- `transcribe/openai_engine.py`
- `vlp transcribe`

Acceptance criteria:

- File input and directory input both work
- Video input triggers audio extraction before transcription
- Engine normalization supports legacy wrapper names
- Structured result contains transcript path, subtitle paths, detected language, and errors

Dependencies:

- M1a-5
- M1a-6
- M1a-7

#### M1b-5 Summary service extraction

Scope:

- Move provider-specific summary logic into `video_link_pipeline.summarize`
- Centralize provider resolution, API key lookup, and output writing
- Preserve current provider coverage in v1 where possible

Deliverables:

- `summarize/service.py`
- `summarize/providers.py`
- `vlp summarize`

Acceptance criteria:

- Provider and model can be resolved from config or CLI overrides
- API keys are resolved from unified config/env loading
- `summary.md` and `keywords.json` are written consistently
- Structured result reports provider, outputs, and errors

Dependencies:

- M1a-5
- M1a-6
- M1a-7

#### M1b-6 CLI integration pass

Scope:

- Wire all migrated services into the unified CLI
- Normalize help text, option names, and defaults
- Ensure command-level errors map to exit codes consistently

Deliverables:

- Fully wired `vlp` CLI for `download`, `transcribe`, `summarize`, `convert-subtitle`

Acceptance criteria:

- `vlp --help` shows all v1 commands
- `vlp <subcommand> --help` is available for each migrated subcommand
- Common workflows no longer require direct invocation of top-level scripts

Dependencies:

- M1b-1
- M1b-2
- M1b-3
- M1b-4
- M1b-5

### M1c: Stable Output Contract

#### M1c-1 Job directory normalization

Scope:

- Formalize the distinction between output root and job directory
- Add helper logic for deriving job folder names
- Reconcile legacy folder naming with the new strategy

Deliverables:

- Shared job-directory helper
- Stable job path contract used by download, transcribe, and summarize

Acceptance criteria:

- Artifacts for one logical job land in one predictable folder
- Multiple runs do not overwrite each other unintentionally
- Relative artifact paths can be computed consistently for manifest storage

Dependencies:

- M1b-2
- M1b-4
- M1b-5

#### M1c-2 Manifest integration for `download`

Scope:

- Create or update `manifest.json` after download
- Record input URL, effective download config, artifacts, and execution status

Deliverables:

- Manifest update in `vlp download`

Acceptance criteria:

- Successful download writes download artifacts and execution status
- Failed download writes failure status and error code when job directory exists
- Sensitive config values are not written verbatim

Dependencies:

- M1a-6
- M1c-1

#### M1c-3 Manifest integration for `transcribe`

Scope:

- Create or update `manifest.json` after transcription
- Record input path, effective whisper config, transcript artifacts, and detected language

Deliverables:

- Manifest update in `vlp transcribe`

Acceptance criteria:

- Running transcription after download supplements the same manifest instead of replacing it
- Transcript and subtitle outputs are recorded with relative paths
- Errors and detected language are persisted in execution metadata

Dependencies:

- M1a-6
- M1c-1
- M1b-4

#### M1c-4 Manifest integration for `summarize`

Scope:

- Create or update `manifest.json` after summarization
- Record summary provider, output files, and execution status

Deliverables:

- Manifest update in `vlp summarize`

Acceptance criteria:

- Running summarize after download/transcribe supplements the same manifest
- `summary.md` and `keywords.json` appear under `artifacts`
- Provider and summary status appear under `execution.summarize`

Dependencies:

- M1a-6
- M1c-1
- M1b-5

#### M1c-5 Effective config snapshot and redaction pass

Scope:

- Finalize what goes into `config_effective`
- Redact secrets and secret-adjacent values
- Ensure each command stores a reproducible but safe config snapshot

Deliverables:

- Shared manifest-config serializer
- Redaction tests or verification cases

Acceptance criteria:

- API keys and similar secrets are redacted or omitted
- Relevant non-secret command options remain visible for reproducibility
- Repeated command runs do not produce conflicting schema shapes

Dependencies:

- M1a-5
- M1a-6
- M1c-2
- M1c-3
- M1c-4

#### M1c-6 Documentation alignment pass

Scope:

- Update `README.md` and `README.en.md`
- Replace script-first examples with `vlp` examples
- Document compatibility wrappers and migration notes
- Align config examples with the canonical schema

Deliverables:

- Updated README files
- Migration notes for legacy script users

Acceptance criteria:

- README command examples match actual CLI names and options
- Config examples match the implemented schema
- Legacy wrapper support and deprecation direction are documented clearly

Dependencies:

- M1b-6
- M1c-5

### Suggested PR Sequencing

Recommended implementation order:

1. M1a-1, M1a-2
2. M1a-3, M1a-4, M1a-5
3. M1a-6, M1a-7
4. M1b-1, M1b-2, M1b-4, M1b-5
5. M1b-3, M1b-6
6. M1c-1, M1c-2, M1c-3, M1c-4
7. M1c-5, M1c-6

### Suggested Issue Labels

Useful labels for backlog tracking:

- `milestone:m1a`
- `milestone:m1b`
- `milestone:m1c`
- `area:packaging`
- `area:config`
- `area:manifest`
- `area:download`
- `area:transcribe`
- `area:summarize`
- `area:subtitles`
- `type:refactor`
- `type:docs`
- `type:infra`
- `type:compat`
