#!/usr/bin/env python3
"""Compatibility wrapper for legacy transcription usage."""

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
from video_link_pipeline.errors import VlpError
from video_link_pipeline.transcribe.service import transcribe_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Whisper 语音转录工具")
    parser.add_argument("--input", "-i", required=True, help="输入音频或视频文件路径")
    parser.add_argument("--output-dir", "-o", default=None, help="输出目录")
    parser.add_argument("--model", "-m", default="small", help="模型大小")
    parser.add_argument("--language", "-l", default="auto", help="语言代码")
    parser.add_argument("--device", "-d", default="auto", help="计算设备")
    parser.add_argument("--compute-type", "-c", default="int8", help="计算类型")
    parser.add_argument(
        "--engine",
        "-e",
        default="auto",
        choices=["auto", "faster", "openai", "faster_whisper", "openai_whisper"],
        help="转录引擎",
    )
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 结果")
    args = parser.parse_args()

    try:
        result = transcribe_path(
            input_path=args.input,
            output_dir=args.output_dir,
            model_size=args.model,
            language=args.language,
            device=args.device,
            compute_type=args.compute_type,
            engine=args.engine,
        )
    except VlpError as exc:
        log.render_vlp_error(exc)
        if args.json:
            print(json.dumps({"success": False, "error": exc.message, "error_code": exc.error_code}, ensure_ascii=False, indent=2))
        return 1

    if not result.get("success"):
        log.error(str(result.get("error") or "转录失败"))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print("转录成功!")
    print(f"  文本: {result['transcript_file']}")
    print(f"  SRT: {result['srt_file']}")
    print(f"  VTT: {result['vtt_file']}")
    if result.get("detected_language"):
        print(f"  语言: {result['detected_language']}")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
