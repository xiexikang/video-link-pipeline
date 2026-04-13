# video-link-pipeline

`video-link-pipeline` 是一个面向本地命令行的全流程工具集，用来完成视频下载、转录、摘要生成和字幕格式转换。

当前仓库正在从“多个独立脚本”迁移到“可发布的 Python 包 + 统一 CLI”的形态。现在推荐的主入口是 `vlp`，旧脚本 `download_video.py`、`parallel_transcribe.py`、`generate_summary.py`、`convert_subtitle.py` 仍然保留为兼容 wrapper。

## 当前能力

- `vlp download <url>`：下载视频、音频、字幕，并标准化输出目录
- `vlp transcribe <path>`：对视频或音频做 Whisper 转录，生成 `transcript.txt`、`subtitle_whisper.srt`、`subtitle_whisper.vtt`
- `vlp summarize <transcript.txt>`：调用大模型生成 `summary.md` 和 `keywords.json`
- `vlp convert-subtitle <file-or-dir>`：在 `srt` 和 `vtt` 之间转换
- `vlp run <url>`：串联下载、转录、摘要，并持续更新 `manifest.json`
- `vlp doctor`：检查 Python、FFmpeg、Selenium extra、cookies 配置

## 安装

要求：

- Python 3.10+
- Windows、Linux、macOS 均可，本项目当前优先照顾 Windows 使用体验

推荐安装方式：

```bash
git clone <repository_url>
cd video-link-pipeline
pip install -e .
```

如果需要 Selenium 兜底能力：

```bash
pip install -e .[selenium]
```

如果需要开发依赖：

```bash
pip install -e .[dev]
```

`vlp doctor` 现在会把部分常见下载诊断码和修复建议串起来，尤其是这些 Windows 常见问题：

- `browser_cookie_locked`：浏览器 cookies 数据库被占用时，先完全关闭 Chrome / Edge / Firefox 再重试
- `browser_driver_unavailable`：未安装 Selenium extra 或浏览器驱动不可用时，先执行 `pip install "video-link-pipeline[selenium]"`
- `ffmpeg_unavailable`：系统没有可用 FFmpeg 时，安装系统 ffmpeg，或确保环境中保留 `imageio-ffmpeg`

安装完成后可以先检查命令是否可用：

```bash
vlp --help
vlp doctor
```

## 本地开发验证

如果你在本地参与开发，推荐直接安装 dev 依赖：

```bash
pip install -e .[dev]
```

与当前 CI 保持一致的最小验证命令：

```bash
python -m ruff check .
python -m pytest
```

如果当前环境还没安装 `pytest`，运行 `python -m pytest` 时会看到类似 `No module named pytest` 的报错。这时重新执行：

```bash
pip install -e .[dev]
```

如果你只想先跑某一小组测试，也可以：

```bash
python -m pytest tests/test_doctor.py
python -m pytest tests/test_download_diagnostics.py
```

## 配置

默认配置文件是项目根目录下的 `config.yaml`。

配置优先级：

1. CLI 参数
2. 环境变量和 `.env`
3. `config.yaml`
4. 内置默认值

配置示例：

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

说明：

- 旧配置 `summary.api_keys.*` 仍会被兼容读取，但会给出迁移 warning
- `vlp doctor` 会提示当前 FFmpeg 来源和 Selenium/cookies 相关问题
- `--selenium auto|on|off` 已接入 `download` 和 `run`

## 使用方式

### 下载

```bash
vlp download "https://www.bilibili.com/video/BV..."
vlp download "https://..." --output-dir ./output --sub-lang zh --sub-lang en
vlp download "https://..." --audio-only
vlp download "https://..." --cookies-from-browser chrome
vlp download "https://..." --cookie-file ./cookies.txt
vlp download "https://..." --selenium auto
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

### 串联执行

```bash
vlp run "https://..."
vlp run "https://..." --do-transcribe
vlp run "https://..." --do-transcribe --do-summary
```

### 环境自检

```bash
vlp doctor
vlp doctor --config ./config.yaml
```

## 输出约定

`output_dir` 是输出根目录，每次任务会落到单独的 job 目录中。

典型输出如下：

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

其中 `manifest.json` 是稳定的机器可读输出，会在 `download`、`transcribe`、`summarize`、`run` 中持续补全。

当下载阶段触发 Selenium fallback 时，`manifest.json` 的 `execution.download` 里还会额外记录诊断字段：

- `used_selenium_fallback`：是否走过浏览器兜底
- `error_code`：下载失败分类，例如 `DOWNLOAD_PRIMARY_FAILED`、`DOWNLOAD_FALLBACK_PREPARE_FAILED`、`DOWNLOAD_FALLBACK_RETRY_FAILED`
- `fallback_status`：fallback 当前状态，例如 `triggered`、`dependency_missing`、`prepare_failed`、`retry_failed`、`succeeded`
- `warnings`：触发 fallback 的原因、缺依赖提示、上下文准备说明
- `warning_details`：结构化 warning 列表，包含 `code`、`message`、`stage`，便于批处理统计，例如 `primary_http_403`、`browser_cookie_locked`、`fallback_media_hint_missing`
- `fallback_context.resolved_url`：浏览器最终停留地址
- `fallback_context.canonical_url`：页面 canonical 或等价主地址
- `fallback_context.media_hint_url`：从页面线索中提取出的优先重试媒体地址
- `fallback_context.site_name`：识别出的站点名称
- `fallback_context.extraction_source`：媒体线索来源，例如 `next-data:playAddr`、`jsonld:contentUrl`

常见 `warning_details.code` 对照：

- `primary_http_403`：主下载遇到 403/Forbidden，通常是反爬、鉴权或区域限制
- `primary_captcha_required`：主下载命中验证码或人机校验
- `primary_auth_required`：主下载需要登录或账号权限
- `browser_cookie_locked`：浏览器 cookies 数据库被占用、锁定或无法复制
- `browser_driver_unavailable`：Selenium 浏览器驱动不可用
- `fallback_context_prepared`：fallback 已成功提取浏览器上下文
- `fallback_media_hint_missing`：未提取到明确媒体地址，只能用页面地址重试
- `fallback_dependency_hint` / `fallback_prepare_hint` / `fallback_retry_hint`：fallback 各阶段的补充提示

一个典型的下载诊断片段示例如下：

```json
{
  "execution": {
    "download": {
      "success": false,
      "used_selenium_fallback": false,
      "fallback_status": "dependency_missing",
      "error_code": "DEPENDENCY_MISSING",
      "error": "selenium fallback requested but optional dependencies are not installed",
      "warnings": [
        "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
        "install with: pip install \"video-link-pipeline[selenium]\""
      ],
      "warning_details": [
        {
          "code": "primary_http_403",
          "stage": "primary_download",
          "message": "primary download failed and triggered selenium fallback: HTTP Error 403: Forbidden",
          "description": "Primary download hit 403/Forbidden, usually anti-bot, auth, or geo restriction."
        },
        {
          "code": "fallback_dependency_hint",
          "stage": "fallback_dependency",
          "message": "install with: pip install \"video-link-pipeline[selenium]\"",
          "description": "Additional hint emitted when fallback dependencies are missing."
        }
      ],
      "fallback_context": null
    }
  }
}
```

如果 fallback 已成功准备浏览器上下文，常见字段会变成：

- `fallback_status = "prepared"` 或 `"succeeded"`
- `warning_details.code` 里出现 `fallback_context_prepared`
- `fallback_context.media_hint_url`、`fallback_context.extraction_source` 可用于后续分析站点提取质量

## 兼容脚本

以下脚本仍然可用，但定位已经变成兼容层：

- `python download_video.py ...`
- `python parallel_transcribe.py ...`
- `python generate_summary.py ...`
- `python convert_subtitle.py ...`

建议新用法统一迁移到 `vlp`。兼容脚本会继续复用包内实现，但不再作为长期主入口。

## 已知状态

- `vlp run` 和 `vlp doctor` 已经落地
- 已补充基础测试与 Windows CI 配置
- 当前环境下如果未安装 `pytest`，本地无法直接执行测试
- Selenium fallback 目前仍在逐步完善，`doctor` 会先给出安装与诊断提示

## License

MIT License
