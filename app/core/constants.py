"""全局常量：版本号与固定枚举。

枚举值与需求文档 9.2 及技术方案 6.5 保持一致，业务代码不得另起同义字符串。
"""

from __future__ import annotations

APP_NAME = "char_cons"
APP_TITLE = "AI 角色形象一致性检查助手"
APP_VERSION = "0.1.0"
# 报告数据结构版本（需求 9.1 / 技术方案 6.3.1）
SCHEMA_VERSION = "1.3"
# 提示词版本（技术方案 14.3）
PROMPT_VERSION = "p0-2026-11-25.1"

# 11 个固定要素（需求 7.2），顺序即页面矩阵行顺序
ATTRIBUTE_DEFS: tuple[tuple[str, str], ...] = (
    ("hair_style", "发型"),
    ("hair_color", "发色"),
    ("top_style", "上装款式"),
    ("top_color", "上装颜色"),
    ("top_pattern", "上装图案"),
    ("bottom_style", "下装款式"),
    ("bottom_color", "下装颜色"),
    ("bottom_pattern", "下装图案"),
    ("accessories", "配饰"),
    ("shoes", "鞋履"),
    ("props", "道具"),
)
ATTRIBUTE_IDS: tuple[str, ...] = tuple(aid for aid, _ in ATTRIBUTE_DEFS)
ATTRIBUTE_NAMES: dict[str, str] = dict(ATTRIBUTE_DEFS)

TASK_STATUSES = ("idle", "running", "retrying", "paused", "completed", "partial", "failed")
SHOT_ANALYSIS_STATUSES = ("pending", "analyzing", "ok", "failed")
SHOT_CONCLUSION_STATUSES = ("ok", "issue", "unknown")
VISIBILITIES = ("visible", "partial", "not_visible")
VERDICTS = ("consistent", "inconsistent", "unknown", "waived", "observed_only")
CONFIDENCES = ("high", "medium", "low")
GENERATION_STATUSES = ("pending", "generating", "prechecking", "succeeded", "partial", "failed")
PRECHECK_STATUSES = ("pending", "running", "completed", "failed")
CANDIDATE_STATES = ("pass", "partial", "fail", "unknown")
RECHECK_STATUSES = ("pending", "running", "consistent", "inconsistent", "unknown", "failed")
TASK_MODES = ("demo", "live")
