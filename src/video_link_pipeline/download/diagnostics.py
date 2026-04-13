from __future__ import annotations

WARNING_CODES = {
    "primary_download_failed": "主下载失败，但未识别出更具体原因。",
    "primary_http_403": "主下载遇到 403/Forbidden，通常是反爬、鉴权或区域限制。",
    "primary_captcha_required": "主下载命中验证码、人机校验或验证页面。",
    "primary_auth_required": "主下载需要登录或账号权限。",
    "browser_cookie_locked": "浏览器 cookies 数据库被占用或无法复制。",
    "browser_driver_unavailable": "Selenium 浏览器驱动不可用或未正确安装。",
    "ffmpeg_unavailable": "FFmpeg 不可用，可能影响媒体合并或转码。",
    "fallback_context_prepared": "Selenium fallback 已成功提取浏览器上下文，可进入重试。",
    "fallback_media_hint_missing": "未提取到明确媒体地址，将退化为用页面地址重试。",
    "fallback_dependency_hint": "fallback 依赖缺失时给出的补充提示。",
    "fallback_prepare_hint": "fallback 准备浏览器上下文失败时的补充提示。",
    "fallback_retry_hint": "fallback 重试失败时的补充提示。",
    "fallback_retry_unhandled_exception": "fallback 重试过程中出现未分类异常。",
}


def warning_code_description(code: str) -> str | None:
    return WARNING_CODES.get(code)
