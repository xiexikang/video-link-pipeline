# 视频提取与处理系统 (Video Extraction & Processing System)

这是一个集成了视频下载、音频提取、字幕处理、语音转录和 AI 摘要生成的全流程工具集。旨在帮助用户快速从各大视频平台获取内容，并利用 AI 技术进行深度处理。

## ✨ 主要功能

*   **全能下载**: 支持 YouTube, Bilibili, TikTok/抖音， Kuaishou (快手) 等多个平台的视频/音频/字幕下载 (基于 `yt-dlp`)。
    *   **强力反爬**: 内置 Selenium 移动端模拟与反检测机制，有效应对快手等平台的反爬虫策略。
    *   **Cookies 支持**: 支持自动调用浏览器 Cookies 或加载 Cookies 文件，解决会员/登录限制。
*   **智能转录**: 使用 `faster-whisper` 进行本地语音转录，支持多种模型和语言，GPU 加速，自动配置 FFmpeg 环境。
*   **字幕转换**: 提供 SRT 与 VTT 字幕格式的互转工具。
*   **AI 摘要**: 集成 Claude 和 OpenAI API，一键生成视频内容的结构化智能摘要（包含一句话概括、核心要点、关键语段、标签等）。
*   **高度可配**: 通过 `config.yaml` 灵活配置各项参数。

## 🛠️ 环境准备

在开始之前，请确保您的系统已安装：

*   **Python 3.8+**
*   **FFmpeg**: 推荐安装并添加到系统环境变量中（脚本也内置了自动下载/配置 FFmpeg 的功能作为备选）。
    *   Windows: [下载链接](https://ffmpeg.org/download.html) (推荐使用 `winget install ffmpeg` 或手动配置)
    *   Linux: `sudo apt install ffmpeg`
    *   macOS: `brew install ffmpeg`

## 🚀 快速安装

1.  **克隆项目**
    ```bash
    git clone <repository_url>
    cd skill-video-extract
    ```

2.  **安装依赖**
    
    *   **Windows**:
        ```bash
        pip install -r requirements.txt
        # 如需使用 Selenium 强力反爬功能，请额外安装：
        pip install selenium webdriver_manager
        ```
    *   **Linux / macOS**:
        ```bash
        chmod +x scripts/install_deps.sh
        ./scripts/install_deps.sh
        ```

3.  **配置**
    确保 `config.yaml` 存在并根据需要修改（可参考项目中的默认配置）：
    ```yaml
    # 示例配置项
    output_dir: ./output
    whisper:
      model: small
      device: auto # auto, cuda, cpu
      compute_type: int8 # int8, float16
    summary:
      provider: claude # claude 或 openai
      api_keys:
        claude: "sk-..." # 在此填入您的 API Key，或使用环境变量
    download:
      cookies_from_browser: chrome # 默认使用的浏览器 Cookies
    ```

## 📖 使用指南

### 1. 下载视频 (download_video.py)

从 URL 下载视频、音频和字幕。支持自动处理反爬虫重定向。

```bash
# 基础用法
python download_video.py "https://www.bilibili.com/video/BV1..."

# 指定输出目录和语言
python download_video.py "https://..." --output-dir ./my_videos --lang zh en

# 仅下载音频
python download_video.py "https://..." --audio-only

# 使用浏览器 Cookies (解决会员/登录限制)
# 支持: chrome, edge, firefox, opera, brave, vivaldi
python download_video.py "https://..." --cookies chrome

# 使用 Cookies 文件 (Netscape 格式)
python download_video.py "https://..." --cookies cookies.txt
```

### 2. 语音转录 (parallel_transcribe.py)

使用 Whisper 模型将音视频文件转录为文本/字幕。

```bash
# 基础转录
python parallel_transcribe.py --input "./output/video.mp4"

# 指定模型大小和语言 (tiny, base, small, medium, large-v3)
python parallel_transcribe.py --input "./output/video.mp4" --model large-v3 --language zh

# 选择转录引擎 (当 faster-whisper 无法运行时使用 openai-whisper)
python parallel_transcribe.py --input "./output/video.mp4" --engine openai_whisper

# 使用 GPU 加速 (需安装 CUDA 对应版本的 PyTorch)
python parallel_transcribe.py --input "./output/video.mp4" --device cuda --compute-type float16
```

### 3. AI 摘要生成 (generate_summary.py)

利用 LLM (Claude/OpenAI/Gemini/DeepSeek 等) 对转录内容进行智能摘要。

**支持的模型提供商**:
- `claude` (Anthropic Claude 3.5 Sonnet 等)
- `openai` (GPT-4o, GPT-3.5 等)
- `gemini` (Google Gemini 1.5 Flash/Pro)
- `deepseek` (DeepSeek V3/R1)
- `kimi` / `moonshot` (Moonshot AI)
- `minimax` (MiniMax)
- `glm` / `zhipu` (智谱 AI GLM-4)

**配置方式**:
在 `config.yaml` 中设置 provider 和对应的 API Key，或通过环境变量设置 (如 `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` 等)。

**输出内容**:
1.  **Markdown 摘要报告** (`summary.md`): 包含一句话概括、核心要点、关键语段、主题标签和整体评价。
2.  **结构化 JSON 数据** (`keywords.json`): 包含便于程序处理的结构化字段。

```bash
# 基础用法 (使用 config.yaml 中的配置)
python generate_summary.py --transcript "./output/video/transcript.txt"

# 指定模型提供商和 API Key (临时覆盖配置)
python generate_summary.py --transcript "transcript.txt" --provider openai --model gpt-4o-mini --api-key "sk-..."

# 使用 DeepSeek (兼容 OpenAI 接口)
python generate_summary.py --transcript "transcript.txt" --provider deepseek --api-key "sk-..."

# 输出完整 JSON 结果到终端
python generate_summary.py --transcript "transcript.txt" --json
```

### 4. 字幕转换 (convert_subtitle.py)

在 SRT 和 VTT 格式之间进行转换。

```bash
# 单个文件转换 (自动识别源格式)
python convert_subtitle.py --input "sub.vtt"

# 批量转换目录下的所有字幕文件
python convert_subtitle.py --input "./subs_dir"
```

## 📂 项目结构

```
.
├── download_video.py       # 视频下载主程序 (集成 Selenium/yt-dlp)
├── parallel_transcribe.py  # 语音转录主程序 (Faster-Whisper)
├── generate_summary.py     # AI 摘要生成程序
├── convert_subtitle.py     # 字幕格式转换工具
├── config.yaml             # 配置文件
├── requirements.txt        # Python 依赖
└── scripts/                # 辅助脚本
```

## � License

MIT License
