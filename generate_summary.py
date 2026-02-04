#!/usr/bin/env python3
"""
AI 智能摘要模块 - 使用 Claude 或 OpenAI API 生成视频内容摘要
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

import yaml
import requests
from dotenv import load_dotenv

load_dotenv()


def load_config(config_path: str = "config.yaml") -> dict:
    """加载配置文件"""
    config = {}
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
    return config


def load_transcript(transcript_path: str) -> str:
    """加载转录文本"""
    with open(transcript_path, "r", encoding="utf-8") as f:
        return f.read()


def generate_summary_claude(
    transcript: str,
    api_key: str,
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Dict:
    """使用 Claude API 生成摘要"""
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""请根据以下视频转录文本生成一份结构化的视频摘要。

转录内容：
{transcript[:15000]}  # 限制长度以避免超出token限制

请按以下格式输出（使用Markdown）：

# 📹 视频摘要

## 📌 一句话概括
[用一句话概括视频核心内容]

## 🔑 核心要点
- [要点1]
- [要点2]
- [要点3]
- [更多要点...]

## 💬 关键语段
[列出3-5个重要的引用或关键语段]

## 📊 主题标签
[列出5-10个相关标签，用逗号分隔]

## ⭐ 整体评价
[对视频内容质量、信息密度、实用性的简短评价]

同时请输出一个JSON对象包含结构化数据：
{{
  "one_sentence_summary": "一句话概括",
  "key_points": ["要点1", "要点2", "要点3"],
  "key_quotes": ["引用1", "引用2"],
  "tags": ["标签1", "标签2", "标签3"],
  "evaluation": "整体评价",
  "confidence": 0.95  // 置信度0-1
}}"""

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        content = response.content[0].text

        # 尝试提取 JSON
        result = {
            "raw_response": content,
            "one_sentence_summary": "",
            "key_points": [],
            "key_quotes": [],
            "tags": [],
            "evaluation": "",
            "confidence": 0.0,
            "success": True,
        }

        # 尝试解析 JSON 部分
        try:
            # 寻找 JSON 代码块
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                # 尝试找到 JSON 对象
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    json_str = content[start : end + 1]
                else:
                    json_str = "{}"

            json_data = json.loads(json_str)
            result.update(json_data)
        except Exception as e:
            print(f"⚠️  JSON 解析警告: {e}")

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def generate_summary_openai_compatible(
    transcript: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Dict:
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)

        prompt = f"""请根据以下视频转录文本生成一份结构化的视频摘要。

转录内容：
{transcript[:15000]}

请按以下格式输出（使用Markdown）：

# 📹 视频摘要

## 📌 一句话概括
[用一句话概括视频核心内容]

## 🔑 核心要点
- [要点1]
- [要点2]
- [要点3]
- [更多要点...]

## 💬 关键语段
[列出3-5个重要的引用或关键语段]

## 📊 主题标签
[列出5-10个相关标签，用逗号分隔]

## ⭐ 整体评价
[对视频内容质量、信息密度、实用性的简短评价]

同时请输出一个JSON对象包含结构化数据。
"""

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": "你是一个专业的视频内容分析助手，擅长提取视频的核心内容和关键信息。"},
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content

        result = {
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
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    json_str = content[start : end + 1]
                else:
                    json_str = "{}"
            json_data = json.loads(json_str)
            result.update(json_data)
        except Exception:
            pass

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def generate_summary_gemini(
    transcript: str,
    api_key: str,
    model: str = "gemini-1.5-flash",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Dict:
    try:
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        prompt = f"""请根据以下视频转录文本生成一份结构化的视频摘要。

转录内容：
{transcript[:15000]}

请按以下格式输出（使用Markdown）：

# 📹 视频摘要

## 📌 一句话概括
[用一句话概括视频核心内容]

## 🔑 核心要点
- [要点1]
- [要点2]
- [要点3]
- [更多要点...]

## 💬 关键语段
[列出3-5个重要的引用或关键语段]

## 📊 主题标签
[列出5-10个相关标签，用逗号分隔]

## ⭐ 整体评价
[对视频内容质量、信息密度、实用性的简短评价]

同时请输出一个JSON对象包含结构化数据。
"""

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }

        r = requests.post(endpoint, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()

        content_text = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                content_text = "\n".join([p.get("text", "") for p in parts if isinstance(p, dict)])
        except Exception:
            content_text = json.dumps(data, ensure_ascii=False)

        if not content_text:
            content_text = json.dumps(data, ensure_ascii=False)

        result = {
            "raw_response": content_text,
            "one_sentence_summary": "",
            "key_points": [],
            "key_quotes": [],
            "tags": [],
            "evaluation": "",
            "confidence": 0.0,
            "success": True,
        }

        try:
            if "```json" in content_text:
                json_str = content_text.split("```json")[1].split("```")[0].strip()
            elif "```" in content_text:
                json_str = content_text.split("```")[1].split("```")[0].strip()
            else:
                start = content_text.find("{")
                end = content_text.rfind("}")
                if start != -1 and end != -1:
                    json_str = content_text[start : end + 1]
                else:
                    json_str = "{}"
            json_data = json.loads(json_str)
            result.update(json_data)
        except Exception:
            pass

        return result
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

def generate_summary_openai(
    transcript: str,
    api_key: str,
    model: str = "gpt-4o-mini",
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> Dict:
    """使用 OpenAI API 生成摘要"""
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        prompt = f"""请根据以下视频转录文本生成一份结构化的视频摘要。

转录内容：
{transcript[:15000]}

请按以下格式输出（使用Markdown）：

# 📹 视频摘要

## 📌 一句话概括
[用一句话概括视频核心内容]

## 🔑 核心要点
- [要点1]
- [要点2]
- [要点3]
- [更多要点...]

## 💬 关键语段
[列出3-5个重要的引用或关键语段]

## 📊 主题标签
[列出5-10个相关标签，用逗号分隔]

## ⭐ 整体评价
[对视频内容质量、信息密度、实用性的简短评价]

同时请输出一个JSON对象包含结构化数据。
"""

        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的视频内容分析助手，擅长提取视频的核心内容和关键信息。",
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content

        result = {
            "raw_response": content,
            "one_sentence_summary": "",
            "key_points": [],
            "key_quotes": [],
            "tags": [],
            "evaluation": "",
            "confidence": 0.0,
            "success": True,
        }

        # 尝试解析 JSON
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            else:
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    json_str = content[start : end + 1]
                else:
                    json_str = "{}"

            json_data = json.loads(json_str)
            result.update(json_data)
        except Exception:
            pass

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }


def generate_summary(
    transcript_path: str,
    output_dir: str,
    config: dict,
) -> Dict:
    """
    生成视频内容摘要

    Args:
        transcript_path: 转录文本文件路径
        output_dir: 输出目录
        config: 配置字典

    Returns:
        dict: 摘要结果
    """
    transcript_path = Path(transcript_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 加载转录文本
    try:
        transcript = load_transcript(str(transcript_path))
    except Exception as e:
        return {
            "success": False,
            "error": f"无法加载转录文件: {e}",
        }

    if not transcript.strip():
        return {
            "success": False,
            "error": "转录文件为空",
        }

    summary_config = config.get("summary", {})
    provider = summary_config.get("provider", "claude")

    # 获取 API Key
    api_keys = config.get("api_keys", {})
    api_key = None

    if provider == "claude":
        api_key = api_keys.get("claude") or os.getenv("ANTHROPIC_API_KEY")
    elif provider == "openai":
        api_key = api_keys.get("openai") or os.getenv("OPENAI_API_KEY")
    elif provider == "gemini":
        api_key = api_keys.get("gemini") or os.getenv("GEMINI_API_KEY")
    elif provider == "deepseek":
        api_key = api_keys.get("deepseek") or os.getenv("DEEPSEEK_API_KEY")
    elif provider in {"kimi", "moonshot"}:
        api_key = api_keys.get("kimi") or api_keys.get("moonshot") or os.getenv("KIMI_API_KEY") or os.getenv("MOONSHOT_API_KEY")
    elif provider == "minimax":
        api_key = api_keys.get("minimax") or os.getenv("MINIMAX_API_KEY")
    elif provider in {"glm", "zhipu"}:
        api_key = api_keys.get("glm") or api_keys.get("zhipu") or os.getenv("GLM_API_KEY") or os.getenv("ZHIPU_API_KEY")
    else:
        api_key = None

    if not api_key:
        return {
            "success": False,
            "error": f"未设置 {provider} API Key。请在 config.yaml 中配置或设置环境变量。",
        }

    # 生成摘要
    print(f"使用 {provider} 生成摘要...")

    if provider == "claude":
        result = generate_summary_claude(
            transcript=transcript,
            api_key=api_key,
            model=summary_config.get("model", "claude-3-5-sonnet-20241022"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider == "openai":
        result = generate_summary_openai(
            transcript=transcript,
            api_key=api_key,
            model=summary_config.get("model", "gpt-4o-mini"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider == "gemini":
        result = generate_summary_gemini(
            transcript=transcript,
            api_key=api_key,
            model=summary_config.get("model", "gemini-1.5-flash"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider == "deepseek":
        result = generate_summary_openai_compatible(
            transcript=transcript,
            api_key=api_key,
            base_url=summary_config.get("base_url", "https://api.deepseek.com"),
            model=summary_config.get("model", "deepseek-chat"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider in {"kimi", "moonshot"}:
        result = generate_summary_openai_compatible(
            transcript=transcript,
            api_key=api_key,
            base_url=summary_config.get("base_url", "https://api.moonshot.cn/v1"),
            model=summary_config.get("model", "moonshot-v1-8k"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider == "minimax":
        result = generate_summary_openai_compatible(
            transcript=transcript,
            api_key=api_key,
            base_url=summary_config.get("base_url", "https://api.minimax.chat/v1"),
            model=summary_config.get("model", "abab5.5-chat"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    elif provider in {"glm", "zhipu"}:
        result = generate_summary_openai_compatible(
            transcript=transcript,
            api_key=api_key,
            base_url=summary_config.get("base_url", "https://open.bigmodel.cn/api/paas/v4"),
            model=summary_config.get("model", "glm-4"),
            max_tokens=summary_config.get("max_tokens", 4096),
            temperature=summary_config.get("temperature", 0.3),
        )
    else:
        result = {
            "success": False,
            "error": f"不支持的 provider: {provider}",
        }

    if result["success"]:
        # 保存 Markdown 格式摘要
        summary_md = output_dir / "summary.md"
        with open(summary_md, "w", encoding="utf-8") as f:
            f.write(result.get("raw_response", ""))
        print(f"✅ Markdown 摘要已保存: {summary_md}")

        # 保存 JSON 格式数据
        keywords_json = output_dir / "keywords.json"
        json_data = {
            "one_sentence_summary": result.get("one_sentence_summary", ""),
            "key_points": result.get("key_points", []),
            "key_quotes": result.get("key_quotes", []),
            "tags": result.get("tags", []),
            "evaluation": result.get("evaluation", ""),
            "confidence": result.get("confidence", 0.0),
        }
        with open(keywords_json, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        print(f"✅ 关键词数据已保存: {keywords_json}")

        result["summary_file"] = str(summary_md)
        result["keywords_file"] = str(keywords_json)

    return result


def main():
    parser = argparse.ArgumentParser(description="AI 视频摘要生成工具")
    parser.add_argument(
        "--transcript", "-t", required=True, help="转录文本文件路径"
    )
    parser.add_argument(
        "--output-dir", "-o", default=None, help="输出目录"
    )
    parser.add_argument(
        "--provider", "-p",
        choices=["claude", "openai", "gemini", "deepseek", "kimi", "moonshot", "minimax", "glm", "zhipu"],
        help="AI 提供商 (覆盖配置)"
    )
    parser.add_argument(
        "--api-key", "-k", help="API Key (覆盖配置)"
    )
    parser.add_argument(
        "--json", "-j", action="store_true", help="输出JSON格式"
    )
    parser.add_argument(
        "--model", help="模型名 (覆盖配置)"
    )
    parser.add_argument(
        "--base-url", help="兼容接口 Base URL (覆盖配置)"
    )

    args = parser.parse_args()

    # 加载配置
    config = load_config()

    # 命令行参数覆盖配置
    if args.provider:
        if "summary" not in config:
            config["summary"] = {}
        
        # 如果切换了 provider 且没有指定 model，则清除 config 中的 model，
        # 避免沿用旧 provider 的模型配置
        old_provider = config.get("summary", {}).get("provider")
        if old_provider != args.provider and not args.model:
            if "model" in config.get("summary", {}):
                del config["summary"]["model"]

        config["summary"]["provider"] = args.provider

    if args.api_key:
        if "api_keys" not in config:
            config["api_keys"] = {}
        if config.get("summary", {}).get("provider") == "claude":
            config["api_keys"]["claude"] = args.api_key
        else:
            config["api_keys"]["openai"] = args.api_key
    if args.model:
        if "summary" not in config:
            config["summary"] = {}
        config["summary"]["model"] = args.model
    if args.base_url:
        if "summary" not in config:
            config["summary"] = {}
        config["summary"]["base_url"] = args.base_url

    # 确定输出目录
    transcript_path = Path(args.transcript)
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = transcript_path.parent

    print(f"转录文件: {transcript_path}")
    print(f"输出目录: {output_dir}")
    print()

    result = generate_summary(
        transcript_path=str(transcript_path),
        output_dir=output_dir,
        config=config,
    )

    if result["success"]:
        print(f"\n✅ 摘要生成成功!")
        if result.get("one_sentence_summary"):
            print(f"\n一句话概括:")
            print(f"  {result['one_sentence_summary']}")
        if result.get("tags"):
            print(f"\n主题标签: {', '.join(result['tags'])}")
    else:
        print(f"\n❌ 摘要生成失败: {result.get('error')}")
        sys.exit(1)

    if args.json:
        print("\n" + json.dumps(result, indent=2, ensure_ascii=False))

    return result


if __name__ == "__main__":
    main()
