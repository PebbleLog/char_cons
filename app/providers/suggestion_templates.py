"""确定性修正建议模板。

用途：
- Mock Provider 与「模型不可用时的本地回退」共用，保证闭环可用；
- 输出结构与 SuggestionOutput 完全一致，绝不引入设定未定义的新外观；
- 所有来源都会在 suggestions.source 中标注 ai / local / mock，不冒充模型结果。
"""

from __future__ import annotations

from typing import Any

from .schemas import CharacterProfile, ScriptContext


def build_local_card_plan(
    *,
    issue: dict[str, Any],
    references: list[dict[str, Any]],
    batch_size: int,
) -> dict[str, Any]:
    attribute_name = issue.get("attributeName") or "目标要素"
    expected = (issue.get("expected") or "").strip()
    reference_codes = [item["shotCode"] for item in references if item.get("shotCode")]
    if expected:
        criteria = [
            f"{attribute_name}与设定一致（期望：{expected}）",
            (
                f"该要素与参考镜头 {reference_codes[0]} 一致"
                if reference_codes
                else "同一角色跨批次特征稳定"
            ),
            "保持当前镜头原构图、机位与景别，不直接复刻参考镜头",
        ]
    else:
        criteria = [
            (
                f"{attribute_name}与参考镜头 {reference_codes[0]} 一致"
                if reference_codes
                else f"{attribute_name}在各批次之间保持一致"
            ),
            "未引入设定之外的新外观",
            "保持当前镜头原构图、机位与景别，不直接复刻参考镜头",
        ]
    return {
        "batchSize": max(1, min(4, int(batch_size or 4))),
        "referenceShots": reference_codes,
        "selectionCriteria": criteria,
        "escalation": (
            "首批均不满足时，强化目标要素描述并更换参考镜头后重抽；"
            "仍不稳定时拆分提示词，分步固定角色特征。"
        ),
        "supportedParams": ["referenceImage", "seed", "size"],
        "negativePromptMode": "merged",
    }


def build_local_suggestion(
    *,
    issue: dict[str, Any],
    profile: CharacterProfile,
    script: ScriptContext,
    references: list[dict[str, Any]],
    batch_size: int,
    existing_prompt: str | None = None,
) -> dict[str, Any]:
    attribute_name = issue.get("attributeName") or "目标要素"
    expected = (issue.get("expected") or "").strip()
    observed = (issue.get("observed") or "").strip()
    reference_codes = [item["shotCode"] for item in references if item.get("shotCode")]
    reference_text = (
        f"与参考镜头 {reference_codes[0]} 一致" if reference_codes else "保持角色特征稳定"
    )
    if expected:
        change_text = (
            f"仅将{attribute_name}由「{observed}」改为「{expected}」"
            if observed
            else f"仅将{attribute_name}改为「{expected}」"
        )
    else:
        change_text = f"仅将{attribute_name}调整为{reference_text}"
    parts = ["保持当前镜头原构图、机位、人物姿态、背景与光线不变", change_text]
    if existing_prompt and existing_prompt.strip():
        parts.append(f"原有要求：{existing_prompt.strip()}")
    revised_prompt = "，".join(parts) + "。"

    negatives = ["五官漂移", "发型改变", "服装款式改变", "配饰缺失", "多人物", "文字水印"]
    if observed:
        negatives.insert(0, observed)
    negative_prompt = "，".join(dict.fromkeys(negatives))

    key_points = [
        f"锁定{attribute_name}：{expected or reference_text}",
        (
            f"引用 {reference_codes[0]} 作为角色参考"
            if reference_codes
            else "无合格参考镜头，采用提示词 + 多批重抽策略"
        ),
        "保留原有构图与镜头语言，避免引入设定外的新外观",
    ]

    rationale = (
        f"{issue.get('shotCode') or '该镜头'} 的{attribute_name}"
        f"观察到「{observed or '与设定不符'}」，与设定/参考不一致；"
        f"{'期望值为「' + expected + '」。' if expected else '设定未定义该要素，因此只要求与参考镜头一致，不臆造具体外观。'}"
        f"剧本规则为「{script.rule_badge}」，本次修正不涉及豁免范围。"
    )

    plan = build_local_card_plan(
        issue=issue, references=references, batch_size=batch_size
    )
    return {
        "revisedPrompt": revised_prompt,
        "negativePrompt": negative_prompt,
        "negativePromptMode": "merged",
        "keyPoints": key_points,
        "referenceShots": reference_codes,
        "rationale": rationale,
        "cardDrawPlan": plan,
    }
