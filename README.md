# video-link-pipeline

`video-link-pipeline` 是一个本地视频处理工具集，用来把“视频链接 / 本地媒体”整理成一套可复用产物：

- 下载视频、音频、字幕和元数据
- 用 Whisper 生成转录文本和字幕
- 用大模型生成摘要和关键词
- 按任务目录持续写入 `manifest.json`

它既可以作为 CLI 使用，也带有一个本地 Web 工作台，适合在本机持续跑下载、转录和摘要流程。

英文说明见 [README.en.md](G:\www-xxk\video-link-pipeline\README.en.md)。

## 适合什么场景

- 想把 B 站、YouTube 等视频内容拉到本地继续整理
- 想把视频快速转成 `transcript.txt`、`subtitle.srt`、`summary.md`
- 想保留稳定的任务目录和机器可读状态文件
- 想在本地页面里查看任务进度、日志和产物预览

## 当前能力

- `vlp download <url>`：下载媒体、字幕和元数据
- `vlp download-subs <url>`：只下载字幕和元数据
- `vlp transcribe <path>`：对本地视频或音频做转录
- `vlp summarize <transcript.txt>`：生成摘要和关键词
- `vlp convert-subtitle <file-or-dir>`：在 `srt` / `vtt` 之间转换
- `vlp run <url>`：串联下载、转录、摘要
- `vlp cookies-login <url>`：打开独立浏览器窗口完成登录并导出 `cookies.txt`
- `vlp doctor`：检查 Python、FFmpeg、Selenium、cookies 等环境状态

## 快速开始

### 1. 安装

要求：

- Python 3.10+
- Windows、Linux、macOS

推荐安装：

```bash
git clone <repository_url>
cd video-link-pipeline
pip install -e .
```

如果你需要 Selenium 浏览器兜底：

```bash
pip install -e .[selenium]
```

如果你要参与开发：

```bash
pip install -e .[dev]
```

安装后先确认命令可用：

```bash
vlp --help
vlp doctor
```

### 2. 跑一个最小流程

只下载：

```bash
vlp download "https://www.bilibili.com/video/BV..."
```

完整流程：

```bash
vlp run "https://www.bilibili.com/video/BV..." --do-transcribe --do-summary
```

对本地文件转录：

```bash
vlp transcribe ./output/demo/video.mp4
```

对已有转录生成摘要：

```bash
vlp summarize ./output/demo/transcript.txt --provider claude
```

## 常用命令

### 下载

```bash
vlp download "https://..."
vlp download "https://..." --audio-only
vlp download "https://..." --sub-lang zh --sub-lang en
vlp download "https://..." --cookies-from-browser chrome
vlp download "https://..." --cookie-file ./cookies.txt
vlp download "https://..." --selenium auto
vlp download "https://..." --group-by-site
```

### 只下载字幕

```bash
vlp download-subs "https://www.bilibili.com/video/BV..."
```

### 转录

```bash
vlp transcribe ./output/demo/video.mp4
vlp transcribe ./output/demo --model small --language auto
vlp transcribe ./output/demo/video.mp4 --engine faster --device cpu --compute-type int8
```

### 摘要

```bash
vlp summarize ./output/demo/transcript.txt --provider claude
vlp summarize ./output/demo/transcript.txt --provider deepseek --base-url https://api.deepseek.com --model deepseek-chat
```

### 字幕转换

```bash
vlp convert-subtitle ./subtitle.vtt --format srt
vlp convert-subtitle ./subs --batch --format srt
```

### 环境检查

```bash
vlp doctor
vlp doctor --config ./config.yaml
```

## Cookies 与登录

很多站点在下载时会依赖登录态。最省心的做法是先导出一个 `cookies.txt`，后续反复复用。

```bash
vlp cookies-login "https://www.bilibili.com" --cookie-file ./cookies.txt
vlp download "https://www.bilibili.com/video/BV..." --cookie-file ./cookies.txt
vlp run "https://www.bilibili.com/video/BV..." --cookie-file ./cookies.txt --do-summary
```

补充说明：

- `--cookies-from-browser chrome` 直接读浏览器 cookies，最方便，但浏览器运行中可能锁库
- Windows 下如果看到浏览器 cookies 复制失败，先彻底关闭 Chrome / Edge / Firefox 再重试
- `cookies-login` 使用独立浏览器 profile，更适合长期复用登录态

## Web 工作台

仓库里带有本地 Web 前端，适合：

- 新建任务
- 查看任务看板
- 查看阶段状态、日志和诊断信息
- 预览 transcript / subtitle / media / summary 等产物

前端代码在：

- [web/frontend](G:\www-xxk\video-link-pipeline\web\frontend)
- [web/api](G:\www-xxk\video-link-pipeline\web\api)

如果你正在做本地开发，通常会把 CLI 产物写到 `output/`，再由 Web API 和前端读取这些任务目录。

## 输出目录约定

所有任务都写入 `output_dir` 下的单独 job 目录。典型结构如下：

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

其中：

- `transcript.txt`：纯文本转录
- `subtitle_whisper.srt` / `subtitle_whisper.vtt`：Whisper 生成字幕
- `summary.md`：摘要结果
- `keywords.json`：关键词结果
- `manifest.json`：稳定的机器可读任务状态

如果开启 `group_output_by_site` 或命令行传入 `--group-by-site`，目录会先按站点归类：

```text
output/
├─ bilibili/
│  └─ BVxxxx-demo-title/
└─ youtube/
   └─ demo-title/
```

## `manifest.json` 是什么

`manifest.json` 是这套工具最重要的状态文件。CLI 和 Web 都围绕它工作。

它通常记录：

- 输入来源
- 当前命令
- 已生成的产物路径
- 下载 / 转录 / 摘要各阶段状态
- 失败原因与部分诊断信息

如果你要做自动化处理、任务扫描、Web 展示，优先依赖 `manifest.json`，不要靠猜目录结构。

## 配置

默认配置文件是项目根目录的 `config.yaml`。

优先级：

1. CLI 参数
2. 环境变量和 `.env`
3. `config.yaml`
4. 内置默认值

一个精简配置示例：

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

常用环境变量：

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

## 项目结构

核心源码在 [src/video_link_pipeline](G:\www-xxk\video-link-pipeline\src\video_link_pipeline)：

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

可以简单理解为三层：

- CLI 编排层：命令入口和参数组织
- 服务层：下载、转录、摘要、字幕转换
- 基础设施：配置、错误、manifest、doctor

兼容脚本仍然保留，但新用法建议统一走 `vlp`：

- `download_video.py`
- `parallel_transcribe.py`
- `generate_summary.py`
- `convert_subtitle.py`

## 本地开发

推荐使用仓库内虚拟环境：

```powershell
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e .[dev]
```

常用检查命令：

```powershell
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m build
```

如果你只想先做一轮轻量检查：

```powershell
& .\.venv\Scripts\python.exe -m compileall src tests
```

仓库里也提供了 PowerShell 检查脚本：

```powershell
./scripts/check.ps1
```

## 相关目录

- [src/video_link_pipeline](G:\www-xxk\video-link-pipeline\src\video_link_pipeline)：核心 Python 包
- [tests](G:\www-xxk\video-link-pipeline\tests)：测试
- [web](G:\www-xxk\video-link-pipeline\web)：本地 Web 工作台
- [scripts](G:\www-xxk\video-link-pipeline\scripts)：开发辅助脚本
- [skills/video-link-pipeline](G:\www-xxk\video-link-pipeline\skills\video-link-pipeline)：Codex skill

## License

MIT License
