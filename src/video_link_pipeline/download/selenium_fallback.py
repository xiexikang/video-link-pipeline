"""Selenium-powered browser fallback for difficult download pages."""

from __future__ import annotations

import ast
import json
import importlib.util
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .diagnostics import selenium_extra_install_hint
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

INLINE_STATE_SOURCES = (
    "__INITIAL_STATE__",
    "__NUXT__",
    "__NEXT_DATA__",
    "__INITIAL_PROPS__",
    "__APP_DATA__",
    "__DATA__",
    "__STATE__",
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
    extraction_source: str


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
            hint=selenium_extra_install_hint(),
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
            extraction_source=page_signals.get("extraction_source") or "dom",
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
                    const contentUrl = document.querySelector('meta[itemprop="contentUrl"]');
                    const twitterPlayer = document.querySelector('meta[property="twitter:player"], meta[name="twitter:player"]');
                    const ogUrl = document.querySelector('meta[property="og:url"], link[rel="canonical"]');
                    const nextData = document.querySelector('#__NEXT_DATA__');
                    const jsonLd = document.querySelector('script[type="application/ld+json"]');
                    const inlineScripts = Array.from(document.scripts || []).slice(0, 20);
                    const inlineStateSignal = inlineScripts.some(script => {
                      const text = String(script.textContent || '');
                      if (!text) return false;
                      return /__INITIAL_STATE__|__NUXT__|__NEXT_DATA__|__INITIAL_PROPS__|__APP_DATA__|__DATA__|__STATE__|playAddr|m3u8|mpd|dash/i.test(text);
                    });
                    const globals =
                      window.__INITIAL_STATE__ ||
                      window.__NUXT__ ||
                      window.__NEXT_DATA__ ||
                      window.__INITIAL_PROPS__ ||
                      window.__APP_DATA__ ||
                      window.__DATA__ ||
                      window.__STATE__ ||
                      window._ROUTER_DATA;
                    return video || ogVideo || contentUrl || twitterPlayer || ogUrl || nextData || jsonLd || globals || inlineStateSignal;
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
            const mediaCandidates = [];
            const read = (selector, attr = 'content') => {
              const node = document.querySelector(selector);
              if (!node) return '';
              return String(node.getAttribute(attr) || '').trim();
            };
            const pushCandidate = (value, source) => {
              if (!value) return;
              const normalized = String(value).trim();
              if (!normalized) return;
              mediaCandidates.push({ url: normalized, source });
            };
            const inlineStateSources = [
              '__INITIAL_STATE__',
              '__NUXT__',
              '__NEXT_DATA__',
              '__INITIAL_PROPS__',
              '__APP_DATA__',
              '__DATA__',
              '__STATE__'
            ];
            const pickFromObject = (input, source, depth = 0) => {
              if (!input || depth > 5) return;
              if (Array.isArray(input)) {
                input.slice(0, 20).forEach(item => pickFromObject(item, source, depth + 1));
                return;
              }
              if (typeof input !== 'object') return;
              const keys = [
                'playAddr', 'play_url', 'playUrl', 'src', 'url', 'uri', 'downloadUrl',
                'download_url', 'streamUrl', 'stream_url', 'm3u8', 'm3u8_url',
                'hls', 'hls_url', 'dash', 'dashUrl', 'dash_url'
              ];
              for (const key of keys) {
                if (key in input) {
                  const value = input[key];
                  if (typeof value === 'string') {
                    pushCandidate(value, source + ':' + key);
                  } else if (value && typeof value === 'object') {
                    pickFromObject(value, source + ':' + key, depth + 1);
                  }
                }
              }
              Object.values(input).slice(0, 30).forEach(value => {
                if (value && typeof value === 'object') {
                  pickFromObject(value, source, depth + 1);
                }
              });
            };
            const pickFromInlineScriptText = (text) => {
              if (!text) return;

              for (const stateName of inlineStateSources) {
                const parsePattern = new RegExp(
                  '(?:window\\\\.)?' + stateName + '\\\\s*=\\\\s*JSON\\\\.parse\\\\(\\\\s*([\"\\\'])((?:\\\\\\\\.|(?!\\\\1)[\\\\s\\\\S])*)\\\\1\\\\s*\\\\)',
                  'i'
                );
                const parseMatch = text.match(parsePattern);
                if (parseMatch) {
                  try {
                    const decoded = JSON.parse(parseMatch[1] + parseMatch[2] + parseMatch[1]);
                    pickFromObject(JSON.parse(decoded), 'window.' + stateName);
                  } catch (error) {}
                }
              }

              const matches = text.match(/https?:[^"'\\s]+(?:m3u8|mp4|mpd)[^"'\\s]*/ig) || [];
              matches.slice(0, 10).forEach(url => pushCandidate(url, 'inline-script'));
            };
            const videoNode = document.querySelector('video');
            const sourceNode = document.querySelector('video source[src], source[src]');
            if (videoNode) {
              pushCandidate(videoNode.currentSrc || videoNode.src || '', 'dom:video');
            }
            if (sourceNode) {
              pushCandidate(sourceNode.getAttribute('src') || '', 'dom:source');
            }
            pushCandidate(read('meta[property="og:video:secure_url"]'), 'meta:og:video:secure_url');
            pushCandidate(read('meta[property="og:video:url"]'), 'meta:og:video:url');
            pushCandidate(read('meta[property="og:video"]'), 'meta:og:video');
            pushCandidate(read('meta[property="twitter:player:stream"]'), 'meta:twitter:player:stream');
            pushCandidate(read('meta[property="twitter:player"]'), 'meta:twitter:player');
            pushCandidate(read('meta[name="twitter:player"]'), 'meta:name:twitter:player');
            pushCandidate(read('meta[itemprop="contentUrl"]'), 'meta:itemprop:contentUrl');

            const jsonLdNodes = Array.from(document.querySelectorAll('script[type="application/ld+json"]')).slice(0, 10);
            for (const node of jsonLdNodes) {
              try {
                const parsed = JSON.parse(node.textContent || '{}');
                pickFromObject(parsed, 'jsonld');
              } catch (error) {}
            }

            const nextDataNode = document.querySelector('#__NEXT_DATA__');
            if (nextDataNode && nextDataNode.textContent) {
              try {
                pickFromObject(JSON.parse(nextDataNode.textContent), 'next-data');
              } catch (error) {}
            }

            if (window.__NEXT_DATA__) pickFromObject(window.__NEXT_DATA__, 'window.__NEXT_DATA__');
            if (window.__INITIAL_STATE__) pickFromObject(window.__INITIAL_STATE__, 'window.__INITIAL_STATE__');
            if (window.__NUXT__) pickFromObject(window.__NUXT__, 'window.__NUXT__');
            if (window.__INITIAL_PROPS__) pickFromObject(window.__INITIAL_PROPS__, 'window.__INITIAL_PROPS__');
            if (window.__APP_DATA__) pickFromObject(window.__APP_DATA__, 'window.__APP_DATA__');
            if (window.__DATA__) pickFromObject(window.__DATA__, 'window.__DATA__');
            if (window.__STATE__) pickFromObject(window.__STATE__, 'window.__STATE__');
            if (window._ROUTER_DATA) pickFromObject(window._ROUTER_DATA, 'window._ROUTER_DATA');

            const inlineScripts = Array.from(document.scripts).slice(0, 20);
            for (const script of inlineScripts) {
              const text = String(script.textContent || '');
              if (!text) continue;
              pickFromInlineScriptText(text);
            }

            const preferredMedia =
              mediaCandidates.find(item => /m3u8|mpd|mp4|playaddr|dash/i.test(item.url)) ||
              mediaCandidates[0] ||
              { url: '', source: '' };
            return {
              resolved_url: String(window.location.href || '').trim(),
              canonical_url: read('link[rel="canonical"]', 'href') || read('meta[property="og:url"]'),
              description: read('meta[name="description"]') || read('meta[property="og:description"]') || read('meta[name="twitter:description"]'),
              site_name: read('meta[property="og:site_name"]') || read('meta[name="application-name"]'),
              media_hint_url: preferredMedia.url || '',
              extraction_source: preferredMedia.source || ''
            };
            """
        )
    except Exception:
        return {}
    return {key: str(value or "").strip() for key, value in dict(payload or {}).items() if value}


def choose_best_media_hint(candidates: list[dict[str, str]]) -> tuple[str, str]:
    """Choose the most useful media hint from extracted candidates."""
    ranked = []
    for candidate in candidates:
        url = str(candidate.get("url") or "").strip()
        if not url:
            continue
        lowered = url.lower()
        score = 0
        if "m3u8" in lowered:
            score += 50
        if "mpd" in lowered or "dash" in lowered:
            score += 40
        if "mp4" in lowered:
            score += 30
        if "playaddr" in lowered:
            score += 20
        if lowered.startswith("https://") or lowered.startswith("http://"):
            score += 10
        ranked.append((score, url, str(candidate.get("source") or "")))
    if not ranked:
        return "", ""
    ranked.sort(key=lambda item: item[0], reverse=True)
    _, url, source = ranked[0]
    return url, source


def extract_page_signals_from_html(
    *,
    html: str,
    resolved_url: str,
    canonical_url: str = "",
    description: str = "",
    site_name: str = "",
) -> dict[str, str]:
    """Extract media hints from raw HTML for unit testing and fallback parsing."""
    candidates: list[dict[str, str]] = []

    def add_candidate(url: str, source: str) -> None:
        if url:
            candidates.append({"url": url, "source": source})

    script_blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in script_blocks[:10]:
        try:
            parsed = json.loads(block.strip())
        except json.JSONDecodeError:
            continue
        _collect_media_candidates(parsed, "jsonld", candidates)

    meta_patterns = (
        (r'<meta[^>]+property=["\']og:video:secure_url["\'][^>]+content=["\']([^"\']+)["\']', "meta:og:video:secure_url"),
        (r'<meta[^>]+property=["\']og:video:url["\'][^>]+content=["\']([^"\']+)["\']', "meta:og:video:url"),
        (r'<meta[^>]+property=["\']og:video["\'][^>]+content=["\']([^"\']+)["\']', "meta:og:video"),
        (r'<meta[^>]+property=["\']twitter:player:stream["\'][^>]+content=["\']([^"\']+)["\']', "meta:twitter:player:stream"),
        (r'<meta[^>]+property=["\']twitter:player["\'][^>]+content=["\']([^"\']+)["\']', "meta:twitter:player"),
        (r'<meta[^>]+name=["\']twitter:player["\'][^>]+content=["\']([^"\']+)["\']', "meta:name:twitter:player"),
        (r'<meta[^>]+itemprop=["\']contentUrl["\'][^>]+content=["\']([^"\']+)["\']', "meta:itemprop:contentUrl"),
    )
    for pattern, source in meta_patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            add_candidate(match.strip(), source)

    next_data_match = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if next_data_match:
        try:
            _collect_media_candidates(json.loads(next_data_match.group(1).strip()), "next-data", candidates)
        except json.JSONDecodeError:
            pass

    for state_name in INLINE_STATE_SOURCES:
        parsed_state = _extract_inline_state_payload(html, state_name)
        if parsed_state is None:
            continue
        _collect_media_candidates(parsed_state, f"window.{state_name}", candidates)

    for match in re.findall(r'https?://[^"\'\s]+(?:m3u8|mp4|mpd)[^"\'\s]*', html, flags=re.IGNORECASE):
        add_candidate(match, "inline-html")

    media_hint_url, extraction_source = choose_best_media_hint(candidates)
    return {
        "resolved_url": resolved_url,
        "canonical_url": canonical_url,
        "description": description,
        "site_name": site_name,
        "media_hint_url": media_hint_url,
        "extraction_source": extraction_source,
    }


def _collect_media_candidates(input_value: object, source: str, candidates: list[dict[str, str]], depth: int = 0) -> None:
    if input_value is None or depth > 5:
        return
    if isinstance(input_value, list):
        for item in input_value[:20]:
            _collect_media_candidates(item, source, candidates, depth + 1)
        return
    if not isinstance(input_value, dict):
        return

    keys = (
        "playAddr",
        "play_url",
        "playUrl",
        "contentUrl",
        "embedUrl",
        "src",
        "url",
        "uri",
        "downloadUrl",
        "download_url",
        "streamUrl",
        "stream_url",
        "m3u8",
        "m3u8_url",
        "hls",
        "hls_url",
        "dash",
        "dashUrl",
        "dash_url",
    )
    for key in keys:
        if key not in input_value:
            continue
        value = input_value[key]
        if isinstance(value, str):
            candidates.append({"url": value, "source": f"{source}:{key}"})
        elif isinstance(value, (dict, list)):
            _collect_media_candidates(value, f"{source}:{key}", candidates, depth + 1)

    for value in list(input_value.values())[:30]:
        if isinstance(value, (dict, list)):
            _collect_media_candidates(value, source, candidates, depth + 1)


def _extract_inline_state_payload(html: str, state_name: str) -> object | None:
    assignment_index = _find_inline_state_assignment(html, state_name)
    if assignment_index < 0:
        return None

    payload_text = html[assignment_index:].lstrip()
    if payload_text.startswith("JSON.parse"):
        return _parse_json_parse_expression(payload_text)
    if payload_text.startswith("{") or payload_text.startswith("["):
        return _parse_json_literal_prefix(payload_text)
    return None


def _find_inline_state_assignment(html: str, state_name: str) -> int:
    patterns = (
        rf"window\.{re.escape(state_name)}\s*=",
        rf"{re.escape(state_name)}\s*=",
    )
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match:
            return match.end()
    return -1


def _parse_json_parse_expression(payload_text: str) -> object | None:
    match = re.match(
        r'JSON\.parse\(\s*(?P<quote>["\'])(?P<body>(?:\\.|(?! (?P=quote)).)*) (?P=quote)\s*\)',
        payload_text,
        flags=re.DOTALL | re.VERBOSE,
    )
    if not match:
        return None

    quote = str(match.group("quote"))
    body = str(match.group("body"))
    wrapped = f"{quote}{body}{quote}"
    try:
        decoded = ast.literal_eval(wrapped)
        return json.loads(decoded)
    except (ValueError, SyntaxError, json.JSONDecodeError):
        return None


def _parse_json_literal_prefix(payload_text: str) -> object | None:
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(payload_text)
    except json.JSONDecodeError:
        return None
    return parsed


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
