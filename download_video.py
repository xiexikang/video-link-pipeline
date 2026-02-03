#!/usr/bin/env python3
"""
视频下载模块 - 使用 yt-dlp 从支持的URL下载视频、音频和字幕
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import shutil
import yaml
from yt_dlp import YoutubeDL


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filename = re.sub(r'\s+', "_", filename)
    filename = re.sub(r'_+', "_", filename)
    return filename.strip("_.")


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def find_ffmpeg() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg as i_ffmpeg
        return i_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def download_video(
    url: str,
    output_dir: str = "./output",
    languages: List[str] = None,
    quality: str = "best",
    cookies_from_browser: Optional[str] = None,
    write_info: bool = True,
) -> Dict:
    """
    下载视频、音频和字幕

    Args:
        url: 视频URL
        output_dir: 输出目录
        languages: 字幕语言列表
        quality: 视频质量
        cookies_from_browser: 从浏览器获取cookies

    Returns:
        dict: 下载结果信息
    """
    if languages is None:
        languages = ["zh", "en"]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = find_ffmpeg()
    ydl_opts = {
        "format": f"bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt/srt",
        "writeinfojson": write_info,
        "outtmpl": {
            "default": str(output_path / "%(title)s" / "%(title)s.%(ext)s"),
        },
        "quiet": False,
        "no_warnings": False,
    }

    if ffmpeg_path:
        ydl_opts["ffmpeg_location"] = ffmpeg_path
    else:
        ydl_opts["format"] = "best[ext=mp4]/best"
        ydl_opts.pop("merge_output_format", None)

    if cookies_from_browser:
        ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)

    result = {
        "folder": None,
        "video": None,
        "audio": None,
        "subtitle": None,
        "subtitle_srt": None,
        "info": None,
        "needs_whisper": False,
        "success": False,
        "error": None,
    }

    try:
        with YoutubeDL(ydl_opts) as ydl_probe:
            probe_info = ydl_probe.extract_info(url, download=False)
            raw_title = probe_info.get("title", "unknown")
            title = sanitize_filename(raw_title)

        dst_folder = output_path / title
        dst_folder.mkdir(parents=True, exist_ok=True)

        ydl_opts_dl = dict(ydl_opts)
        ydl_opts_dl["outtmpl"] = {
            "default": str(dst_folder / f"{title}.%(ext)s"),
        }

        with YoutubeDL(ydl_opts_dl) as ydl:
            info = ydl.extract_info(url, download=True)

        standardize_and_move_files(dst_folder, dst_folder)

        result["folder"] = str(dst_folder)
        result["title"] = title

        video_file = dst_folder / "video.mp4"
        if video_file.exists():
            result["video"] = str(video_file.relative_to(output_path))

        subtitle_vtt = dst_folder / "subtitle.vtt"
        subtitle_srt = dst_folder / "subtitle.srt"

        if subtitle_vtt.exists():
            result["subtitle"] = str(subtitle_vtt.relative_to(output_path))
            result["subtitle_vtt"] = str(subtitle_vtt.relative_to(output_path))

        if subtitle_srt.exists():
            result["subtitle_srt"] = str(subtitle_srt.relative_to(output_path))

        if not result["subtitle"]:
            result["needs_whisper"] = True

        info_file = dst_folder / "info.json"
        if info_file.exists() and write_info:
            result["info"] = str(info_file.relative_to(output_path))

        result["success"] = True

    except Exception as e:
        result["error"] = str(e)
        result["success"] = False

    return result


def standardize_and_move_files(src_folder: Path, dst_folder: Path):
    try:
        if src_folder.exists():
            mp4_files = list(src_folder.glob("*.mp4"))
            if mp4_files:
                dst = dst_folder / "video.mp4"
                if not dst.exists():
                    mp4_files[0].rename(dst)
            m4a_files = list(src_folder.glob("*.m4a"))
            if m4a_files:
                dst = dst_folder / "audio.m4a"
                if not dst.exists():
                    m4a_files[0].rename(dst)
            mp3_files = list(src_folder.glob("*.mp3"))
            if mp3_files:
                dst = dst_folder / "audio.mp3"
                if not dst.exists():
                    mp3_files[0].rename(dst)
            vtt_files = list(src_folder.glob("*.vtt"))
            if vtt_files:
                def pick(files):
                    zh = [f for f in files if ".zh" in f.name or "zh-hans" in f.name]
                    en = [f for f in files if ".en" in f.name]
                    return (zh or en or files)[0]
                src = pick(vtt_files)
                dst = dst_folder / "subtitle.vtt"
                if not dst.exists():
                    src.rename(dst)
            srt_files = list(src_folder.glob("*.srt"))
            if srt_files:
                def pick(files):
                    zh = [f for f in files if ".zh" in f.name or "zh-hans" in f.name]
                    en = [f for f in files if ".en" in f.name]
                    return (zh or en or files)[0]
                src = pick(srt_files)
                dst = dst_folder / "subtitle.srt"
                if not dst.exists():
                    src.rename(dst)
            info_files = list(src_folder.glob("*.info.json"))
            if info_files:
                dst = dst_folder / "info.json"
                if not dst.exists():
                    info_files[0].rename(dst)
            try:
                remaining = list(src_folder.glob("*"))
                if not remaining:
                    src_folder.rmdir()
            except Exception:
                pass
    except Exception:
        pass


def extract_audio(video_path: str, output_path: str) -> bool:
    """从视频提取音频为MP3"""
    try:
        import ffmpeg

        video_path = Path(video_path)
        output_path = Path(output_path)

        if output_path.exists():
            return True

        process = (
            ffmpeg.input(str(video_path))
            .output(str(output_path), vn=True, acodec="libmp3lame", q="2")
            .overwrite_output()
        )
        process.run(quiet=True)
        return True
    except Exception as e:
        print(f"提取音频失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="视频下载工具")
    parser.add_argument("url", help="视频URL")
    parser.add_argument(
        "--output-dir", "-o", default="./output", help="输出目录"
    )
    parser.add_argument(
        "--lang",
        "-l",
        nargs="+",
        default=["zh", "en"],
        help="字幕语言 (默认: zh en)",
    )
    parser.add_argument(
        "--quality", "-q", default="best", help="视频质量 (默认: best)"
    )
    parser.add_argument(
        "--cookies",
        "-c",
        choices=["chrome", "firefox", "edge", "safari"],
        help="从浏览器获取cookies",
    )
    parser.add_argument(
        "--audio-only", "-a", action="store_true", help="仅下载音频"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="输出JSON格式"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()
    if config:
        download_config = config.get("download", {})
        if not args.cookies:
            args.cookies = download_config.get("cookies_from_browser")

    print(f"正在下载: {args.url}")
    print(f"输出目录: {args.output_dir}")

    result = download_video(
        url=args.url,
        output_dir=args.output_dir,
        languages=args.lang,
        quality=args.quality,
        cookies_from_browser=args.cookies,
    )

    if result["success"]:
        print(f"\n✅ 下载成功!")
        print(f"📁 文件夹: {result['folder']}")

        if result["video"]:
            print(f"🎬 视频: {result['video']}")

        if result["subtitle"]:
            print(f"📝 字幕: {result['subtitle']}")
            if result.get("is_auto_sub"):
                print("   (自动生成字幕)")
        else:
            print("⚠️  未找到字幕，需要Whisper转录")
            print(f"   运行: python parallel_transcribe.py --input {result['folder']}/video.mp4")

        if result.get("needs_whisper"):
            print("\n🔊 需要语音转录，运行:")
            print(
                f"   python parallel_transcribe.py --input {result['folder']}/video.mp4"
            )
    else:
        print(f"\n❌ 下载失败: {result['error']}")
        sys.exit(1)

    if args.json:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))

    return result


if __name__ == "__main__":
    main()
