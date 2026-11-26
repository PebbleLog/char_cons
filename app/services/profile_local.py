"""角色设定本地规则解析（AI 解析失败时的回退）。

原则（需求 F-03）：只提取原文明确写出的要素，未提及一律 undefined，不推断。
这是规则近似实现，权威解析仍以视觉/语言模型为准；本地结果 confidence 较低。
"""

from __future__ import annotations

import re

from ..core.constants import ATTRIBUTE_DEFS, ATTRIBUTE_NAMES
from ..providers.schemas import CharacterProfile, ProfileAttribute

_CLAUSE_SPLIT = re.compile(r"[，,。；;\n]+")

_HAIR_COLORS = [
    "深棕", "浅棕", "栗棕", "黑棕", "银灰", "亚麻金", "浅金", "深金",
    "金色", "银色", "黑色", "白色", "灰色", "棕色", "红色", "蓝色",
    "紫色", "绿色", "粉色", "橙色",
]
_TOP_COLORS = [
    "浅暖米色", "浅米色", "米白色", "暖白色", "米色", "杏色", "卡其色",
    "藏青", "深蓝", "宝蓝", "天蓝", "浅蓝", "深灰", "浅灰", "黑色",
    "白色", "灰色", "红色", "黄色", "绿色", "紫色", "粉色", "棕色",
    "橙色", "蓝色", "银色", "金色",
]
_BOTTOM_COLORS = _TOP_COLORS
_SHOE_COLORS = _TOP_COLORS

_HAIR_WORDS = ("发型", "发髻", "长发", "短发", "齐肩", "马尾", "丸子头", "编发",
               "卷发", "直发", "盘发", "刘海", "光头")
_LENGTH_WORDS = ("超长发", "超短发", "齐肩发", "长发", "短发", "齐肩")
_STYLE_WORDS = ("低侧发髻", "高马尾", "低马尾", "双马尾", "丸子头", "披肩发",
                "齐刘海", "侧分刘海", "马尾", "编发", "卷发", "直发", "盘发", "发髻")

_TOP_KEYWORDS = {
    "风衣": 90, "夹克": 85, "西装外套": 100, "外套": 95, "西装": 92,
    "连衣裙": 80, "卫衣": 70, "毛衣": 68, "制服": 66, "衬衫": 50,
    "T恤": 45, "polo衫": 45, "上衣": 40, "背心": 35,
}
_BOTTOM_KEYWORDS = ("背带裤", "短裤", "长裤", "裙子", "半身裙", "连衣裙", "裤")
_ACCESSORY_KEYWORDS = ("项链", "吊坠", "耳环", "耳饰", "耳钉", "眼镜", "墨镜",
                       "帽子", "围巾", "手套", "背包", "腰带", "发饰", "胸针")
_SHOE_KEYWORDS = ("皮鞋", "靴子", "短靴", "长靴", "运动鞋", "高跟鞋", "凉鞋", "鞋")
_PROP_KEYWORDS = ("道具", "手持", "拿着", "握着", "拎着", "撑着")
_PATTERN_WORDS = ("条纹", "格纹", "印花", "logo", "Logo", "LOGO", "纯色", "波点", "碎花")


def split_clauses(text: str) -> list[str]:
    return [part.strip() for part in _CLAUSE_SPLIT.split(text or "") if part.strip()]


def _find_color(clause: str, colors: list[str]) -> str | None:
    for color in sorted(colors, key=len, reverse=True):
        if color in clause:
            return color
    return None


def _remove_color(clause: str, color: str | None) -> str:
    value = clause if not color else clause.replace(color, "")
    value = value.replace("的", " ").strip(" 、，。")
    return re.sub(r"\s+", "", value)


def _find_pattern(clause: str) -> str | None:
    for word in _PATTERN_WORDS:
        if word.lower() in clause.lower():
            return "logo" if word.lower() == "logo" else word
    return None


def _hair_style(clauses: list[str]) -> tuple[str | None, str | None]:
    for clause in clauses:
        if not any(word in clause for word in _HAIR_WORDS):
            continue
        style = next((word for word in _STYLE_WORDS if word in clause), None)
        length = next((word for word in _LENGTH_WORDS if word in clause), None)
        if style and length:
            value = f"{style}（{length}）"
        elif style:
            value = style
        elif length:
            value = length
        else:
            continue
        return value, clause
    return None, None


def _top_clause(clauses: list[str]) -> tuple[str, int] | None:
    best: tuple[str, int] | None = None
    for clause in clauses:
        score = max(
            (weight for word, weight in _TOP_KEYWORDS.items() if word in clause),
            default=0,
        )
        if score and (best is None or score > best[1]):
            best = (clause, score)
    return best


def _first_clause(clauses: list[str], words: tuple[str, ...]) -> str | None:
    for clause in clauses:
        if any(word in clause for word in words):
            return clause
    return None


def _explicit(
    attribute_id: str,
    value: str | None,
    evidence: str | None,
    confidence: float = 0.55,
) -> ProfileAttribute:
    return ProfileAttribute(
        id=attribute_id,
        value=value,
        source="explicit" if value else "undefined",
        evidenceText=evidence if value else None,
        confidence=confidence if value else None,
    )


def parse_profile_local(text: str) -> CharacterProfile:
    raw = (text or "").strip()
    clauses = split_clauses(raw)
    attributes: dict[str, ProfileAttribute] = {}

    hair_value, hair_evidence = _hair_style(clauses)
    hair_color = None
    if hair_evidence:
        hair_color = _find_color(hair_evidence, _HAIR_COLORS)

    top = _top_clause(clauses)
    top_style = top_color = top_pattern = None
    if top:
        top_clause = top[0]
        top_color = _find_color(top_clause, _TOP_COLORS)
        top_style = _remove_color(top_clause, top_color) or None
        top_pattern = _find_pattern(top_clause)

    bottom_clause = _first_clause(clauses, _BOTTOM_KEYWORDS)
    bottom_style = bottom_color = bottom_pattern = None
    if bottom_clause:
        bottom_color = _find_color(bottom_clause, _BOTTOM_COLORS)
        bottom_style = _remove_color(bottom_clause, bottom_color) or None
        bottom_pattern = _find_pattern(bottom_clause)

    accessory_clauses = [
        clause for clause in clauses
        if any(word in clause for word in _ACCESSORY_KEYWORDS)
    ]
    accessories = "、".join(dict.fromkeys(accessory_clauses)) or None

    shoe_clause = _first_clause(clauses, _SHOE_KEYWORDS)
    prop_clause = _first_clause(clauses, _PROP_KEYWORDS)

    values: dict[str, tuple[str | None, str | None]] = {
        "hair_style": (hair_value, hair_evidence),
        "hair_color": (hair_color, hair_evidence if hair_color else None),
        "top_style": (top_style, top[0] if top else None),
        "top_color": (top_color, top[0] if top and top_color else None),
        "top_pattern": (top_pattern, top[0] if top and top_pattern else None),
        "bottom_style": (bottom_style, bottom_clause if bottom_style else None),
        "bottom_color": (bottom_color, bottom_clause if bottom_color else None),
        "bottom_pattern": (bottom_pattern, bottom_clause if bottom_pattern else None),
        "accessories": (accessories, accessory_clauses[0] if accessory_clauses else None),
        "shoes": (shoe_clause, shoe_clause),
        "props": (prop_clause, prop_clause),
    }

    for attribute_id, _name in ATTRIBUTE_DEFS:
        value, evidence = values.get(attribute_id, (None, None))
        attributes[attribute_id] = _explicit(attribute_id, value, evidence)

    return CharacterProfile(rawText=raw, attributes=list(attributes.values()))


def summarise_profile(profile: CharacterProfile) -> str:
    lines = []
    for attribute in profile.attributes:
        if attribute.source == "explicit":
            lines.append(f"{attribute.name}：{attribute.value}")
    return "；".join(lines)
