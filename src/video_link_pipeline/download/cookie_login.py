"""Interactive browser login flow for exporting reusable cookies."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .diagnostics import selenium_extra_install_hint
from .selenium_fallback import _write_netscape_cookies, selenium_extra_available
from ..errors import DependencyMissingError, VlpError


class CookieLoginError(VlpError):
    """Raised when interactive cookie export cannot complete."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="COOKIE_ACCESS_FAILED", hint=hint)


def _chrome_cookie_to_netscape(cookie: dict[str, Any]) -> dict[str, object]:
    return {
        "domain": cookie.get("domain") or "",
        "path": cookie.get("path") or "/",
        "secure": bool(cookie.get("secure")),
        "expiry": int(cookie.get("expiry") or cookie.get("expires") or cookie.get("expiration") or 0),
        "name": cookie.get("name") or "",
        "value": cookie.get("value") or "",
    }


def _collect_browser_cookies(driver: object) -> list[dict[str, object]]:
    """Collect cookies from Chrome DevTools when available, falling back to current domain."""
    try:
        payload = driver.execute_cdp_cmd("Network.getAllCookies", {})  # type: ignore[attr-defined]
        cookies = payload.get("cookies", []) if isinstance(payload, dict) else []
        if cookies:
            return [_chrome_cookie_to_netscape(cookie) for cookie in cookies if isinstance(cookie, dict)]
    except Exception:
        pass

    return [
        _chrome_cookie_to_netscape(cookie)
        for cookie in driver.get_cookies()  # type: ignore[attr-defined]
        if isinstance(cookie, dict)
    ]


def export_cookies_after_login(
    *,
    url: str,
    cookie_file: str | Path,
    profile_dir: str | Path,
    prompt: Callable[[str], None] | None = None,
) -> Path:
    """Open an isolated visible browser, wait for user login, then export cookies."""
    if not selenium_extra_available():
        raise DependencyMissingError(
            "interactive cookie login requires optional Selenium dependencies",
            hint=selenium_extra_install_hint(),
        )

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager

    output_path = Path(cookie_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    profile_path = Path(profile_dir)
    profile_path.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={profile_path.resolve()}")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--lang=zh-CN")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options,
    )
    try:
        driver.get(url)
        if prompt is not None:
            prompt(
                "请在打开的浏览器窗口中完成登录/验证。完成后回到终端按回车导出 cookies..."
            )

        cookies = _collect_browser_cookies(driver)
        if not cookies:
            raise CookieLoginError(
                "no cookies were available after browser login",
                hint="make sure you logged in on the opened page before pressing Enter",
            )

        _write_netscape_cookies(output_path, cookies)
        return output_path
    finally:
        driver.quit()
