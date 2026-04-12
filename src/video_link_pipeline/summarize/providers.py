"""Provider integrations for transcript summarization."""

from __future__ import annotations

import json
from typing import Any

import requests

from ..errors import VlpError

SUMMARY_PROMPT_TEMPLATE = """请根据以下视频转录文本生成一份结构化的视频摘要。
转录内容：{transcript}

请按以下格式输出，优先返回 Markdown 内容，同时包含一个 JSON 对象：

# 视频摘要

## 一句话概括
[一句话概括核心内容]

## 核心要点
- [要点1]
- [要点2]
- [要点3]

## 关键语段
[列出 3-5 个重要引用或短语]

## 主题标签
[列出 5-10 个相关标签，逗号分隔]

## 整体评价
[对信息密度、可操作性、内容质量给出简短评价]

JSON 对象格式：
{{
  "one_sentence_summary": "一句话概括",
  "key_points": ["要点1", "要点2"],
  "key_quotes": ["引用1", "引用2"],
  "tags": ["标签1", "标签2"],
  "evaluation": "整体评价",
  "confidence": 0.95
}}
"""


class SummaryProviderError(VlpError):
    """Raised when a summary provider call fails."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message=message, error_code="SUMMARY_FAILED", hint=hint)


def build_summary_prompt(transcript: str) -> str:
    return SUMMARY_PROMPT_TEMPLATE.format(transcript=transcript[:15000])


def parse_summary_response(content: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "raw_response": content,
        "one_sentence_summary": "",
        "key_points": [],
        "key_quotes": [],
        "tags": [],
        "evaluation": "",
        "confidence": 0.0,
        "success": True,
    }

    try:
        if "```json" in content:
            json_str = content.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in content:
            json_str = content.split("```", 1)[1].split("```", 1)[0].strip()
        else:
            start = content.find("{")
            end = content.rfind("}")
            json_str = content[start : end + 1] if start != -1 and end != -1 and end > start else "{}"
        parsed = json.loads(json_str)
        if isinstance(parsed, dict):
            result.update(parsed)
    except Exception:
        pass

    return result


def summarize_with_claude(*, transcript: str, api_key: str, model: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    try:
        import anthropic
    except Exception as exc:
        raise SummaryProviderError("anthropic SDK is not available", hint=str(exc)) from exc

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": build_summary_prompt(transcript)}],
        )
        content = response.content[0].text
        return parse_summary_response(content)
    except Exception as exc:
        raise SummaryProviderError("claude summary request failed", hint=str(exc)) from exc


def summarize_with_openai(*, transcript: str, api_key: str, model: str, max_tokens: int, temperature: float, base_url: str | None = None) -> dict[str, Any]:
    try:
        from openai import OpenAI
    except Exception as exc:
        raise SummaryProviderError("openai SDK is not available", hint=str(exc)) from exc

    try:
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": "你是专业的视频内容分析助手，擅长提炼重点并输出结构化摘要。"},
                {"role": "user", "content": build_summary_prompt(transcript)},
            ],
        )
        content = response.choices[0].message.content or ""
        return parse_summary_response(content)
    except Exception as exc:
        raise SummaryProviderError("openai-compatible summary request failed", hint=str(exc)) from exc


def summarize_with_gemini(*, transcript: str, api_key: str, model: str, max_tokens: int, temperature: float) -> dict[str, Any]:
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": build_summary_prompt(transcript)}]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
    }
    try:
        response = requests.post(endpoint, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise SummaryProviderError("gemini summary request failed", hint=str(exc)) from exc

    content = ""
    candidates = data.get("candidates", [])
    if candidates:
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "\n".join(part.get("text", "") for part in parts if isinstance(part, dict))
    if not content:
        content = json.dumps(data, ensure_ascii=False)
    return parse_summary_response(content)
