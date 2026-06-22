"""Interactive cookie login routes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from video_link_pipeline.errors import VlpError
from web.api.services.cookie_login import default_cookie_file_for_url, get_cookie_login_registry

router = APIRouter(prefix="/api/cookies", tags=["cookies"])


class CookieLoginStartRequest(BaseModel):
    url: str
    cookie_file: str | None = None


class CookieLoginStartResponse(BaseModel):
    session_id: str
    cookie_file: str
    message: str


class CookieLoginExportResponse(BaseModel):
    cookie_file: str
    message: str


@router.post("/login/start", response_model=CookieLoginStartResponse)
def start_cookie_login(request: CookieLoginStartRequest) -> CookieLoginStartResponse:
    if not request.url.strip():
        raise HTTPException(status_code=400, detail="url 不能为空")
    cookie_file = request.cookie_file or str(default_cookie_file_for_url(request.url))
    try:
        session_id, resolved_cookie_file = get_cookie_login_registry().start(
            url=request.url.strip(),
            cookie_file=cookie_file,
        )
    except VlpError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CookieLoginStartResponse(
        session_id=session_id,
        cookie_file=str(resolved_cookie_file),
        message="登录窗口已打开，请在浏览器中完成登录后点击导出 Cookies",
    )


@router.post("/login/{session_id}/export", response_model=CookieLoginExportResponse)
def export_cookie_login(session_id: str) -> CookieLoginExportResponse:
    try:
        cookie_file = get_cookie_login_registry().export(session_id)
    except VlpError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if cookie_file is None:
        raise HTTPException(status_code=404, detail="登录会话不存在或已结束")
    return CookieLoginExportResponse(
        cookie_file=str(Path(cookie_file)),
        message="Cookies 已导出",
    )


@router.delete("/login/{session_id}", status_code=204)
def cancel_cookie_login(session_id: str) -> None:
    get_cookie_login_registry().cancel(session_id)
