"""从模型文本中提取 JSON。

模型可能返回 Markdown 代码块、前后说明文字或截断输出；这里只做“提取首对象”，
提取失败由 Provider 触发一次 JSON 修复请求，而不是猜测字段。
"""

from __future__ import annotations

import json
import re

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def extract_json_object(text: str) -> dict:
    if not text or not text.strip():
        raise ValueError("模型返回为空")
    candidate = text.strip()
    fence = _FENCE.search(candidate)
    if fence:
        candidate = fence.group(1).strip()

    start = candidate.find("{")
    if start < 0:
        raise ValueError("模型返回中未找到 JSON 对象")
    decoder = json.JSONDecoder()
    try:
        value, _end = decoder.raw_decode(candidate[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 解析失败：{exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError("模型返回的 JSON 顶层必须是对象")
    return value


def truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...(已截断)"
