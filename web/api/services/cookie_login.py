"""Manage interactive cookie-login browser sessions for the web UI."""

from __future__ import annotations

import re
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from video_link_pipeline.download.cookie_login import (
    CookieLoginSession,
    close_cookie_login_session,
    export_cookie_login_session,
    open_cookie_login_session,
)


def _safe_site_name(url: str) -> str:
    host = urlparse(url).netloc.lower().strip() or "site"
    if host.startswith("www."):
        host = host[4:]
    return re.sub(r"[^a-z0-9._-]+", "-", host).strip("-") or "site"


def default_cookie_file_for_url(url: str) -> Path:
    """Return the default cookies.txt path used by web-triggered login."""
    return Path("temp") / "web-cookies" / f"{_safe_site_name(url)}.txt"


def default_profile_dir_for_url(url: str) -> Path:
    """Return a dedicated Chrome profile path for the target site."""
    return Path("temp") / "web-cookie-profiles" / _safe_site_name(url)


class CookieLoginRegistry:
    """Thread-safe registry for visible browser sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, CookieLoginSession] = {}
        self._lock = threading.Lock()

    def start(self, *, url: str, cookie_file: str | Path | None = None) -> tuple[str, Path]:
        session_id = str(uuid.uuid4())
        target_cookie_file = Path(cookie_file) if cookie_file else default_cookie_file_for_url(url)
        session = open_cookie_login_session(
            url=url,
            cookie_file=target_cookie_file,
            profile_dir=default_profile_dir_for_url(url),
        )
        with self._lock:
            self._sessions[session_id] = session
        return session_id, target_cookie_file

    def export(self, session_id: str) -> Path | None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        return export_cookie_login_session(session, close=True)

    def cancel(self, session_id: str) -> bool:
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        close_cookie_login_session(session)
        return True


_registry = CookieLoginRegistry()


def get_cookie_login_registry() -> CookieLoginRegistry:
    return _registry
