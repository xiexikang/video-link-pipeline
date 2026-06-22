# video-link-pipeline

`video-link-pipeline` is a local video-processing toolkit for turning a video URL or local media file into a reusable set of artifacts:

- download video, audio, subtitles, and metadata
- generate transcripts and subtitles with Whisper
- generate summaries and keywords with LLMs
- keep task state in `manifest.json`

It can be used as a CLI and also includes a local Web workspace for running and reviewing download, transcription, and summary jobs on your own machine.

Chinese documentation is available in [README.md](G:\www-xxk\video-link-pipeline\README.md).

## What It Is Good For

- pulling Bilibili, YouTube, and similar content into a local workflow
- turning videos into `transcript.txt`, `subtitle.srt`, and `summary.md`
- keeping stable task folders and machine-readable state files
- reviewing task progress, logs, and artifacts in a local web UI

## Current Commands

- `vlp download <url>`: download media, subtitles, and metadata
- `vlp download-subs <url>`: download subtitles and metadata only
- `vlp transcribe <path>`: transcribe a local video or audio file
- `vlp summarize <transcript.txt>`: generate a summary and keywords
- `vlp convert-subtitle <file-or-dir>`: convert between `srt` and `vtt`
- `vlp run <url>`: chain download, transcription, and summary
- `vlp cookies-login <url>`: open a dedicated browser window for login and export `cookies.txt`
- `vlp doctor`: inspect Python, FFmpeg, Selenium, cookies, and related setup

## Quick Start

### 1. Install

Requirements:

- Python 3.10+
- Windows, Linux, or macOS

Recommended installation:

```bash
git clone <repository_url>
cd video-link-pipeline
pip install -e .
```

If you need Selenium-based browser fallback:

```bash
pip install -e .[selenium]
```

If you are contributing locally:

```bash
pip install -e .[dev]
```

Verify the CLI is available:

```bash
vlp --help
vlp doctor
```

### 2. Run a Minimal Flow

Download only:

```bash
vlp download "https://www.bilibili.com/video/BV..."
```

Full pipeline:

```bash
vlp run "https://www.bilibili.com/video/BV..." --do-transcribe --do-summary
```

Transcribe a local file:

```bash
vlp transcribe ./output/demo/video.mp4
```

Summarize an existing transcript:

```bash
vlp summarize ./output/demo/transcript.txt --provider claude
```

## Common Commands

### Download

```bash
vlp download "https://..."
vlp download "https://..." --audio-only
vlp download "https://..." --sub-lang zh --sub-lang en
vlp download "https://..." --cookies-from-browser chrome
vlp download "https://..." --cookie-file ./cookies.txt
vlp download "https://..." --selenium auto
vlp download "https://..." --group-by-site
```

### Download Subtitles Only

```bash
vlp download-subs "https://www.bilibili.com/video/BV..."
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

### Convert Subtitles

```bash
vlp convert-subtitle ./subtitle.vtt --format srt
vlp convert-subtitle ./subs --batch --format srt
```

### Doctor

```bash
vlp doctor
vlp doctor --config ./config.yaml
```

## Cookies and Login

Many sites need a logged-in session for stable downloads. The simplest long-term setup is to export a reusable `cookies.txt` file once and keep using it.

```bash
vlp cookies-login "https://www.bilibili.com" --cookie-file ./cookies.txt
vlp download "https://www.bilibili.com/video/BV..." --cookie-file ./cookies.txt
vlp run "https://www.bilibili.com/video/BV..." --cookie-file ./cookies.txt --do-summary
```

Notes:

- `--cookies-from-browser chrome` is convenient but may fail when the browser cookie database is locked
- on Windows, fully closing Chrome / Edge / Firefox often resolves cookie-copy failures
- `cookies-login` uses a dedicated browser profile and is better for long-term reuse

## Web Workspace

The repository also includes a local web frontend for:

- creating jobs
- browsing the task board
- checking stage status, logs, and diagnostics
- previewing transcript, subtitle, media, and summary artifacts

Frontend and API code live in:

- [web/frontend](G:\www-xxk\video-link-pipeline\web\frontend)
- [web/api](G:\www-xxk\video-link-pipeline\web\api)

In local development, CLI jobs typically write to `output/`, then the Web API and frontend read those task folders.

## Output Layout

All tasks write into their own job directory under `output_dir`. A typical structure looks like this:

```text
output/
└─ BVxxxx-demo-title/
   ├─ video.mp4
   ├─ audio.m4a
   ├─ subtitle.srt
   ├─ subtitle.vtt
   ├─ transcript.txt
   ├─ subtitle_whisper.srt
   ├─ subtitle_whisper.vtt
   ├─ transcript.json
   ├─ summary.md
   ├─ keywords.json
   └─ manifest.json
```

Where:

- `transcript.txt`: plain-text transcript
- `subtitle_whisper.srt` / `subtitle_whisper.vtt`: Whisper-generated subtitles
- `summary.md`: summary output
- `keywords.json`: keywords output
- `manifest.json`: stable machine-readable task state

If `group_output_by_site` is enabled, or you pass `--group-by-site`, output is grouped by site first:

```text
output/
├─ bilibili/
│  └─ BVxxxx-demo-title/
└─ youtube/
   └─ demo-title/
```

## What `manifest.json` Is

`manifest.json` is the core state file in this project. Both the CLI and Web workspace rely on it.

It usually records:

- the input source
- the current command
- generated artifact paths
- download / transcribe / summarize stage state
- failure details and some diagnostics

If you are building automation, scanners, or UI features, rely on `manifest.json` first instead of guessing from directory names alone.

## Configuration

The default config file is `config.yaml` in the project root.

Precedence:

1. CLI arguments
2. environment variables and `.env`
3. `config.yaml`
4. built-in defaults

A compact example:

```yaml
output_dir: ./output
group_output_by_site: false
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

## Project Layout

Core source code lives in [src/video_link_pipeline](G:\www-xxk\video-link-pipeline\src\video_link_pipeline):

```text
src/video_link_pipeline/
├── cli.py
├── config.py
├── manifest.py
├── doctor.py
├── errors.py
├── download/
├── transcribe/
├── summarize/
└── subtitles/
```

At a high level:

- CLI orchestration layer: command entry points and flow wiring
- service layer: download, transcription, summary, subtitle conversion
- infrastructure layer: config, errors, manifest, doctor

Compatibility scripts are still present, but new usage should prefer `vlp`:

- `download_video.py`
- `parallel_transcribe.py`
- `generate_summary.py`
- `convert_subtitle.py`

## Local Development

Using a repository-local virtual environment is recommended:

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .[dev]
```

Common validation commands:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m build
```

If you only want a lighter first pass:

```powershell
& .\.venv\Scripts\python.exe -m compileall src tests
```

There is also a PowerShell helper:

```powershell
./scripts/check.ps1
```

## Related Directories

- [src/video_link_pipeline](G:\www-xxk\video-link-pipeline\src\video_link_pipeline): core Python package
- [tests](G:\www-xxk\video-link-pipeline\tests): test suite
- [web](G:\www-xxk\video-link-pipeline\web): local Web workspace
- [scripts](G:\www-xxk\video-link-pipeline\scripts): helper scripts
- [skills/video-link-pipeline](G:\www-xxk\video-link-pipeline\skills\video-link-pipeline): Codex skill

## License

MIT License
