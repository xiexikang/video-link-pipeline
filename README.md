# 视频提取与处理系统

从第三方平台链接中提取视频、音频及字幕，并提供AI驱动的语音转录和智能摘要功能。

## 快速开始

### 1. 安装依赖

```bash
# Linux/macOS
bash scripts/install_deps.sh

# Windows (手动安装)
# 1. 安装 Python 3.8+ 和 FFmpeg
# 2. pip install -r requirements.txt
```

### 2. 下载视频

```bash
python download_video.py "https://www.youtube.com/watch?v=xxxxx" \
  --output-dir ./output \
  --lang zh en \
  --cookies chrome
```

### 3. 语音转录（如需要）

```bash
python parallel_transcribe.py \
  --input output/Video_Title/video.mp4 \
  --model small \
  --language zh
```

### 4. 生成AI摘要

```bash
python generate_summary.py \
  --transcript output/Video_Title/transcript.txt
```

## 功能模块

- **download_video.py** - 视频/音频/字幕下载 (yt-dlp)
- **parallel_transcribe.py** - Whisper语音转录
- **convert_subtitle.py** - 字幕格式转换 (VTT ↔ SRT)
- **generate_summary.py** - AI智能摘要生成

## 配置文件

编辑 `config.yaml` 自定义设置：

```yaml
output_dir: ./output
whisper:
  model: small
  workers: 4
summary:
  enabled: true
  provider: claude  # 或 openai
api_keys:
  claude: your-api-key-here
  openai: your-api-key-here
```

## 支持平台

YouTube、哔哩哔哩、抖音/TikTok、Twitter/X、Instagram、Vimeo 等 1800+ 平台。
