# Manifest Reference

Use this reference to inspect `manifest.json` as the primary machine-readable status record for a pipeline job.

Do not guess workflow state from filenames or CLI text alone when `manifest.json` is available.

## Primary Purpose

Treat `manifest.json` as the best source for:

- what input was processed
- which command last updated the job
- which artifacts were produced
- which stage failed
- whether fallback was used
- which effective config was applied
- whether existing outputs were reused

## First Fields To Check

When reading a manifest, inspect these sections first:

1. `command`
2. `input`
3. `artifacts`
4. `execution`
5. `config_effective`

## `command`

`command` shows which CLI step last wrote the manifest.

Common values include:

- `vlp download`
- `vlp download-subs`
- `vlp transcribe`
- `vlp summarize`
- `vlp run`

## `input`

`input` shows what the job was created from.

Common fields:

- `input.url`
- `input.input_path`

## `artifacts`

`artifacts` shows what concrete outputs exist for the job.

Important fields may include:

- `folder`
- `video`
- `audio`
- `subtitle_vtt`
- `subtitle_srt`
- `info_json`
- `transcript_txt`
- `transcript_json`
- `summary_md`
- `keywords_json`

Treat artifact presence as evidence that the file path was produced or registered by a step. Still verify on disk if a later task depends on the file being physically present.

## `execution`

`execution` is the most important diagnostic block.

Check these step sections:

- `execution.download`
- `execution.transcribe`
- `execution.summarize`

Read them independently. A later step may fail while earlier steps succeeded.

## `execution.download`

Use this block to inspect download state.

Common fields:

- `success`
- `used_selenium_fallback`
- `fallback_status`
- `error_code`
- `error`
- `hint`
- `warnings`
- `warning_details`
- `fallback_context`

Look at `success`, `error_code`, `hint`, `warning_details`, `fallback_status`, and `fallback_context` first.

## `warning_details`

`warning_details` is the structured diagnostic list for download problems.

Prefer this field over plain warning text when available.

Each warning record may contain:

- `code`
- `stage`
- `message`
- `description`

## `fallback_context`

`fallback_context` helps interpret Selenium-based retry behavior.

Common fields:

- `resolved_url`
- `canonical_url`
- `media_hint_url`
- `site_name`
- `extraction_source`
- `extraction_kind`

Use this block when fallback was prepared or attempted.

## `execution.transcribe`

Use this block to inspect transcription state.

Common fields:

- `success`
- `detected_language`
- `engine`
- `reused_existing`
- `error_code`
- `error`
- `warnings`

Do not treat `reused_existing=true` as a missing step. It means reuse was intentional.

## `execution.summarize`

Use this block to inspect summary state.

Common fields:

- `success`
- `provider`
- `reused_existing`
- `error_code`
- `error`
- `warnings`

## Partial Success Interpretation

A job may contain mixed status across stages.

Do not collapse these states into a single overall success or failure judgment. Read each stage separately.

## `config_effective`

`config_effective` shows the resolved configuration used for the recorded step.

Treat `config_effective` as the final resolved config snapshot, not merely the contents of `config.yaml`.

## Practical Rule

When available, `manifest.json` should drive the next action:

- continue from the latest successful artifact
- inspect the specific failed stage
- avoid restarting the entire pipeline without reason
