"""剧本说明解析与豁免规则（确定性，P0）。

规则（需求 F-04 / 技术方案 3.4）：
1. 「无换装/没有换装/不换装」→ 严格比对，无豁免；
2. 写明镜头号与具体要素的变化才建立豁免（如「S2 发色变为红褐色」→ 仅豁免 S2 发色）；
   只写「换装」而不写具体要素，不豁免任何要素；
3. 有变化描述但没有镜头号 → 不建立豁免，徽标「待定位 · 暂不豁免」；
4. 场景切换本身不豁免；无法解析按严格处理；
5. 未写明的要素始终严格比对；剧本与设定冲突时以设定为基准。
"""

from __future__ import annotations

import re

from ..core.constants import ATTRIBUTE_IDS
from ..providers.schemas import (
    GlobalChange,
    ScriptContext,
    ShotChange,
)

_CHANGE_WORDS = re.compile(
    r"换装|换成|换为|改为|改成|变为|变成|改穿|更换|换上|换下|染成|摘下|戴上|取下|摘掉"
    r"|剪成|剪短|脱下|穿上|换穿|允许变化|可变化|可变|可调整|允许调整|允许变动"
    r"|不做限制|不限制|豁免|换(?=发型|发色|配饰|道具|上装|下装|鞋)"
)
_NO_CHANGE = re.compile(r"(?:无|没有|不|未)(?:换装|更换)")
# 「所有要素允许变化」：明确写入时开放全部 11 个要素（未定义要素仍不比对）
_ALL_ATTRIBUTES_WORDS = re.compile(r"所有要素|全部要素|所有外观要素|全部外观要素|所有外观|全部外观")
_NEGATION = re.compile(r"(?:不|未|别|勿|不要|没有|无需)[^，。；]{0,3}$")
_SCENE_WORDS = re.compile(r"场景|时间切换|转场")

_SHOT_PATTERNS = (
    re.compile(r"[Ss]\s*(\d+)"),
    re.compile(r"第\s*([0-9一二三四五六七八九十]+)\s*(?:个)?镜头"),
    re.compile(r"镜头\s*(\d+)"),
)

# 要素关键词：长词优先，避免「上装」抢在「上装颜色」前面。
_ATTRIBUTE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = tuple(
    sorted(
        (
            ("上装款式", ("top_style",)),
            ("上装颜色", ("top_color",)),
            ("上装图案", ("top_pattern",)),
            ("上装花纹", ("top_pattern",)),
            ("外套款式", ("top_style",)),
            ("外套颜色", ("top_color",)),
            ("外套图案", ("top_pattern",)),
            ("上衣款式", ("top_style",)),
            ("上衣颜色", ("top_color",)),
            ("上衣图案", ("top_pattern",)),
            ("下装款式", ("bottom_style",)),
            ("下装颜色", ("bottom_color",)),
            ("下装图案", ("bottom_pattern",)),
            ("下装花纹", ("bottom_pattern",)),
            ("裤子款式", ("bottom_style",)),
            ("裤子颜色", ("bottom_color",)),
            ("裤子图案", ("bottom_pattern",)),
            ("裙子款式", ("bottom_style",)),
            ("裙子颜色", ("bottom_color",)),
            ("裙子图案", ("bottom_pattern",)),
            ("上装", ("top_style", "top_color", "top_pattern")),
            ("下装", ("bottom_style", "bottom_color", "bottom_pattern")),
            ("鞋履", ("shoes",)),
            ("鞋子", ("shoes",)),
            ("发色", ("hair_color",)),
            ("头发颜色", ("hair_color",)),
            ("头发", ("hair_style", "hair_color")),
            ("发型", ("hair_style",)),
            ("配饰", ("accessories",)),
            ("项链", ("accessories",)),
            ("吊坠", ("accessories",)),
            ("颈链", ("accessories",)),
            ("耳环", ("accessories",)),
            ("耳饰", ("accessories",)),
            ("耳钉", ("accessories",)),
            ("手链", ("accessories",)),
            ("手镯", ("accessories",)),
            ("戒指", ("accessories",)),
            ("帽子", ("accessories",)),
            ("围巾", ("accessories",)),
            ("围脖", ("accessories",)),
            ("手套", ("accessories",)),
            ("眼镜", ("accessories",)),
            ("墨镜", ("accessories",)),
            ("太阳镜", ("accessories",)),
            ("领带", ("accessories",)),
            ("领结", ("accessories",)),
            ("手表", ("accessories",)),
            ("腕表", ("accessories",)),
            ("发带", ("accessories",)),
            ("发夹", ("accessories",)),
            ("发箍", ("accessories",)),
            ("道具", ("props",)),
        ),
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

_CN_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


def _parse_number(token: str) -> int | None:
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token in _CN_NUMBERS:
        return _CN_NUMBERS[token]
    if token == "十一":
        return 11
    if token == "十二":
        return 12
    return None


def find_shot_codes(sentence: str) -> list[str]:
    codes: list[str] = []
    for pattern in _SHOT_PATTERNS:
        for match in pattern.finditer(sentence):
            number = _parse_number(match.group(1))
            if number and 1 <= number <= 999:
                code = f"S{number}"
                if code not in codes:
                    codes.append(code)
    return codes


def _has_change_verb(fragment: str) -> bool:
    for match in _CHANGE_WORDS.finditer(fragment):
        if _NEGATION.search(fragment[: match.start()]):
            continue
        return True
    return False


_CLAUSE_BOUNDARY = re.compile(r"[，,。；;]")


def _clause_at(sentence: str, position: int) -> str:
    """取 position 所在的分句；顿号不切分，便于「发型、发色、配饰允许变化」这种列写。"""

    start = 0
    end = len(sentence)
    for match in _CLAUSE_BOUNDARY.finditer(sentence):
        if match.start() < position:
            start = match.end()
        elif end == len(sentence):
            end = match.start()
    return sentence[start:end]


def _has_positive_change(sentence: str) -> bool:
    """整句存在未被否定的变化词；「没有变为红色」不算变化描述。"""

    return _has_change_verb(sentence)


def _named_attributes(sentence: str) -> set[str]:
    """找出「要素名 + 变化词」明确写出的要素，避免把整句变化扩成全部服装。"""

    hits: list[tuple[int, int]] = []
    found: set[str] = set()
    for keyword, attribute_ids in _ATTRIBUTE_KEYWORDS:
        start = 0
        while True:
            index = sentence.find(keyword, start)
            if index < 0:
                break
            end = index + len(keyword)
            overlaps = any(index < hit_end and end > hit_start for hit_start, hit_end in hits)
            direct = index > 0 and sentence[index - 1] == "换"
            if not overlaps and (direct or _has_change_verb(_clause_at(sentence, index))):
                hits.append((index, end))
                found.update(attribute_ids)
            start = end
    return found


def parse_script(text: str, shot_codes: list[str] | None = None) -> ScriptContext:
    raw = (text or "").strip()
    warnings: list[str] = []
    unparsed: list[str] = []

    if not raw:
        return ScriptContext(
            rawText="",
            ruleBadge="待填写 · 暂不豁免",
            warnings=["剧本说明为空，暂不建立任何豁免。"],
        )

    sentences = [part.strip() for part in re.split(r"[。；;\n]+", raw) if part.strip()]
    shot_changes: list[ShotChange] = []
    unlocated: list[str] = []
    missing_elements: list[str] = []
    has_no_change = False
    has_change_words = False

    for sentence in sentences:
        no_change = bool(_NO_CHANGE.search(sentence))
        if no_change:
            has_no_change = True
            # 「无换装」中的「换装」不应被当成变化描述
            continue
        if not _has_positive_change(sentence):
            continue
        has_change_words = True
        codes = find_shot_codes(sentence)
        if not codes:
            unlocated.append(sentence)
            continue
        named = _named_attributes(sentence)
        attributes = set(named)
        if _ALL_ATTRIBUTES_WORDS.search(sentence):
            attributes.update(ATTRIBUTE_IDS)
        if not attributes:
            # 只写「换装」而不写要素：不再默认放开整套服装
            missing_elements.append(sentence)
            continue
        ordered = [aid for aid in ATTRIBUTE_IDS if aid in attributes]
        for code in codes:
            if shot_codes and code not in shot_codes:
                warnings.append(f"剧本提到的 {code} 不在当前镜头序列中，已忽略该条豁免。")
                continue
            shot_changes.append(
                ShotChange(
                    shotCode=code,
                    attributes=ordered,
                    changeText=sentence,
                    evidence=sentence,
                )
            )

    if has_no_change and shot_changes:
        warnings.append("剧本同时出现「无换装」与变化描述，按严格比对处理，不建立豁免。")
        shot_changes = []

    if unlocated:
        warnings.append(
            "变化描述尚未定位到镜头，不建立任何豁免。补充镜头号与要素"
            "（如「S2 发色变为红褐色」）后才会开放对应要素。"
        )

    if missing_elements:
        warnings.append(
            "变化描述已定位到镜头，但没有写明具体要素，不建立豁免。"
            "写入如「S3 上装款式改为黑色高领毛衣」后才会开放对应项。"
        )

    if has_no_change:
        badge = "严格比对 · 无豁免"
        global_changes: list[GlobalChange] = []
    elif shot_changes:
        badge = "局部豁免 · 其余严格"
        global_changes = []
    elif unlocated:
        badge = "待定位 · 暂不豁免"
        global_changes = []
    else:
        badge = "严格比对 · 无豁免"
        global_changes = []
        if not has_change_words and _SCENE_WORDS.search(raw):
            warnings.append("场景切换本身不构成外观豁免，将严格比对。")
        elif not has_change_words:
            warnings.append("未识别到变化说明，将严格比对。")

    return ScriptContext(
        rawText=raw,
        globalAllowedChanges=global_changes,
        shotChanges=shot_changes,
        unlocatedChanges=unlocated,
        unparsed=unparsed,
        ruleBadge=badge,
        warnings=warnings,
    )
