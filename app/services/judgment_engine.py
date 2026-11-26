"""确定性一致性判定引擎（R1～R10）。

- AI 只提供观察；本模块负责判定、豁免、疑似、无法判断、仅记录与统计；
- 规则优先级：R1 镜头失败 → R2/R10 不可见或证据不足 → R4 豁免 → R5/R6 比对 → R7 仅记录 → R9 疑似；
- 设定未定义的要素不做跨镜头对比：可见则仅记录，不可见则无法判断；
- 统计口径按「镜头 × 要素」；定稿示例为 33 = 12+2+14+5+0。

关于口径的说明（2026-11-25 已确认）：设定未定义只表示“没有设定期望值”，
不表示可以跨镜头推断期望。未定义要素不会生成问题或提示；可见时只记录观察事实，
不可见/缺少观察值时按无法判断处理，不再执行 R8 镜头间冲突提升。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from ..core.constants import ATTRIBUTE_IDS, ATTRIBUTE_NAMES
from ..providers.schemas import CharacterProfile, ScriptContext

MatchLevel = str  # match / mismatch / suspect

_COLOR_FAMILIES: tuple[tuple[str, str], ...] = (
    ("冷灰", "gray"), ("浅灰", "gray"), ("深灰", "gray"), ("灰", "gray"),
    ("藏青", "blue"), ("深蓝", "blue"), ("宝蓝", "blue"), ("天蓝", "blue"),
    ("浅蓝", "blue"), ("蓝", "blue"),
    ("浅米", "beige"), ("暖白", "beige"), ("米白", "beige"), ("米色", "beige"),
    ("杏色", "beige"), ("卡其", "beige"),
    ("深棕", "brown"), ("浅棕", "brown"), ("栗棕", "brown"), ("棕", "brown"),
    ("黑色", "black"), ("黑", "black"), ("白色", "white"), ("白", "white"),
    ("红色", "red"), ("红", "red"), ("橙色", "orange"), ("橙", "orange"),
    ("黄色", "yellow"), ("黄", "yellow"), ("金色", "yellow"), ("金", "yellow"),
    ("绿色", "green"), ("绿", "green"), ("紫色", "purple"), ("紫", "purple"),
    ("粉色", "pink"), ("粉", "pink"), ("银色", "silver"), ("银", "silver"),
)
_LIGHT_DARK = ("深", "浅", "暗", "明")

_STYLE_CATEGORIES: dict[str, str] = {
    "西装外套": "outerwear", "外套": "outerwear", "风衣": "outerwear",
    "夹克": "outerwear", "大衣": "outerwear",
    "西装": "suit", "衬衫": "shirt", "T恤": "tshirt", "polo衫": "tshirt",
    "卫衣": "sweatshirt", "连帽衫": "sweatshirt", "毛衣": "sweater",
    "针织衫": "sweater", "连衣裙": "dress", "制服": "uniform",
    "背心": "vest", "长裤": "pants", "短裤": "shorts", "裙": "skirt",
    "半身裙": "skirt", "背带裤": "overalls",
}
_HAIR_STYLES = (
    "低侧发髻", "高马尾", "低马尾", "双马尾", "丸子头", "披肩发",
    "齐刘海", "侧分刘海", "马尾", "编发", "卷发", "直发", "盘发", "发髻",
)
_HAIR_LENGTHS = ("超长发", "超短发", "齐肩发", "长发", "短发", "齐肩")
_ACCESSORY_NONE = ("无", "未佩戴", "没有", "缺失", "未戴")

_ATTRIBUTE_SEVERITY = {
    "hair_style": "medium", "hair_color": "medium", "top_style": "medium",
    "top_color": "medium", "accessories": "medium",
    "top_pattern": "low", "bottom_style": "low", "bottom_color": "low",
    "bottom_pattern": "low", "shoes": "low", "props": "low",
}


def _norm(value: str | None) -> str:
    return re.sub(r"[\s，。,.、；;：:（）()【】\[\]]+", "", (value or "").lower())


def _color_family(value: str | None) -> str | None:
    text = value or ""
    for token, family in _COLOR_FAMILIES:
        if token in text:
            return family
    return None


def _style_category(value: str | None) -> str | None:
    text = value or ""
    for token, category in _STYLE_CATEGORIES.items():
        if token in text:
            return category
    return None


def _tokens(value: str | None, tokens: Sequence[str]) -> set[str]:
    text = value or ""
    return {token for token in tokens if token in text}


def compare_values(attribute_id: str, expected: str, observed: str) -> MatchLevel:
    exp, obs = _norm(expected), _norm(observed)
    if not exp or not obs:
        return "mismatch"
    if exp == obs:
        return "match"

    if attribute_id.endswith("_color"):
        exp_f, obs_f = _color_family(expected), _color_family(observed)
        if exp_f and obs_f:
            if exp_f != obs_f:
                return "mismatch"
            exp_deep = any(tok in (expected or "") for tok in ("深", "暗"))
            obs_deep = any(tok in (observed or "") for tok in ("深", "暗"))
            exp_light = any(tok in (expected or "") for tok in ("浅", "明"))
            obs_light = any(tok in (observed or "") for tok in ("浅", "明"))
            if (exp_deep and obs_light) or (exp_light and obs_deep):
                # 同色系但明度明显相反：疑似，而非确定问题
                return "suspect"
            return "match"
        return "match" if exp in obs or obs in exp else "mismatch"

    if attribute_id == "hair_style":
        exp_styles, obs_styles = _tokens(expected, _HAIR_STYLES), _tokens(observed, _HAIR_STYLES)
        if exp_styles and obs_styles and not (exp_styles & obs_styles):
            return "mismatch"
        exp_len, obs_len = _tokens(expected, _HAIR_LENGTHS), _tokens(observed, _HAIR_LENGTHS)
        if exp_len and obs_len and exp_len != obs_len:
            return "mismatch"
        return "match"

    if attribute_id.endswith("_style"):
        exp_c, obs_c = _style_category(expected), _style_category(observed)
        if exp_c and obs_c:
            return "match" if exp_c == obs_c else "mismatch"
        return "match" if exp in obs or obs in exp else "mismatch"

    if attribute_id == "accessories":
        if any(token in (observed or "") for token in _ACCESSORY_NONE):
            return "mismatch"
        required: set[str] = set()
        for token, _family in _COLOR_FAMILIES:
            if token in (expected or ""):
                required.add(token)
        for token in re.findall(r"[一二三四五六七八九十两\d]+[瓣角边]", expected or ""):
            required.add(token)
        required = {token for token in required if _norm(token) not in obs}
        return "mismatch" if required else "match"

    if attribute_id in ("top_pattern", "bottom_pattern"):
        return "match" if exp in obs or obs in exp else "mismatch"

    # 鞋履/道具等：若双方都有颜色且色系不同，直接判不一致
    exp_f, obs_f = _color_family(expected), _color_family(observed)
    if exp_f and obs_f and exp_f != obs_f:
        return "mismatch"
    return "match" if exp in obs or obs in exp else "mismatch"


@dataclass
class ObservationView:
    attribute_id: str
    observed_value: str | None
    visibility: str
    visibility_reason: str | None = None
    evidence: str | None = None
    confidence: str | None = None


@dataclass
class ShotView:
    shot_id: str
    shot_code: str
    seq: int
    version_id: str
    analysis_status: str
    observations: dict[str, ObservationView] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None


@dataclass
class UnitDecision:
    shot_id: str
    shot_code: str
    version_id: str
    attribute_id: str
    verdict: str
    expected: str | None
    observed: str | None
    reason: str | None = None
    confidence: str | None = None
    severity: str | None = None
    issue_type: str | None = None
    visibility: str | None = None
    evidence: str | None = None
    is_suspected: bool = False


@dataclass
class IssueDraft:
    unit: UnitDecision
    attribute_name: str
    type: str


@dataclass
class UnknownDraft:
    unit: UnitDecision
    attribute_name: str


@dataclass
class WaiverDraft:
    unit: UnitDecision
    attribute_name: str
    script_evidence: str


@dataclass
class SuspectedDraft:
    unit: UnitDecision
    attribute_name: str


@dataclass
class JudgmentResult:
    units: list[UnitDecision]
    issues: list[IssueDraft]
    unknown_items: list[UnknownDraft]
    waivers: list[WaiverDraft]
    suspected: list[SuspectedDraft]
    shot_conclusions: dict[str, str | None]
    stats: dict[str, int]
    summary: str


def _is_defined(profile: CharacterProfile, attribute_id: str) -> tuple[bool, str | None]:
    attribute = next(
        (item for item in profile.attributes if item.attribute_id == attribute_id), None
    )
    if attribute and attribute.source == "explicit" and attribute.value:
        return True, attribute.value
    return False, None


def _conclusion_for(units: Sequence[UnitDecision]) -> str:
    if any(unit.verdict == "inconsistent" for unit in units):
        return "issue"
    if any(unit.verdict == "unknown" for unit in units):
        return "unknown"
    return "ok"


def judge(
    profile: CharacterProfile,
    script: ScriptContext,
    shots: Sequence[ShotView],
    *,
    character_name: str,
) -> JudgmentResult:
    units: list[UnitDecision] = []
    issues: list[IssueDraft] = []
    unknowns: list[UnknownDraft] = []
    waivers: list[WaiverDraft] = []
    suspected: list[SuspectedDraft] = []
    conclusions: dict[str, str | None] = {}

    successful = [shot for shot in shots if shot.analysis_status == "ok"]

    for shot in shots:
        if shot.analysis_status != "ok":
            conclusions[shot.shot_id] = None
            continue
        shot_units: list[UnitDecision] = []
        allowed = script.allowed_for_shot(shot.shot_code)
        for attribute_id in ATTRIBUTE_IDS:
            name = ATTRIBUTE_NAMES[attribute_id]
            defined, expected = _is_defined(profile, attribute_id)
            observation = shot.observations.get(attribute_id)

            if observation is None:
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "unknown", expected, None, "缺少该要素的观察数据。",
                    None, None, None, "not_visible",
                )
                units.append(unit); shot_units.append(unit)
                unknowns.append(UnknownDraft(unit, name))
                continue

            observed = observation.observed_value
            visibility = observation.visibility

            # R2 / R10：不可见或没有观察值优先；设定未定义也一样无法记录事实
            if visibility == "not_visible" or not observed:
                reason = observation.visibility_reason or "画面中该要素不可见或缺少观察值。"
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "unknown", expected, None, reason,
                    observation.confidence, None, None, visibility,
                )
                units.append(unit); shot_units.append(unit)
                unknowns.append(UnknownDraft(unit, name))
                continue

            # R7：设定未定义但可见 → 仅记录观察事实，不判对错、不跨镜头提示
            if not defined:
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "observed_only", None, observed,
                    observation.visibility_reason if visibility == "not_visible" else None,
                    observation.confidence, None, None, visibility,
                    observation.evidence,
                )
                units.append(unit); shot_units.append(unit)
                continue

            # R4：剧本豁免（在不可见检查之后）
            if attribute_id in allowed:
                evidence = _script_evidence(script, shot.shot_code)
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "waived", expected, observed, evidence,
                    observation.confidence, None, None, visibility,
                    observation.evidence,
                )
                units.append(unit); shot_units.append(unit)
                waivers.append(WaiverDraft(unit, name, evidence))
                continue

            # R10：缺少证据不得判定
            if not observation.evidence or not observed:
                reason = observation.visibility_reason or "缺少足以支撑判定的画面证据。"
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "unknown", expected, observed, reason,
                    observation.confidence, None, None, visibility,
                )
                units.append(unit); shot_units.append(unit)
                unknowns.append(UnknownDraft(unit, name))
                continue

            level = compare_values(attribute_id, expected, observed)
            if level == "match":
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "consistent", expected, observed, None,
                    observation.confidence, None, None, visibility,
                    observation.evidence,
                )
                units.append(unit); shot_units.append(unit)
                continue

            if level == "suspect" or observation.confidence == "low":
                reason = (
                    "低置信度或细微差异，尚不足以形成确定结论，疑似与设定不一致。"
                    if observation.confidence == "low"
                    else "同色系但明度/色温存在差异，疑似不一致。"
                )
                unit = UnitDecision(
                    shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                    "unknown", expected, observed, reason,
                    observation.confidence, None, None, visibility,
                    observation.evidence, True,
                )
                units.append(unit); shot_units.append(unit)
                suspected.append(SuspectedDraft(unit, name))
                continue

            # R6：确定不一致
            unit = UnitDecision(
                shot.shot_id, shot.shot_code, shot.version_id, attribute_id,
                "inconsistent", expected, observed,
                observation.visibility_reason,
                observation.confidence,
                _ATTRIBUTE_SEVERITY.get(attribute_id, "medium"),
                "profile_violation", visibility, observation.evidence,
            )
            units.append(unit); shot_units.append(unit)
            issues.append(IssueDraft(unit, name, "profile_violation"))

        conclusions[shot.shot_id] = _conclusion_for(shot_units)

    issues.sort(key=lambda item: (item.unit.shot_code, ATTRIBUTE_IDS.index(item.unit.attribute_id)))
    unknowns.sort(key=lambda item: (item.unit.shot_code, ATTRIBUTE_IDS.index(item.unit.attribute_id)))
    waivers.sort(key=lambda item: (item.unit.shot_code, ATTRIBUTE_IDS.index(item.unit.attribute_id)))
    suspected.sort(key=lambda item: (item.unit.shot_code, ATTRIBUTE_IDS.index(item.unit.attribute_id)))

    counts = {verdict: 0 for verdict in ("consistent", "inconsistent", "unknown", "waived", "observed_only")}
    for unit in units:
        counts[unit.verdict] += 1

    failed_shots = len(shots) - len(successful)
    stats = {
        "totalShots": len(shots),
        "totalUnits": len(units),
        "failedShots": failed_shots,
        "consistent": counts["consistent"],
        "inconsistent": counts["inconsistent"],
        "confirmedIssues": len(issues),
        "unknown": counts["unknown"],
        "waived": counts["waived"],
        "observedOnly": counts["observed_only"],
        "suspectedIssues": len(suspected),
    }
    summary = _summary(character_name, stats, issues, unknowns)
    return JudgmentResult(
        units=units,
        issues=issues,
        unknown_items=unknowns,
        waivers=waivers,
        suspected=suspected,
        shot_conclusions=conclusions,
        stats=stats,
        summary=summary,
    )


def _script_evidence(script: ScriptContext, shot_code: str) -> str:
    for change in script.shot_changes:
        if change.shot_code == shot_code:
            return change.evidence or change.change_text or script.raw_text
    return script.raw_text


def _summary(
    character_name: str,
    stats: dict[str, int],
    issues: Sequence[IssueDraft],
    unknowns: Sequence[UnknownDraft],
) -> str:
    name = character_name or "该角色"
    if stats["totalUnits"] == 0:
        return "全部镜头观察失败，未生成一致性结论。"
    if issues:
        head = f"{name}在 {stats['totalShots']} 个镜头中有 {len(issues)} 处确定不一致"
        locations = "、".join(
            f"{issue.unit.shot_code} 的{issue.attribute_name}" for issue in issues[:4]
        )
        text = f"{head}，集中在 {locations}"
    else:
        text = f"{name}的 {stats['totalShots']} 个镜头中已无确定不一致"
    if unknowns:
        text += f"；另有 {len(unknowns)} 项信息因画面不可见或证据不足，无法判断"
    if stats["failedShots"]:
        text += f"；{stats['failedShots']} 个镜头观察失败，报告仅覆盖成功镜头"
    return text + "。"
