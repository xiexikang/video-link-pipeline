# Skill Test Cases

Use this reference to manually test whether the `video-link-pipeline` skill is discovered correctly and applies the intended workflow guidance.

Focus on behavior, not style. The skill is working well when it consistently chooses the right `vlp` command, prioritizes `manifest.json` and `vlp doctor`, and treats the repository as a content-processing pipeline rather than only a downloader.

## How To Run The Tests

Start a fresh session when possible so the model reloads the globally installed skill.

Prefer explicit invocation during testing:

```text
Use $video-link-pipeline ...
```

For each case, check:

- whether the skill is clearly being used
- whether the recommended command is correct
- whether the answer aligns with this repository's current CLI and manifest model
- whether the answer avoids falling back to outdated wrapper scripts unless explicitly asked

## Acceptance Signals

Treat these as positive signals:

- recommends `vlp` subcommands instead of legacy wrappers
- chooses the smallest command that matches the goal
- treats `manifest.json` as the primary job-state source
- treats `vlp doctor` as the first-class environment and diagnostics entry point
- recommends reusing existing outputs when appropriate
- describes the project as a pipeline for reusable content assets

Treat these as negative signals:

- defaults to full download when the user only wants text
- ignores `manifest.json`
- ignores `vlp doctor` during troubleshooting
- suggests rerunning the whole flow when reuse is possible
- describes the project as only a downloader

## Test Case 1: Subtitle-First Remote Workflow

Prompt:

```text
Use $video-link-pipeline. I have a video URL and mainly want subtitles or text for later summarization. I do not care about keeping the video file. Which command should I use?
```

Expected behavior:

- prefers `vlp download-subs <url>`
- explains why subtitle-first flow is more appropriate than full media download
- frames the goal as content extraction

## Test Case 2: Full Remote Download

Prompt:

```text
Use $video-link-pipeline. I want the local video, audio, and any available subtitles from a remote video URL. Which command fits best?
```

Expected behavior:

- prefers `vlp download <url>`
- may mention normalized job directory output
- does not redirect to `download-subs`

## Test Case 3: Local Media To Transcript

Prompt:

```text
Use $video-link-pipeline. I already have a local mp4 file and only need transcript output and Whisper subtitles. What should I run?
```

Expected behavior:

- prefers `vlp transcribe <path>`
- explicitly skips download because local media already exists

## Test Case 4: Transcript To Summary

Prompt:

```text
Use $video-link-pipeline. I already have transcript.txt and only want a summary and keywords. What should I run next?
```

Expected behavior:

- prefers `vlp summarize <transcript.txt>`
- does not suggest rerunning transcription

## Test Case 5: Subtitle Format Conversion

Prompt:

```text
Use $video-link-pipeline. I already have subtitle.vtt but another tool only accepts srt. What is the right command?
```

Expected behavior:

- prefers `vlp convert-subtitle`
- does not suggest redownloading or retranscribing

## Test Case 6: End-To-End Workflow

Prompt:

```text
Use $video-link-pipeline. I want one command that downloads a remote video, then produces transcript and summary artifacts if needed. What should I use?
```

Expected behavior:

- prefers `vlp run <url>` with the relevant flags
- explains that this is the orchestrated path
- does not use a step command as the main answer

## Test Case 7: Manifest-Led Troubleshooting

Prompt:

```text
Use $video-link-pipeline. I already have a job folder with manifest.json. How should I determine which pipeline stage failed?
```

Expected behavior:

- tells the user to inspect `manifest.json` first
- points to `execution.download`, `execution.transcribe`, and `execution.summarize`
- treats the manifest as the primary source of truth

## Test Case 8: Download 403 Failure

Prompt:

```text
Use $video-link-pipeline. My download failed with HTTP 403. What should I inspect first in this repository's workflow?
```

Expected behavior:

- mentions auth, anti-bot, cookies, or Selenium fallback
- recommends checking manifest warning codes or hints
- recommends `vlp doctor` when environment or config may contribute

## Test Case 9: Environment Diagnostics

Prompt:

```text
Use $video-link-pipeline. I am not sure whether my environment is broken or the site itself is failing. What should I run first?
```

Expected behavior:

- prefers `vlp doctor`
- mentions FFmpeg, Selenium, cookies, or config risks

## Test Case 10: Existing Transcript Reuse

Prompt:

```text
Use $video-link-pipeline. The job folder already contains transcript.txt. Should I rerun transcription or continue from the existing file?
```

Expected behavior:

- recommends reuse by default
- explains that summary can continue from existing transcript
- may mention `reused_existing` semantics in manifest-aware flows

## Test Case 11: Config Precedence

Prompt:

```text
Use $video-link-pipeline. Explain how this repository resolves config between CLI arguments, .env, config.yaml, and defaults.
```

Expected behavior:

- states the precedence correctly
- explains effective config rather than only raw YAML

## Test Case 12: Legacy Wrapper Guardrail

Prompt:

```text
Use $video-link-pipeline. Which command should I use for summary generation in this repository?
```

Expected behavior:

- recommends `vlp summarize`
- does not default to `generate_summary.py`
- may mention wrappers only as compatibility paths

## Stretch Cases

Use these when you want deeper confidence.

### Mixed-Stage Failure Interpretation

Prompt:

```text
Use $video-link-pipeline. The manifest shows download success and transcribe success, but summarize failed. How should I continue?
```

Expected behavior:

- treats this as partial success
- avoids restarting download or transcription
- continues from summary-stage diagnosis

### Cookie Conflict Interpretation

Prompt:

```text
Use $video-link-pipeline. Both cookies_from_browser and cookie_file are set. Is that a good idea in this project?
```

Expected behavior:

- identifies it as a risky or conflicting setup
- recommends using one cookie source, not both

### Fallback Context Interpretation

Prompt:

```text
Use $video-link-pipeline. The manifest says fallback_status=retry_failed and includes fallback_context.extraction_kind=window_state. What does that usually mean?
```

Expected behavior:

- explains that structured cues were found
- explains that retry still failed
- points toward site-specific extraction quality, cookies, or final retry conditions

## Regression Checklist

Re-run at least these cases after changing the skill:

- Test Case 1
- Test Case 4
- Test Case 7
- Test Case 8
- Test Case 9
- Test Case 11

If these still behave correctly, the skill usually remains aligned with the intended workflow.
