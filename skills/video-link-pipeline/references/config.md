# Config Reference

Use this reference to understand configuration precedence, key settings, and common conflicts in the `video-link-pipeline` repository.

Treat the effective runtime config as the combination of defaults, `config.yaml`, `.env` or environment variables, and CLI overrides.

## Precedence

Configuration precedence is:

1. CLI arguments
2. environment variables and `.env`
3. `config.yaml`
4. built-in defaults

When explaining actual runtime behavior, prefer the resolved effective config over the raw `config.yaml` file.

## Main Config Areas

The main config groups are:

- root-level output settings
- `download`
- `whisper`
- `summary`
- `api_keys`

## Root Settings

Common root settings include:

- `output_dir`
- `group_output_by_site`
- `temp_dir`

### `output_dir`

This is the output root, not a single job folder.

### `group_output_by_site`

When enabled, downloaded jobs are grouped under a site bucket such as `bilibili/` or `youtube/`.

## Download Config

Important `download` fields include:

- `quality`
- `format`
- `subtitles_langs`
- `write_subtitles`
- `write_auto_subs`
- `cookies_from_browser`
- `cookie_file`
- `selenium`

### `cookies_from_browser`

This configures browser-based cookie extraction.

Common example values:

- `chrome`
- `edge`
- `firefox`

### `cookie_file`

This configures a Netscape-format cookies file.

### `selenium`

Supported values:

- `auto`
- `on`
- `off`

Interpret them like this:

- `auto` attempts browser fallback only after qualifying failures.
- `on` allows browser fallback aggressively after qualifying failures.
- `off` never uses Selenium fallback.

## Whisper Config

Important `whisper` fields include:

- `model`
- `engine`
- `language`
- `device`
- `compute_type`

### `engine`

Supported values:

- `auto`
- `faster`
- `openai`

### `device`

Supported values:

- `auto`
- `cpu`
- `cuda`

### `compute_type`

Supported values:

- `int8`
- `float16`
- `float32`

## Summary Config

Important `summary` fields include:

- `enabled`
- `provider`
- `model`
- `base_url`
- `max_tokens`
- `temperature`

## API Keys

API credentials are represented under `api_keys`.

Interpretation rule:

- API keys are sensitive.
- They should be redacted in logs and manifests.
- Missing keys can explain summary-provider failures.

## Environment Variables

Common examples include:

- `VLP_OUTPUT_DIR`
- `VLP_GROUP_OUTPUT_BY_SITE`
- `VLP_DOWNLOAD_COOKIES_FROM_BROWSER`
- `VLP_DOWNLOAD_COOKIE_FILE`
- `VLP_DOWNLOAD_SELENIUM`
- `VLP_WHISPER_MODEL`
- `VLP_WHISPER_ENGINE`
- `VLP_SUMMARY_PROVIDER`
- `VLP_SUMMARY_MODEL`

Provider keys may also come from standard variables such as:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `DEEPSEEK_API_KEY`

## Common Config Conflicts

These are the most important conflict patterns to watch for:

### Both `cookies_from_browser` and `cookie_file` set

- This is usually a bad combination.
- Prefer one cookie source, not both.

### `selenium=off` with no cookie source

- This is risky for sites that need login, anti-bot bypass, or browser-assisted retry.

### Browser cookies configured but browser unavailable or locked

- Browser-based cookie extraction may fail even if the config looks correct.

### Missing summary provider key

- Download and transcription may succeed while summary fails later because provider auth is unavailable.

## Effective Config Interpretation

When available, use the effective config snapshot rather than guessing from scattered files.

Typical sources of truth include:

- CLI arguments provided for the current command
- `config_effective` recorded in `manifest.json`
- `vlp doctor` effective download config output

## Final Rule

Do not explain pipeline behavior from `config.yaml` alone.

Always reason from effective config:
CLI > environment > `config.yaml` > defaults
