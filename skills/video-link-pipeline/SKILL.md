---
name: video-link-pipeline
description: End-to-end local CLI workflow for the video-link-pipeline project. Use when Codex needs to choose commands, run the pipeline, inspect manifest.json outputs, diagnose environment or download failures, or explain how this repository converts video links and local media into subtitles, transcripts, summaries, and reusable content assets.
---

# video-link-pipeline

Use this skill when working inside the `video-link-pipeline` repository.

Treat this project as a local content-processing pipeline, not only as a downloader. The main goal is to turn video links or local media into reusable outputs such as subtitles, transcripts, summaries, keywords, and machine-readable job state.

Prefer the unified `vlp` CLI over legacy wrapper scripts unless the user explicitly asks about backward compatibility.

## Default Approach

- Prefer the smallest command that solves the user's goal instead of always using the full pipeline.
- Prefer reading existing outputs before regenerating work.
- Prefer `manifest.json` as the primary status record for a job.
- Prefer `vlp doctor` when the failure may involve environment, FFmpeg, Selenium, browser cookies, or conflicting download settings.

## Command Selection

Use these rules first:

- Use `vlp download-subs <url>` when subtitles and metadata are enough, especially if the user mainly wants text extraction and the site may restrict media download.
- Use `vlp download <url>` when the user needs downloaded media artifacts such as video, audio, or original subtitles.
- Use `vlp transcribe <path>` when the input is local media or when downloaded content lacks usable subtitles.
- Use `vlp summarize <transcript.txt>` when a transcript already exists and the user wants summary or keywords.
- Use `vlp convert-subtitle <file-or-dir>` when the main issue is subtitle format compatibility.
- Use `vlp run <url>` when the user explicitly wants one orchestrated workflow from link to final artifacts.
- Use `vlp doctor` before troubleshooting environment-dependent failures or confusing download problems.

## Working Style

- Reuse existing `transcript.txt` or `summary.md` when present instead of regenerating them unnecessarily.
- Read the job directory before making assumptions about missing steps.
- Check whether the user needs video files, subtitles only, transcript only, or transcript plus summary.
- Keep command choice aligned with the user's real goal: content extraction, not download for its own sake.

## Output Model

Expect each job to produce a dedicated output folder.

Important outputs usually include:

- `video.mp4`
- `audio.m4a`
- `subtitle.vtt`
- `subtitle.srt`
- `transcript.txt`
- `transcript.json`
- `summary.md`
- `keywords.json`
- `manifest.json`

Treat `manifest.json` as the stable machine-readable contract for job status, artifacts, effective config, and step-level execution results.

## Troubleshooting Order

When a workflow fails, follow this order:

1. Read `manifest.json` if it exists.
2. Identify the failing stage from `execution.download`, `execution.transcribe`, or `execution.summarize`.
3. Check whether outputs already exist and can be reused.
4. Run or inspect `vlp doctor` for environment and configuration issues.
5. For download failures, pay special attention to cookies, Selenium fallback, FFmpeg availability, and warning codes.

Do not guess blindly from CLI text when manifest diagnostics are available.

## Manifest Guidance

Focus on these fields first:

- `artifacts.*` to see what was actually produced
- `execution.download.*` to inspect download success, fallback usage, error code, hint, and warnings
- `execution.transcribe.*` to inspect transcription success and reuse status
- `execution.summarize.*` to inspect summary success and reuse status
- `config_effective` to understand the resolved configuration that was actually used

If the manifest records `reused_existing=true`, treat that as an intentional skip rather than a missing step.

## Diagnostics Guidance

- The repository uses shared warning and remediation codes for download diagnostics.
- Common areas to inspect first are browser cookies unavailable or locked, Selenium extra or browser driver unavailable, FFmpeg unavailable, authentication-related failures, and fallback prepared successfully but without a direct media hint.
- Use `vlp doctor` and the manifest together. Prefer the repository's structured diagnostics over ad hoc interpretations.

## References

Read additional references only when needed:

- Read `references/commands.md` for command choice and workflow examples.
- Read `references/manifest.md` for field-level manifest interpretation.
- Read `references/diagnostics.md` for warning codes, fallback states, and remediation logic.
- Read `references/config.md` for config precedence, key settings, and common conflicts.
