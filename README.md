# 视频提取与处理系统 (Video Extraction & Processing System)

这是一个集成了视频下载、音频提取、字幕处理、语音转录和 AI 摘要生成的全流程工具集。旨在帮助用户快速从各大视频平台获取内容，并利用 AI 技术进行深度处理。

## ✨ 主要功能

*   **全能下载**: 支持 YouTube, Bilibili, TikTok 等 1800+ 平台的视频/音频/字幕下载 (基于 `yt-dlp`)。
*   **智能转录**: 使用 `faster-whisper` 进行本地语音转录，支持多种模型和语言，GPU 加速。
*   **字幕转换**: 提供 SRT 与 VTT 字幕格式的互转工具。
*   **AI 摘要**: 集成 Claude 和 OpenAI API，一键生成视频内容的智能摘要。
*   **高度可配**: 通过 `config.yaml` 灵活配置各项参数。

## 🛠️ 环境准备

在开始之前，请确保您的系统已安装：

*   **Python 3.8+**
*   **FFmpeg**: 必须安装并添加到系统环境变量中。
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
      device: auto # 或 cuda
    summary:
      provider: claude # 或 openai
      api_keys:
        claude: "sk-..."
    ```

## 📖 使用指南

### 1. 下载视频 (download_video.py)

从 URL 下载视频、音频和字幕。

```bash
# 基础用法
python download_video.py "https://www.bilibili.com/video/BV1..."

# 指定输出目录和语言
python download_video.py "https://..." --output-dir ./my_videos --lang zh en

# 仅下载音频
python download_video.py "https://..." --audio-only

# 使用浏览器 Cookies (解决会员/登录限制)
python download_video.py "https://..." --cookies chrome
```

### 2. 语音转录 (parallel_transcribe.py)

使用 Whisper 模型将音视频文件转录为文本/字幕。

```bash
# 基础转录
python parallel_transcribe.py --input "./output/video.mp4"

# 指定模型大小和语言
python parallel_transcribe.py --input "./output/video.mp4" --model large-v3 --language zh

# 使用 GPU 加速 (需安装 CUDA 对应版本的 PyTorch)
python parallel_transcribe.py --input "./output/video.mp4" --device cuda --compute-type float16
```

### 3. 字幕转换 (convert_subtitle.py)

在 SRT 和 VTT 格式之间进行转换。

```bash
# 单个文件转换 (自动识别源格式)
python convert_subtitle.py --input "sub.vtt"

# 批量转换目录下的所有字幕文件
python convert_subtitle.py --input "./subs_folder" --batch --format srt
```

### 4. 生成 AI 摘要 (generate_summary.py)

基于转录文本生成内容摘要。

```bash
# 生成摘要
python generate_summary.py --transcript "./output/video/transcript.txt"

# 临时指定 API Key 和提供商
python generate_summary.py --transcript "..." --provider openai --api-key "sk-..."
```

## ⚙️ 配置文件说明 (config.yaml)

| 配置项 | 说明 | 默认值 |
| :--- | :--- | :--- |
| `output_dir` | 默认下载/输出目录 | `./output` |
| `whisper.model` | Whisper 模型大小 (tiny, base, small, medium, large-v3) | `small` |
| `whisper.device` | 运行设备 (`cpu`, `cuda`, `auto`) | `auto` |
| `summary.provider` | 摘要服务提供商 (`claude`, `openai`) | `claude` |
| `download.cookies_from_browser`| 默认使用的浏览器 Cookies 来源 | `null` |

## 📂 项目结构

```
skill-video-extract/
├── download_video.py       # 视频下载主程序
├── parallel_transcribe.py  # 语音转录主程序
├── generate_summary.py     # AI 摘要生成主程序
├── convert_subtitle.py     # 字幕转换工具
├── config.yaml             # 全局配置文件
├── requirements.txt        # Python 依赖列表
├── scripts/                # 辅助脚本
└── README.md               # 项目说明文档
```

## 📄 许可证

详见 LICENSE 文件。
