#!/usr/bin/env python3
"""Compatibility wrapper for legacy summary generation usage."""

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
from video_link_pipeline.config import load_config
from video_link_pipeline.errors import VlpError
from video_link_pipeline.summarize.service import summarize_transcript


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 视频摘要生成工具")
    parser.add_argument("--transcript", "-t", required=True, help="转录文本文件路径")
    parser.add_argument("--output-dir", "-o", default=None, help="输出目录")
    parser.add_argument(
        "--provider",
        "-p",
        choices=["claude", "openai", "gemini", "deepseek", "kimi", "moonshot", "minimax", "glm", "zhipu"],
        help="AI 提供商",
    )
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 结果")
    parser.add_argument("--model", help="模型名称")
    parser.add_argument("--base-url", help="兼容接口 Base URL")
    parser.add_argument("--max-tokens", type=int, help="最大输出 token 数")
    parser.add_argument("--temperature", type=float, help="采样温度")
    args = parser.parse_args()

    try:
        bundle = load_config(
            overrides={
                "output_dir": args.output_dir,
                "summary": {
                    "provider": args.provider,
                    "model": args.model,
                    "base_url": args.base_url,
                    "max_tokens": args.max_tokens,
                    "temperature": args.temperature,
                },
            }
        )
        result = summarize_transcript(
            transcript_path=args.transcript,
            output_dir=args.output_dir,
            config=bundle.effective_config,
        )
    except VlpError as exc:
        log.render_vlp_error(exc)
        if args.json:
            print(json.dumps({"success": False, "error": exc.message, "error_code": exc.error_code}, ensure_ascii=False, indent=2))
        return 1

    if not result.get("success"):
        log.error(str(result.get("error") or "摘要生成失败"))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print("摘要生成成功!")
    print(f"  Markdown: {result['summary_file']}")
    print(f"  JSON: {result['keywords_file']}")
    if result.get("one_sentence_summary"):
        print(f"  一句话概括: {result['one_sentence_summary']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
