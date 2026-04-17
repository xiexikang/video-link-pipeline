# Commands Reference

Use this reference to choose the smallest correct `vlp` command for the user's goal.

## Primary Rule

Choose commands based on the user's real outcome:

- If the user wants text content, do not default to full media download.
- If the user already has local media, skip link download and go straight to transcription.
- If the user already has `transcript.txt`, skip transcription and go straight to summarization.
- If the user only needs subtitle format compatibility, use subtitle conversion instead of rerunning the whole pipeline.

Prefer existing artifacts over regenerating work.

## Command Map

### `vlp download <url>`

Use when the user needs one or more of these:

- local video file
- local audio file
- original subtitles
- normalized job directory for a remote video URL

Do not prefer this command when subtitles or transcript are the only real goal and full media download is unnecessary.

### `vlp download-subs <url>`

Use when the user mainly wants:

- subtitles
- metadata
- text-oriented downstream processing
- a lighter entry point for sites where full media download may be restricted

Prefer this command over `vlp download` when content extraction matters more than media retention.

### `vlp transcribe <path>`

Use when the user already has local input such as:

- a video file
- an audio file
- a downloaded job directory

This command is also appropriate after a download step if subtitles are missing or low quality.

### `vlp summarize <transcript.txt>`

Use when the user already has a transcript and wants:

- `summary.md`
- `keywords.json`
- a faster reading layer over long transcript text

Do not use this command unless transcript input already exists or is generated first.

### `vlp convert-subtitle <file-or-dir>`

Use when the user's problem is only subtitle format mismatch.

Prefer this command over re-download or re-transcribe when subtitle content is already present and only the format is wrong.

### `vlp run <url>`

Use when the user explicitly wants an orchestrated end-to-end workflow.

If the task is clearly only one stage, prefer the narrower command.

### `vlp doctor`

Use before or during troubleshooting when the issue may involve:

- Python runtime mismatch
- FFmpeg availability
- Selenium extra availability
- browser cookies configuration
- conflicting download config
- confusing environment-dependent failures

## Workflow Patterns

### Pattern: remote URL to local media

Prefer:

```bash
vlp download "<url>"
```

### Pattern: remote URL to subtitle-first text workflow

Prefer:

```bash
vlp download-subs "<url>"
```

### Pattern: local file to transcript

Prefer:

```bash
vlp transcribe "<path>"
```

### Pattern: transcript to summary

Prefer:

```bash
vlp summarize "<transcript.txt>"
```

### Pattern: one command for the whole flow

Prefer:

```bash
vlp run "<url>" --do-summary
```

### Pattern: diagnose before retry

Prefer:

```bash
vlp doctor
```

## Reuse Rules

Before choosing a command, check whether these files already exist:

- `transcript.txt`
- `summary.md`
- `keywords.json`
- subtitle files
- `manifest.json`

If they exist, prefer continuing from the latest successful artifact instead of restarting the whole flow.

## Selection Heuristics

Use these quick rules:

- "I want the content/text" -> prefer `download-subs`, `transcribe`, or `summarize`
- "I want the video/audio files" -> prefer `download`
- "I already have a local file" -> prefer `transcribe`
- "I already have transcript text" -> prefer `summarize`
- "I want one pipeline command" -> prefer `run`
- "Something failed and I am not sure why" -> prefer `doctor` plus manifest inspection

## Notes

Prefer the unified `vlp` CLI over legacy wrapper scripts unless the user explicitly asks about backward compatibility.

When a job folder already exists, inspect its outputs and `manifest.json` before rerunning expensive work.
