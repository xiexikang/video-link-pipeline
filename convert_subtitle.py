#!/usr/bin/env python3
"""
字幕格式转换工具 - 支持 VTT 和 SRT 格式互转
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Optional


def parse_vtt_time(time_str: str) -> float:
    """解析 VTT 时间格式为秒数"""
    time_str = time_str.strip()
    if "." in time_str:
        time_str = time_str.replace(".", ",")
    
    parts = time_str.split(":")
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2].replace(",", "."))
    elif len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds = float(parts[1].replace(",", "."))
    else:
        hours = minutes = 0
        seconds = float(parts[0].replace(",", "."))
    
    return hours * 3600 + minutes * 60 + seconds


def format_srt_time(seconds: float) -> str:
    """将秒数格式化为 SRT 时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_vtt_time(seconds: float) -> str:
    """将秒数格式化为 VTT 时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def vtt_to_srt(vtt_content: str) -> str:
    """将 VTT 格式转换为 SRT 格式"""
    lines = vtt_content.strip().split("\n")
    
    # 跳过 WEBVTT 头部
    i = 0
    while i < len(lines) and (lines[i].strip() == "" or lines[i].strip().startswith("WEBVTT") or lines[i].strip().startswith("NOTE")):
        i += 1
    
    srt_lines = []
    cue_index = 1
    
    while i < len(lines):
        line = lines[i].strip()
        
        # 查找时间轴行
        if " --> " in line:
            time_parts = line.split(" --> ")
            start_time = parse_vtt_time(time_parts[0])
            end_time = parse_vtt_time(time_parts[1].split()[0])  # 去除可能有的位置信息
            
            # 收集文本行
            text_lines = []
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                # 去除 VTT 的 voice span 标签
                text = re.sub(r'<[^>]+>', '', lines[i].strip())
                if text:
                    text_lines.append(text)
                i += 1
            
            if text_lines:
                srt_lines.append(str(cue_index))
                srt_lines.append(f"{format_srt_time(start_time)} --> {format_srt_time(end_time)}")
                srt_lines.extend(text_lines)
                srt_lines.append("")
                cue_index += 1
        else:
            i += 1
    
    return "\n".join(srt_lines)


def srt_to_vtt(srt_content: str) -> str:
    """将 SRT 格式转换为 VTT 格式"""
    lines = srt_content.strip().split("\n")
    
    vtt_lines = ["WEBVTT", ""]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # 跳过序号行
        if line.isdigit():
            i += 1
            continue
        
        # 查找时间轴行
        if " --> " in line:
            time_parts = line.replace(",", ".").split(" --> ")
            start_time = time_parts[0].strip()
            end_time = time_parts[1].strip()
            
            vtt_lines.append(f"{start_time} --> {end_time}")
            
            # 收集文本行
            i += 1
            while i < len(lines) and lines[i].strip() != "":
                vtt_lines.append(lines[i].strip())
                i += 1
            
            vtt_lines.append("")
        else:
            i += 1
    
    return "\n".join(vtt_lines)


def convert_subtitle(input_path: str, output_path: Optional[str] = None, output_format: Optional[str] = None) -> bool:
    """
    转换字幕文件格式
    
    Args:
        input_path: 输入文件路径
        output_path: 输出文件路径 (可选)
        output_format: 输出格式 (vtt 或 srt)
    
    Returns:
        bool: 转换是否成功
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        print(f"❌ 错误: 文件不存在 {input_path}")
        return False
    
    # 读取输入文件
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        return False
    
    # 自动检测输入格式
    input_format = None
    if content.strip().startswith("WEBVTT"):
        input_format = "vtt"
    else:
        input_format = "srt"
    
    # 确定输出格式
    if not output_format:
        if input_format == "vtt":
            output_format = "srt"
        else:
            output_format = "vtt"
    
    # 确定输出路径
    if not output_path:
        if output_format == "srt":
            output_path = input_path.with_suffix(".srt")
        else:
            output_path = input_path.with_suffix(".vtt")
    else:
        output_path = Path(output_path)
    
    # 执行转换
    try:
        if input_format == "vtt" and output_format == "srt":
            result = vtt_to_srt(content)
        elif input_format == "srt" and output_format == "vtt":
            result = srt_to_vtt(content)
        elif input_format == output_format:
            print(f"⚠️  输入输出格式相同 ({input_format})，无需转换")
            return True
        else:
            print(f"❌ 不支持的转换: {input_format} -> {output_format}")
            return False
        
        # 写入输出文件
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)
        
        print(f"✅ 转换成功!")
        print(f"   输入: {input_path} ({input_format})")
        print(f"   输出: {output_path} ({output_format})")
        return True
        
    except Exception as e:
        print(f"❌ 转换失败: {e}")
        return False


def batch_convert(input_dir: str, output_format: str = "srt") -> int:
    """
    批量转换目录中的字幕文件
    
    Returns:
        int: 成功转换的文件数
    """
    input_dir = Path(input_dir)
    
    if not input_dir.exists():
        print(f"❌ 目录不存在: {input_dir}")
        return 0
    
    # 查找所有字幕文件
    if output_format == "srt":
        source_ext = ".vtt"
    else:
        source_ext = ".srt"
    
    files = list(input_dir.glob(f"**/*{source_ext}"))
    
    if not files:
        print(f"⚠️  未找到 {source_ext} 文件")
        return 0
    
    print(f"找到 {len(files)} 个 {source_ext} 文件")
    print(f"开始批量转换为 {output_format}...")
    print()
    
    success_count = 0
    for file_path in files:
        if convert_subtitle(str(file_path), output_format=output_format):
            success_count += 1
    
    print()
    print(f"批量转换完成: {success_count}/{len(files)} 成功")
    return success_count


def main():
    parser = argparse.ArgumentParser(description="字幕格式转换工具")
    parser.add_argument("--input", "-i", required=True, help="输入文件或目录路径")
    parser.add_argument("--output", "-o", help="输出文件路径")
    parser.add_argument(
        "--format", "-f",
        choices=["srt", "vtt"],
        help="输出格式 (srt 或 vtt，不指定则自动反向转换)"
    )
    parser.add_argument(
        "--batch", "-b",
        action="store_true",
        help="批量转换目录中的所有文件"
    )
    
    args = parser.parse_args()
    
    if args.batch:
        batch_convert(args.input, args.format or "srt")
    else:
        success = convert_subtitle(args.input, args.output, args.format)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
