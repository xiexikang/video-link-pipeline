# video-link-pipeline 

This is a complete toolset integrating video downloading, audio extraction, subtitle processing, speech transcription, and AI summarization. It aims to help users quickly acquire content from major video platforms and perform in-depth processing using AI technology.

## ✨ Key Features

*   **All-in-One Download**: Supports video/audio/subtitle downloading from multiple platforms like YouTube, Bilibili, TikTok, Kuaishou, etc. (based on `yt-dlp`).
    *   **Powerful Anti-Crawling**: Built-in Selenium mobile emulation and anti-detection mechanisms to effectively counter anti-crawling strategies of platforms like Kuaishou, automatically attempting direct link downloads.
    *   **Cookies Support**: Supports automatically invoking browser Cookies (Chrome, Edge, Firefox, etc.) or loading Netscape format Cookies files to solve member/login restrictions.
    *   **Audio Only Mode**: Supports downloading only audio and automatically converting it to MP3.
*   **Smart Transcription**: Uses `faster-whisper` (default) or `openai-whisper` for local speech transcription.
    *   **Multi-Model Support**: Supports models of all sizes from tiny to large-v3.
    *   **High Performance**: Supports GPU acceleration (CUDA) and INT8/Float16 quantization inference.
    *   **Auto Environment**: Built-in FFmpeg environment automatic configuration function, no need for tedious manual installation.
*   **AI Summary**: Integrates multiple mainstream large model APIs to generate structured intelligent summaries of video content with one click.
    *   **Multi-Model Support**: Claude 3.5, GPT-4o, Gemini 1.5, DeepSeek V3, Kimi, MiniMax, Zhipu GLM-4, etc.
    *   **Structured Output**: Generates Markdown reports and JSON data containing a one-sentence summary, core points, key segments, and tags.
*   **Subtitle Tools**: Provides conversion tools between SRT and VTT subtitle formats, supporting batch processing.
*   **Highly Configurable**: Flexibly configure various parameters via `config.yaml`.

## 🛠️ Prerequisites

Before starting, please ensure your system has installed:

*   **Python 3.8+**
*   **FFmpeg**: 
    *   The project has built-in automatic detection and configuration of FFmpeg. If not installed on the system, the script will automatically try to use `imageio-ffmpeg` or configure the local `bin` directory.
    *   Of course, you can also manually install and add it to the environment variables for the best experience.

## 🚀 Quick Install

1.  **Clone Project**
    ```bash
    git clone <repository_url>
    cd skill-video-extract
    ```

2.  **Install Dependencies**
    
    *   **Windows**:
        ```bash
        pip install -r requirements.txt
        # To use Selenium powerful anti-crawling features (recommended), please install additionally:
        pip install selenium webdriver_manager
        ```
    *   **Linux / macOS**:
        ```bash
        chmod +x scripts/install_deps.sh
        ./scripts/install_deps.sh
        ```

3.  **Configuration**
    Ensure `config.yaml` exists and modify it as needed (default configuration is in the project root directory):
    ```yaml
    # config.yaml example
    output_dir: ./output
    
    whisper:
      model: small
      device: auto # auto, cuda, cpu
      compute_type: int8 # int8, float16
    
    summary:
      provider: claude # Supports claude, openai, gemini, deepseek, kimi, minimax, glm
      model: claude-3-5-sonnet-20241022
      api_keys:
        claude: "sk-..." 
        openai: "sk-..."
        # Or use environment variables ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.
    
    download:
      cookies_from_browser: chrome # Default browser Cookies to use
    ```

## 📖 Usage Guide

### 1. Download Video (download_video.py)

Download video, audio, and subtitles from URL. Supports automatic handling of anti-crawling redirects.

```bash
# Basic usage
python download_video.py "https://www.bilibili.com/video/BV1..."

# Specify output directory and languages
python download_video.py "https://..." --output-dir ./my_videos --lang zh en

# Download audio only (save as MP3)
python download_video.py "https://..." --audio-only

# Use browser Cookies (solve member/login restrictions)
# Supports: chrome, edge, firefox, opera, brave, vivaldi
python download_video.py "https://..." --cookies chrome

# Use Cookies file (Netscape format)
python download_video.py "https://..." --cookies cookies.txt
```

### 2. Speech Transcription (parallel_transcribe.py)

Transcribe audio/video files to text/subtitles using Whisper models.

```bash
# Basic transcription (uses faster-whisper, small model by default)
python parallel_transcribe.py --input "./output/video/video.mp4"

# Specify model size and language
python parallel_transcribe.py -i "./video.mp4" --model large-v3 --language zh

# Use GPU acceleration (requires CUDA version of PyTorch)
python parallel_transcribe.py -i "./video.mp4" --device cuda --compute-type float16

# Switch transcription engine
# faster_whisper (recommended, fast) | openai_whisper (original, good compatibility)
python parallel_transcribe.py -i "./video.mp4" --engine openai_whisper

# Batch transcription (input directory)
python parallel_transcribe.py -i "./output/videos_folder"
```

### 3. AI Summary Generation (generate_summary.py)

Generate intelligent summaries of transcribed content using LLMs.

**Supported Model Providers**:
*   `claude` (Anthropic Claude 3.5 Sonnet, etc.)
*   `openai` (GPT-4o, GPT-3.5, etc.)
*   `gemini` (Google Gemini 1.5 Flash/Pro)
*   `deepseek` (DeepSeek V3/R1)
*   `kimi` / `moonshot` (Moonshot AI)
*   `minimax` (MiniMax)
*   `glm` / `zhipu` (Zhipu AI GLM-4)

**Configuration**:
Set `provider` and corresponding `api_keys` in `config.yaml`, or create a `.env` file in the project root (or set environment variables) to configure API Keys (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY`, etc.).

**Output Content**:
1.  **Markdown Summary Report** (`summary.md`): Contains one-sentence summary, core points, key segments, topic tags, and overall evaluation.
2.  **Structured JSON Data** (`keywords.json`): Contains structured fields for easy programmatic processing.

```bash
# Basic usage (uses configuration in config.yaml)
python generate_summary.py --transcript "./output/video/transcript.txt"

# Temporarily specify model provider and API Key
python generate_summary.py -t "transcript.txt" --provider openai --model gpt-4o --api-key "sk-..."

# Use DeepSeek
python generate_summary.py -t "transcript.txt" --provider deepseek --api-key "sk-..."

# Output full JSON result to terminal
python generate_summary.py -t "transcript.txt" --json
```

### 4. Subtitle Conversion (convert_subtitle.py)

Convert between SRT and VTT formats.

```bash
# Single file conversion (automatically detects source format and converts reversely)
python convert_subtitle.py --input "sub.vtt"

# Specify output format
python convert_subtitle.py --input "sub.vtt" --format srt

# Batch convert all subtitle files in a directory
python convert_subtitle.py --input "./subs_dir" --batch --format srt
```

## 📂 Project Structure

```
.
├── download_video.py       # Video download main program (integrates Selenium/yt-dlp)
├── parallel_transcribe.py  # Speech transcription main program (Faster-Whisper/OpenAI-Whisper)
├── generate_summary.py     # AI summary generation program (multi-model support)
├── convert_subtitle.py     # Subtitle format conversion tool
├── config.yaml             # Configuration file
├── requirements.txt        # Python dependencies
└── scripts/                # Helper scripts
```

## 📄 License

MIT License
