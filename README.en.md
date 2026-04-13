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

Quick verification:

```bash
vlp --help
vlp doctor
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
- `warnings`: trigger reason, dependency hints, and context-preparation notes
- `fallback_context.resolved_url`: the final browser URL
- `fallback_context.canonical_url`: the canonical page URL when available
- `fallback_context.media_hint_url`: the preferred media URL extracted from page signals
- `fallback_context.site_name`: the detected site name
- `fallback_context.extraction_source`: where the media hint came from, such as `next-data:playAddr` or `jsonld:contentUrl`

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
