#!/usr/bin/env python3
"""
视频下载模块 - 使用 yt-dlp 从支持的URL下载视频、音频和字幕
"""

import argparse
import json
import os
import re
import sys
import time
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


def try_selenium_extract(url: str) -> Tuple[Optional[str], Optional[str], Optional[List]]:
    """
    尝试使用 Selenium 获取视频真实地址
    返回: (video_url, title, cookies)
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("⚠️  未安装 Selenium 相关依赖，无法自动尝试 Selenium 提取。")
        print("   请运行: pip install selenium webdriver_manager")
        return None, None, None

    print(f"\n🔄 尝试使用 Selenium 模拟浏览器访问: {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 无头模式
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = None
    try:
        # 初始化浏览器
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        driver.get(url)
        time.sleep(5)  # 等待页面加载和重定向
        
        # 尝试获取视频元素
        video_elements = driver.find_elements("tag name", "video")
        
        video_src = None
        for video in video_elements:
            src = video.get_attribute("src")
            if src and "blob" not in src:
                video_src = src
                break
            
            # 尝试查找 source 标签
            sources = video.find_elements("tag name", "source")
            for source in sources:
                src = source.get_attribute("src")
                if src:
                    video_src = src
                    break
            if video_src:
                break
        
        title = driver.title
        # 清理标题
        title = sanitize_filename(title)
        
        if video_src:
            print(f"✅ Selenium 成功获取视频地址!")
            return video_src, title, None
        else:
            print("⚠️ Selenium 未能直接获取视频地址，尝试提取 Cookies...")
            cookies = driver.get_cookies()
            return None, title, cookies

    except Exception as e:
        print(f"❌ Selenium 尝试失败: {e}")
        return None, None, None
    finally:
        if driver:
            driver.quit()


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
        # 检查是否为已知浏览器名称
        known_browsers = ["chrome", "firefox", "edge", "safari", "opera", "brave", "vivaldi"]
        if cookies_from_browser.lower() in known_browsers:
            ydl_opts["cookiesfrombrowser"] = (cookies_from_browser,)
        else:
            # 假设是文件路径
            if os.path.exists(cookies_from_browser):
                ydl_opts["cookiefile"] = cookies_from_browser
            else:
                print(f"⚠️ 警告: 未找到 Cookies 文件或未知的浏览器名称: {cookies_from_browser}")
                # 尝试作为浏览器名称传递，以防 yt-dlp 支持更多浏览器
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
        error_msg = str(e)
        
        # 检查是否为抖音链接且可能是反爬虫问题
        is_douyin = "douyin.com" in url or "tiktok.com" in url
        is_crawler_issue = "cookies" in error_msg.lower() or "verify" in error_msg.lower() or "403" in error_msg or "json" in error_msg.lower()
        
        if is_douyin and is_crawler_issue:
            print(f"\n⚠️ 检测到可能的反爬虫限制: {error_msg.splitlines()[0]}")
            print("🔄 正在切换到 Selenium 模式重试...")
            
            sel_url, sel_title, sel_cookies = try_selenium_extract(url)
            
            if sel_url:
                # 使用获取到的直链下载
                try:
                    # 更新下载选项
                    ydl_opts_retry = dict(ydl_opts)
                    # 必须指定文件名，因为直链通常没有元数据
                    if sel_title:
                        title = sel_title
                    else:
                        title = f"video_{int(time.time())}"
                        
                    dst_folder = output_path / title
                    dst_folder.mkdir(parents=True, exist_ok=True)
                    
                    ydl_opts_retry["outtmpl"] = {
                        "default": str(dst_folder / f"{title}.%(ext)s"),
                    }
                    # 直链通常不需要 cookies，但可能需要 headers，yt-dlp 会自动处理基础的
                    # 禁用证书检查，以防直链 HTTPS 问题
                    ydl_opts_retry["nocheckcertificate"] = True
                    
                    # 设置与 Selenium 一致的 User-Agent，并清空 Referer 以防防盗链
                    ydl_opts_retry["http_headers"] = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://www.douyin.com/",
                    }
                    
                    print(f"🚀 开始下载直链视频: {sel_title}")
                    with YoutubeDL(ydl_opts_retry) as ydl:
                        ydl.download([sel_url])
                    
                    # 填充成功结果
                    standardize_and_move_files(dst_folder, dst_folder)
                    result["folder"] = str(dst_folder)
                    result["title"] = title
                    result["video"] = str((dst_folder / "video.mp4").relative_to(output_path)) if (dst_folder / "video.mp4").exists() else None
                    result["success"] = True
                    result["error"] = None
                    return result
                    
                except Exception as retry_e:
                    print(f"❌ Selenium 辅助下载也失败了: {retry_e}")
                    error_msg += f"\n\n[Selenium 尝试失败]: {retry_e}"

            elif sel_cookies:
                # TODO: 使用提取的 Cookies 重试 (暂时仅提示用户)
                # 因为 yt-dlp 接受 cookiefile 或 browser，传递 dict 比较麻烦，需要转 cookiejar
                pass

        if "cookies" in error_msg.lower() and "needed" in error_msg.lower():
            error_msg += "\n\n💡 提示: 该网站可能需要 Cookies 才能访问。\n   请尝试添加 --cookies chrome (或 edge/firefox) 参数重试。\n   例如: python download_video.py ... --cookies chrome"
        result["error"] = error_msg
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
        help="从浏览器获取cookies (如 chrome, edge) 或 cookies.txt 文件路径",
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
