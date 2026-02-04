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
import urllib.request
import gzip
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


def parse_cookie_file(cookie_file: str) -> List[dict]:
    """解析 Netscape 格式的 cookies 文件"""
    cookies = []
    try:
        with open(cookie_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                fields = line.strip().split('\t')
                if len(fields) >= 7:
                    cookie = {
                        'domain': fields[0],
                        'flag': fields[1] == 'TRUE',
                        'path': fields[2],
                        'secure': fields[3] == 'TRUE',
                        'expiration': fields[4],
                        'name': fields[5],
                        'value': fields[6]
                    }
                    cookies.append(cookie)
    except Exception as e:
        print(f"⚠️ 解析 Cookies 文件失败: {e}")
    return cookies


def extract_kuaishou_info_fallback(url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    尝试不依赖 Selenium，通过简单的请求或 URL 解析获取信息
    Returns: (video_id, title)
    """
    video_id = None
    title = None
    
    # 1. 从 URL 提取 ID
    # https://www.kuaishou.com/short-video/3xqy7yy5tbdgrrw
    match = re.search(r'short-video/([a-zA-Z0-9]+)', url)
    if not match:
        match = re.search(r'photo/([a-zA-Z0-9]+)', url)
    
    if match:
        video_id = match.group(1)
        
    # 2. 尝试获取网页标题 (简单的请求有时候能绕过某些检测，或者获取到静态 Meta 信息)
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        }
        req = urllib.request.Request(url, headers=headers)
        # 短超时，因为如果需要 Captcha 通常会 redirect 或卡住
        with urllib.request.urlopen(req, timeout=5) as response:
            content = response.read()
            # Handle gzip
            if response.info().get('Content-Encoding') == 'gzip':
                content = gzip.decompress(content)
            
            html = content.decode('utf-8', errors='ignore')
            
            # Extract title from <title>
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                raw_title = title_match.group(1)
                # Kuaishou titles often end with " - 快手"
                raw_title = raw_title.replace(" - 快手", "").strip()
                if raw_title and raw_title != "快手" and raw_title != "Kuaishou":
                    title = sanitize_filename(raw_title)

            # Extract title from meta description (often contains the caption)
            if not title:
                 desc_match = re.search(r'<meta\s+name="description"\s+content="(.*?)"', html)
                 if desc_match:
                     desc = desc_match.group(1)
                     desc = desc.replace(" - 快手", "").strip()
                     if desc:
                         title = sanitize_filename(desc)
                         
    except Exception as e:
        # print(f"⚠️ Fallback title extraction failed: {e}")
        pass
        
    return video_id, title


def extract_video_from_html(page_source: str) -> Optional[str]:
    """
    从 HTML 源码中提取视频链接 (融合原 analyze_html.py 的逻辑)
    """
    # 1. 常见 JSON 字段匹配
    patterns = [
        r'"srcNoMark":"(https?://[^"]+)"',
        r'"photoUrl":"(https?://[^"]+)"',
        r'"url":"(https?://[^"]+)"',
        r'"backupUrl":\["(https?://[^"]+)"',
        # 快手特定
        r'"manifest":{"adaptationSet":\[{"representation":\[{"url":"(https?://[^"]+)"',
    ]
    
    for pattern in patterns:
        try:
            match = re.search(pattern, page_source)
            if match:
                found_url = match.group(1)
                # 处理转义字符
                if "\\" in found_url:
                    try:
                        found_url = found_url.encode('utf-8').decode('unicode_escape')
                    except:
                        pass
                
                # 过滤非视频链接
                if (".mp4" in found_url or "video" in found_url) and "blob:" not in found_url:
                    return found_url
        except Exception as e:
            print(f"⚠️ 正则匹配解析错误: {e}")
            continue

    return None


def try_selenium_extract(url: str, cookie_file: Optional[str] = None) -> Tuple[Optional[str], Optional[str], Optional[List]]:
    """
    尝试使用 Selenium 获取视频真实地址
    返回: (video_url, title, cookies)
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        print("⚠️  未安装 Selenium 相关依赖，无法自动尝试 Selenium 提取。")
        print("   请运行: pip install selenium webdriver_manager")
        return None, None, None

    print(f"\n🔄 尝试使用 Selenium 模拟浏览器访问: {url}")
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # 新版无头模式，更像真实浏览器
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--window-size=1920,1080")
    # 切换回桌面端 UA 尝试绕过验证码
    # chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    # 启用移动端模拟
    mobile_emulation = { "deviceName": "iPhone X" }
    chrome_options.add_experimental_option("mobileEmulation", mobile_emulation)
    # 反爬虫检测规避
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Enable performance logging to capture network requests
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
    
    driver = None
    try:
        # 初始化浏览器
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        # 规避 webdriver 检测
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['zh-CN', 'zh', 'en']
            });
            window.chrome = {
                runtime: {}
            };
            """
        })
        
        # 如果提供了 Cookies 文件，先加载域名再注入 Cookies
        if cookie_file and os.path.exists(cookie_file):
            print(f"🍪 正在加载 Cookies 文件: {cookie_file}")
            # 先访问主域以设置 Cookie
            domain = "https://www.douyin.com" if "douyin.com" in url else "https://www.kuaishou.com"
            try:
                driver.get(domain)
                time.sleep(2)
                
                cookies = parse_cookie_file(cookie_file)
                count = 0
                for cookie in cookies:
                    # 仅添加当前域名的 cookie，避免跨域错误
                    if cookie['domain'] in domain or ("." + cookie['domain']) in domain or domain in cookie['domain']:
                        # Selenium add_cookie 需要的字段: name, value, domain, path, secure
                        cookie_dict = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'path': cookie['path'],
                            'secure': cookie['secure']
                        }
                        # 处理 expiry
                        if cookie['expiration'] and cookie['expiration'] != '0':
                             try:
                                 cookie_dict['expiry'] = int(cookie['expiration'])
                             except:
                                 pass
                                 
                        try:
                            driver.add_cookie(cookie_dict)
                            count += 1
                        except Exception as ce:
                            pass
                            
                print(f"✅ 已注入 {count} 个 Cookies")
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ 注入 Cookies 失败: {e}")

        driver.get(url)

        time.sleep(5)  # 等待页面加载和重定向
        
        print(f"📄 当前页面标题: {driver.title}")
        print(f"🔗 当前页面URL: {driver.current_url}")
        
        # 检查是否发生了错误的重定向 (针对快手)
        if "kuaishou.com" in url and "short-video" in url:
            # 提取原始ID
            input_id_match = re.search(r'short-video/([a-zA-Z0-9]+)', url)
            if input_id_match:
                input_id = input_id_match.group(1)
                if input_id not in driver.current_url:
                    print(f"⚠️ 警告: 页面发生了重定向 (期望ID: {input_id})，可能被反爬虫系统拦截跳转到了推荐页。")
                    print("   这通常是因为没有登录 Cookies。尝试继续提取，但结果可能不正确...")
        
        # 模拟滚动以触发懒加载
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
        time.sleep(2)

        # 尝试获取视频元素
        video_elements = driver.find_elements("tag name", "video")
        print(f"🔍 找到 {len(video_elements)} 个 video 标签")
        
        video_src = None
        for video in video_elements:
            # 尝试获取 src 属性和 currentSrc 属性
            src_attr = video.get_attribute("src")
            current_src = video.get_property("currentSrc")
            
            print(f"🔍 Video 标签检测 - src属性: {src_attr}, currentSrc属性: {current_src}")
            
            # 优先使用 currentSrc
            if current_src and "blob:" not in current_src and len(current_src) > 0:
                video_src = current_src
                break
                
            if src_attr and "blob:" not in src_attr and len(src_attr) > 0:
                video_src = src_attr
                break
            
            # 尝试查找 source 标签
            sources = video.find_elements("tag name", "source")
            for source in sources:
                src = source.get_attribute("src")
                print(f"🔍 发现 source 标签 src: {src[:100] if src else 'None'}")
                if src and "blob:" not in src:
                    video_src = src
                    break
            
            if video_src:
                break
                
            # 尝试点击播放以触发网络请求
            try:
                print("🖱️ 尝试点击视频元素以触发加载...")
                driver.execute_script("arguments[0].click();", video)
                time.sleep(1)
            except Exception as e:
                print(f"⚠️ 点击视频失败: {e}")

        # 如果 DOM 中未找到，尝试检查网络日志
        if not video_src:
            print("🔍 检查网络日志寻找视频流...")
            try:
                logs = driver.get_log('performance')
                for entry in logs:
                    try:
                        message = json.loads(entry['message'])['message']
                        if message['method'] == 'Network.responseReceived':
                            resp_url = message['params']['response']['url']
                            mime_type = message['params']['response'].get('mimeType', '')
                            
                            # 检查视频相关特征
                            is_video = False
                            if any(ext in resp_url for ext in ['.mp4', '.m3u8', '.flv', '.ts']):
                                is_video = True
                            if 'video/' in mime_type:
                                is_video = True
                                
                            if is_video:
                                print(f"🔍 网络日志捕获潜在视频: {resp_url[:100]}... Type: {mime_type}")
                                # 排除 blob: 协议 (通常无法直接下载) 和非视频域名的干扰
                                if 'blob:' not in resp_url and '.js' not in resp_url and '.css' not in resp_url:
                                    # 排除头像等图片被误识别为视频的情况
                                    if "kuaishou" in resp_url or "kwaicdn" in resp_url or "yximgs" in resp_url:
                                        print(f"✅ 从网络日志中确认视频链接: {resp_url[:100]}...")
                                        video_src = resp_url
                                        break
                    except:
                        pass
            except Exception as e:
                print(f"⚠️ 读取网络日志失败: {e}")

        # 如果找不到 video 标签 src，尝试从页面源码中正则提取
        if not video_src:
            print("⚠️ 未能在 DOM 中直接找到视频 src，尝试从页面源码提取...")
            page_source = driver.page_source
            
            # 保存页面源码以便调试 (原 debug_kuaishou.html 逻辑) - 已禁用
            # try:
            #     with open("debug_kuaishou.html", "w", encoding="utf-8") as f:
            #         f.write(page_source)
            #     print("📄 已保存页面源码到 debug_kuaishou.html")
            # except Exception as e:
            #     print(f"⚠️ 保存 debug_kuaishou.html 失败: {e}")
            
            # 使用融合的分析逻辑提取视频
            video_src = extract_video_from_html(page_source)
            if video_src:
                print(f"✅ 通过源码分析提取到视频地址: {video_src[:100]}...")
        
        # 尝试获取视频标题（针对移动端页面优化）
        try:
            print("🔍 正在尝试提取视频标题...")
            wait = WebDriverWait(driver, 10) # 增加等待时间
            
            # 方法1: 从 page_source 正则提取 <title>
            # import re # Removed redundant import
            page_source = driver.page_source
            
            # 保存调试文件以便分析
            # with open("debug_kuaishou.html", "w", encoding="utf-8") as f:
            #     f.write(page_source)

            # 尝试提取 <title> 标签内容
            title_match = re.search(r'<title>(.*?)</title>', page_source)
            if title_match:
                extracted_title = title_match.group(1)
                if extracted_title and "快手" in extracted_title and len(extracted_title) > 10:
                    print(f"✅ 从源码 <title> 提取标题: {extracted_title[:50]}...")
                    # 移除 "-快手" 后缀
                    extracted_title = extracted_title.replace("-快手", "").replace("- 快手", "")
                    driver.execute_script("document.title = arguments[0]", f"{extracted_title} - 快手")

            # 方法2: 尝试从 video-info-title 类获取 (正则匹配，避免元素查找问题)
            if driver.title == "快手" or driver.title == "Kuaishou":
                 # 尝试多种选择器
                 possible_selectors = [
                     ".video-info-title", 
                     ".text.txt", 
                     ".photo-info .title",
                     "h1",
                     ".video-desc"
                 ]
                 
                 found_title = False
                 for selector in possible_selectors:
                     try:
                         elements = driver.find_elements(By.CSS_SELECTOR, selector)
                         for element in elements:
                             text = element.text
                             # 过滤掉太短的或者无关的文本
                             if text and len(text) > 5 and "快手" not in text and "点击" not in text:
                                 print(f"✅ 从元素 {selector} 获取标题: {text[:50]}...")
                                 driver.execute_script("document.title = arguments[0]", f"{text} - 快手")
                                 found_title = True
                                 break
                         if found_title:
                             break
                     except Exception as e:
                         # print(f"尝试选择器 {selector} 失败: {e}")
                         pass
                 
                 # 如果元素查找失败，尝试正则匹配源码
                 if not found_title:
                      # 匹配 <span class="text txt"...>...</span>
                      txt_match = re.search(r'class="[^"]*text\s+txt[^"]*".*?>\s*(.*?)\s*<', page_source, re.DOTALL)
                      if txt_match:
                          video_text = txt_match.group(1).strip()
                          if video_text:
                              print(f"✅ 从源码 .text.txt 提取标题: {video_text[:50]}...")
                              driver.execute_script("document.title = arguments[0]", f"{video_text} - 快手")

        except Exception as e:
            print(f"⚠️ 标题提取过程出错: {e}")
            pass

        title = driver.title
        # 如果标题太短或为通用标题，尝试再次查找
        if not title or title.strip() == "快手" or title.strip() == "Kuaishou":
             try:
                # 尝试直接读取 <title> 标签的 innerText，有时候 driver.title 没更新
                raw_title = driver.execute_script("return document.getElementsByTagName('title')[0].innerText")
                if raw_title and raw_title.strip() != "快手":
                     title = raw_title
             except:
                 pass

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
    audio_only: bool = False,
) -> Dict:
    """
    下载视频、音频和字幕

    Args:
        url: 视频URL
        output_dir: 输出目录
        languages: 字幕语言列表
        quality: 视频质量
        cookies_from_browser: 从浏览器获取cookies
        audio_only: 仅下载音频

    Returns:
        dict: 下载结果信息
    """
    if languages is None:
        languages = ["zh", "en"]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    ffmpeg_path = find_ffmpeg()
    
    if audio_only:
        ydl_opts = {
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            "writesubtitles": False, # 音频通常不需要字幕，或者视需求而定
            "writeinfojson": write_info,
            "outtmpl": {
                "default": str(output_path / "%(title)s" / "%(title)s.%(ext)s"),
            },
            "quiet": False,
            "no_warnings": False,
        }
    else:
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
    
    title = None

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

        # 验证下载的文件是否有效
        video_file = dst_folder / "video.mp4"
        
        # 1. 检查是否生成了目标视频文件
        if not video_file.exists():
            # 检查目录下是否有其他文件 (如下载到了 unknown_video 但没被重命名)
            all_files = list(dst_folder.glob("*"))
            if all_files:
                # 如果只有小文件，视为失败
                if all(f.stat().st_size < 100 * 1024 for f in all_files): # < 100KB
                    print(f"⚠️ 下载失败: 未找到有效视频文件，仅存在小文件: {[f.name for f in all_files]}")
                    try:
                        import shutil
                        shutil.rmtree(dst_folder)
                    except:
                        pass
                    raise Exception("Download failed: No valid video file found (only small files)")
            else:
                 try:
                     dst_folder.rmdir()
                 except:
                     pass
                 raise Exception("Download failed: No files downloaded")

        # 2. 检查视频文件大小
        if video_file.exists() and video_file.stat().st_size < 100 * 1024:
            # 文件存在但太小 (< 100KB)，视为失败
            print(f"⚠️ 下载的文件过小 ({video_file.stat().st_size} bytes)，可能是无效文件或反爬虫拦截。")
            # 删除无效文件
            try:
                import shutil
                shutil.rmtree(dst_folder)
            except:
                pass
            raise Exception("Downloaded file is too small (likely anti-crawling response)")

        result["folder"] = str(dst_folder)
        result["title"] = title

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
        
        # 检查是否为短视频链接 (抖音/快手/TikTok) 且可能是反爬虫问题
        is_short_video = any(d in url for d in ["douyin.com", "tiktok.com", "kuaishou.com", "chenzhongtech.com"])
        is_crawler_issue = (
            "cookie" in error_msg.lower() 
            or "verify" in error_msg.lower() 
            or "403" in error_msg 
            or "json" in error_msg.lower()
            or "downloaded file is too small" in error_msg.lower()
            or "unsupported url" in error_msg.lower()
            or "no valid video file" in error_msg.lower()
            or "no files downloaded" in error_msg.lower()
        )
        
        if is_short_video and is_crawler_issue:
            print(f"\n⚠️ 检测到可能的反爬虫限制: {error_msg.splitlines()[0]}")
            
            if "could not copy" in error_msg.lower() and "database" in error_msg.lower():
                print("💡 提示: yt-dlp 无法读取浏览器 Cookies，通常是因为浏览器正在运行。")
                print("   请尝试关闭浏览器后重试，或使用 --cookies cookies.txt 方式。")
            
            print("🔄 正在切换到 Selenium 模式重试...")
            
            sel_url, sel_title, sel_cookies = try_selenium_extract(url, cookies_from_browser)
            
            if sel_url:
                # 使用获取到的直链下载
                try:
                    # 更新下载选项
                    ydl_opts_retry = dict(ydl_opts)
                    # 必须指定文件名，因为直链通常没有元数据
                    if sel_title:
                        title = sel_title
                    elif title and title != "unknown" and "video_" not in title:
                        # 使用之前 yt-dlp 提取到的标题 (如果有)
                        print(f"ℹ️ 使用之前提取的标题: {title}")
                        pass
                    else:
                        # 尝试 Fallback 提取标题
                        fb_id, fb_title = extract_kuaishou_info_fallback(url)
                        if fb_title:
                            title = fb_title
                            print(f"✅ 使用 Fallback 提取的标题: {title}")
                        elif fb_id:
                            title = fb_id
                            print(f"ℹ️ 使用视频 ID 作为标题: {title}")
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
                    referer = "https://www.douyin.com/" if "douyin" in url else "https://www.kuaishou.com/"
                    ydl_opts_retry["http_headers"] = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": referer,
                    }
                    
                    print(f"🚀 开始下载直链视频: {title}")
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

    # 清理 URL 中的空白字符
    args.url = args.url.strip()

    print(f"正在下载: {args.url}")
    print(f"输出目录: {args.output_dir}")

    result = download_video(
        url=args.url,
        output_dir=args.output_dir,
        languages=args.lang,
        quality=args.quality,
        cookies_from_browser=args.cookies,
        audio_only=args.audio_only,
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
