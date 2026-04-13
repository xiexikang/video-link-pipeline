"""Selenium-powered browser fallback for difficult download pages."""

from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from ..errors import DependencyMissingError, VlpError

ANTI_CRAWL_MARKERS = (
    "403",
    "forbidden",
    "captcha",
    "verification",
    "verify you are human",
    "sign in",
    "login required",
    "cookies",
    "cookie",
    "access denied",
    "temporarily unavailable",
)


DEFAULT_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36"
)


@dataclass(slots=True)
class SeleniumContext:
    """Browser-derived context used to retry yt-dlp."""

    original_url: str
    resolved_url: str
    page_title: str
    user_agent: str
    referer: str
    cookie_file: Path
    page_description: str
    canonical_url: str
    media_hint_url: str
    site_name: str


class SeleniumFallbackError(VlpError):
    """Raised when Selenium fallback cannot produce a usable browser context."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="DOWNLOAD_FAILED", hint=hint)


def selenium_extra_available() -> bool:
    """Return whether the optional Selenium dependencies are installed."""
    return (
        importlib.util.find_spec("selenium") is not None
        and importlib.util.find_spec("webdriver_manager") is not None
    )


def should_attempt_selenium_fallback(mode: str, error_message: str | None) -> bool:
    """Decide whether Selenium fallback should run for the given mode and failure."""
    normalized_mode = (mode or "auto").strip().lower()
    if normalized_mode == "off":
        return False
    if normalized_mode == "on":
        return True
    if normalized_mode != "auto":
        return False
    if not error_message:
        return False

    lowered = error_message.lower()
    return any(marker in lowered for marker in ANTI_CRAWL_MARKERS)


def run_selenium_browser_context(*, url: str, workspace_dir: str | Path) -> SeleniumContext:
    """Open the URL in Selenium and export cookies plus useful request context."""
    if not selenium_extra_available():
        raise DependencyMissingError(
            "selenium fallback requested but optional dependencies are not installed",
            hint="install with: pip install 'video-link-pipeline[selenium]'",
        )

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager

    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    cookie_file = workspace / "selenium-cookies.txt"

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=412,915")
    options.add_argument("--lang=zh-CN")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={DEFAULT_MOBILE_USER_AGENT}")
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )
    try:
        driver.set_page_load_timeout(45)
        driver.get(url)
        time.sleep(3)
        _wait_for_document_ready(driver)
        _wait_for_media_signals(driver)
        time.sleep(2)

        resolved_url = driver.current_url or url
        if not resolved_url:
            raise SeleniumFallbackError("selenium fallback could not resolve a usable page URL")

        page_signals = _extract_page_signals(driver)
        user_agent = str(driver.execute_script("return navigator.userAgent") or DEFAULT_MOBILE_USER_AGENT)
        page_title = str(driver.title or "")
        _write_netscape_cookies(cookie_file, driver.get_cookies())

        return SeleniumContext(
            original_url=url,
            resolved_url=page_signals.get("resolved_url") or resolved_url,
            page_title=page_title,
            user_agent=user_agent,
            referer=page_signals.get("canonical_url") or resolved_url,
            cookie_file=cookie_file,
            page_description=page_signals.get("description") or "",
            canonical_url=page_signals.get("canonical_url") or resolved_url,
            media_hint_url=page_signals.get("media_hint_url") or resolved_url,
            site_name=page_signals.get("site_name") or _derive_site_name(resolved_url),
        )
    except Exception as exc:
        raise SeleniumFallbackError(
            "selenium fallback could not prepare browser context",
            hint=str(exc),
        ) from exc
    finally:
        driver.quit()


def _wait_for_document_ready(driver: object) -> None:
    try:
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(driver, 15).until(
            lambda current: current.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        return


def _wait_for_media_signals(driver: object) -> None:
    try:
        from selenium.webdriver.support.ui import WebDriverWait

        WebDriverWait(driver, 12).until(
            lambda current: bool(
                current.execute_script(
                    """
                    const video = document.querySelector('video, source[src], video source[src]');
                    const ogVideo = document.querySelector('meta[property="og:video"], meta[property="og:video:url"], meta[property="og:video:secure_url"]');
                    const ogUrl = document.querySelector('meta[property="og:url"], link[rel="canonical"]');
                    return video || ogVideo || ogUrl;
                    """
                )
            )
        )
    except Exception:
        return


def _extract_page_signals(driver: object) -> dict[str, str]:
    try:
        payload = driver.execute_script(
            """
            const read = (selector, attr = 'content') => {
              const node = document.querySelector(selector);
              if (!node) return '';
              return String(node.getAttribute(attr) || '').trim();
            };
            const videoNode = document.querySelector('video');
            const sourceNode = document.querySelector('video source[src], source[src]');
            return {
              resolved_url: String(window.location.href || '').trim(),
              canonical_url: read('link[rel="canonical"]', 'href') || read('meta[property="og:url"]'),
              description: read('meta[name="description"]') || read('meta[property="og:description"]') || read('meta[name="twitter:description"]'),
              site_name: read('meta[property="og:site_name"]') || read('meta[name="application-name"]'),
              media_hint_url:
                read('meta[property="og:video:secure_url"]') ||
                read('meta[property="og:video:url"]') ||
                read('meta[property="og:video"]') ||
                read('meta[property="twitter:player:stream"]') ||
                (videoNode ? String(videoNode.currentSrc || videoNode.src || '').trim() : '') ||
                (sourceNode ? String(sourceNode.getAttribute('src') || '').trim() : '')
            };
            """
        )
    except Exception:
        return {}
    return {key: str(value or "").strip() for key, value in dict(payload or {}).items() if value}


def _derive_site_name(url: str) -> str:
    netloc = urlparse(url).netloc.lower().strip()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _write_netscape_cookies(cookie_file: Path, cookies: list[dict[str, object]]) -> None:
    lines = [
        "# Netscape HTTP Cookie File",
        "# Generated by video-link-pipeline Selenium fallback",
    ]

    for cookie in cookies:
        domain = str(cookie.get("domain") or "")
        include_subdomains = "TRUE" if domain.startswith(".") else "FALSE"
        path = str(cookie.get("path") or "/")
        secure = "TRUE" if bool(cookie.get("secure")) else "FALSE"
        expiry = str(int(cookie.get("expiry", 0) or 0))
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        lines.append("\t".join([domain, include_subdomains, path, secure, expiry, name, value]))

    cookie_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
