#!/usr/bin/env python3
"""Compatibility wrapper for legacy video download usage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

from video_link_pipeline import logging as log
from video_link_pipeline.download.service import execute_download
from video_link_pipeline.errors import VlpError


def main() -> int:
    parser = argparse.ArgumentParser(description="视频下载工具")
    parser.add_argument("url", help="视频 URL")
    parser.add_argument("--output-dir", "-o", default="./output", help="输出目录")
    parser.add_argument(
        "--lang",
        "-l",
        nargs="+",
        default=["zh", "en"],
        help="字幕语言列表 (默认: zh en)",
    )
    parser.add_argument(
        "--quality",
        "-q",
        default="bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        help="yt-dlp format 选择器",
    )
    parser.add_argument(
        "--cookies",
        "-c",
        help="浏览器名称或 Netscape cookies.txt 文件路径",
    )
    parser.add_argument(
        "--audio-only",
        "-a",
        action="store_true",
        help="仅下载音频",
    )
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()

    try:
        result = execute_download(
            url=args.url.strip(),
            output_dir=args.output_dir,
            languages=args.lang,
            quality=args.quality,
            audio_only=args.audio_only,
            cookies_from_browser=args.cookies,
        )
    except VlpError as exc:
        log.render_vlp_error(exc)
        if args.json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "url": args.url.strip(),
                        "error": exc.message,
                        "error_code": exc.error_code,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 1

    if result.get("success"):
        print("下载成功!")
        print(f"  文件夹: {result['folder']}")
        if result.get("video"):
            print(f"  视频: {result['video']}")
        if result.get("audio"):
            print(f"  音频: {result['audio']}")
        if result.get("subtitle"):
            print(f"  字幕: {result['subtitle']}")
        if result.get("subtitle_srt"):
            print(f"  SRT: {result['subtitle_srt']}")
        if result.get("info"):
            print(f"  信息: {result['info']}")
        if result.get("needs_whisper"):
            print("  提示: 当前下载结果没有字幕，后续可能需要转录。")
    else:
        log.error(str(result.get("error") or "下载失败"))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
