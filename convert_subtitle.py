#!/usr/bin/env python3
"""Compatibility wrapper for subtitle conversion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))

from video_link_pipeline.errors import VlpError
from video_link_pipeline import logging as log
from video_link_pipeline.subtitles.convert import batch_convert_subtitles, convert_subtitle_file


def main() -> int:
    parser = argparse.ArgumentParser(description="字幕格式转换工具")
    parser.add_argument("--input", "-i", required=True, help="输入文件或目录路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument(
        "--format",
        "-f",
        choices=["srt", "vtt"],
        help="输出格式 (srt 或 vtt，不指定则自动反向转换)",
    )
    parser.add_argument(
        "--batch",
        "-b",
        action="store_true",
        help="批量转换目录中的所有字幕文件",
    )
    args = parser.parse_args()

    try:
        if args.batch:
            result = batch_convert_subtitles(args.input, args.format or "srt")
            print(f"找到 {result['matched_files']} 个待处理文件")
            print(f"批量转换完成: {result['converted_files']}/{result['matched_files']} 成功")
            return 0

        result = convert_subtitle_file(args.input, output_path=args.output, output_format=args.format)
        if result["changed"]:
            print("转换成功!")
        else:
            print(f"提示: {result['message']}")
        print(f"  输入: {result['input_path']} ({result['input_format']})")
        print(f"  输出: {result['output_path']} ({result['output_format']})")
        return 0
    except VlpError as exc:
        log.render_vlp_error(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
