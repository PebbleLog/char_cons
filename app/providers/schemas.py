"""AI 结构化输出模型（Pydantic 约束）。

- CharacterProfile：恰好 11 个要素，缺失项补为 undefined（不推断）；
- ShotObservation：恰好 11 条观察；可见要素必须有值+证据，不可见必须有原因；
- ScriptContext：确定性剧本规则的结果，不交给模型自由决定。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..core.constants import ATTRIBUTE_IDS, ATTRIBUTE_NAMES

Visibility = Literal["visible", "partial", "not_visible"]
Confidence = Literal["high", "medium", "low"]
RuleBadge = Literal[
    "严格比对 · 无豁免",
    "局部豁免 · 其余严格",
    "待定位 · 暂不豁免",
    "待填写 · 暂不豁免",
]

# 历史保留：早期版本「只写换装」时的默认服装范围。
# 当前规则只豁免剧本写明的要素，未写要素不建立任何豁免；
# 该常量不再参与 script_parser 的判定。
_ALLOWED_CHANGE_ATTRIBUTES = (
    "top_style",
    "top_color",
    "top_pattern",
    "bottom_style",
    "bottom_color",
    "bottom_pattern",
    "shoes",
)


class _Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class ProfileAttribute(_Model):
    attribute_id: str = Field(alias="id")
    name: str | None = None
    value: str | None = None
    source: Literal["explicit", "undefined"] = "undefined"
    evidence_text: str | None = Field(default=None, alias="evidenceText")
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def _normalize(self) -> "ProfileAttribute":
        self.value = (self.value or "").strip() or None
        self.evidence_text = (self.evidence_text or "").strip() or None
        if self.source == "explicit" and not self.value:
            self.source = "undefined"
        if self.source == "undefined":
            self.value = None
            self.evidence_text = None
        self.name = ATTRIBUTE_NAMES.get(self.attribute_id, self.name)
        return self


class CharacterProfile(_Model):
    # 原文由调用方回填；模型只负责结构化要素，避免因未回显原文而整条解析失败。
    raw_text: str = Field(default="", alias="rawText")
    attributes: list[ProfileAttribute] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _normalize(self) -> "CharacterProfile":
        known: dict[str, ProfileAttribute] = {}
        for attribute in self.attributes:
            if attribute.attribute_id in ATTRIBUTE_IDS:
                known[attribute.attribute_id] = attribute
        self.attributes = [
            known.get(aid)
            or ProfileAttribute(id=aid, name=ATTRIBUTE_NAMES[aid], source="undefined")
            for aid in ATTRIBUTE_IDS
        ]
        return self

    @property
    def explicit_count(self) -> int:
        return sum(1 for attribute in self.attributes if attribute.source == "explicit")

    def explicit_values(self) -> dict[str, str]:
        return {
            attribute.attribute_id: attribute.value
            for attribute in self.attributes
            if attribute.source == "explicit" and attribute.value
        }


class SubjectInfo(_Model):
    person_count: int = Field(alias="personCount", ge=0, le=50, default=1)
    main_subject: bool = Field(alias="mainSubject", default=True)
    confidence: float | None = Field(default=None, ge=0, le=1)
    note: str | None = None

    @model_validator(mode="after")
    def _strip(self) -> "SubjectInfo":
        self.note = (self.note or "").strip() or None
        return self


_VISIBILITY_ALIASES = {
    "visible": "visible",
    "partially_visible": "partial",
    "partiallyvisible": "partial",
    "partial_visible": "partial",
    "partial": "partial",
    "not_visible": "not_visible",
    "notvisible": "not_visible",
    "invisible": "not_visible",
    "可见": "visible",
    "完全可见": "visible",
    "部分可见": "partial",
    "不完全可见": "partial",
    "不可见": "not_visible",
}


class ObservationItem(_Model):
    attribute_id: str = Field(alias="attributeId")
    observed_value: str | None = Field(default=None, alias="observedValue")
    visibility: Visibility
    visibility_reason: str | None = Field(default=None, alias="visibilityReason")
    evidence: str | None = None
    confidence: Confidence | None = None

    @field_validator("visibility", mode="before")
    @classmethod
    def _normalize_visibility(cls, value):
        if not isinstance(value, str):
            return value
        key = value.strip().lower().replace("-", "_").replace(" ", "_")
        return _VISIBILITY_ALIASES.get(key, _VISIBILITY_ALIASES.get(value.strip(), value))

    @model_validator(mode="after")
    def _check_evidence(self) -> "ObservationItem":
        for field in ("observed_value", "visibility_reason", "evidence"):
            value = getattr(self, field)
            setattr(self, field, value.strip() if isinstance(value, str) else value)
            if getattr(self, field) == "":
                setattr(self, field, None)

        if self.visibility == "not_visible":
            if not self.visibility_reason:
                raise ValueError("不可见要素必须填写原因")
            self.observed_value = None
            self.evidence = None
        else:
            if not self.observed_value:
                raise ValueError("可见/部分可见要素必须填写观察值")
            if not self.evidence:
                raise ValueError("可见/部分可见要素必须填写证据")
        return self


class ShotObservation(_Model):
    subject: SubjectInfo = Field(default_factory=SubjectInfo)
    observations: list[ObservationItem]

    @model_validator(mode="after")
    def _exactly_all_attributes(self) -> "ShotObservation":
        seen: dict[str, ObservationItem] = {}
        for item in self.observations:
            if item.attribute_id not in ATTRIBUTE_IDS:
                raise ValueError(f"未知要素：{item.attribute_id}")
            if item.attribute_id in seen:
                raise ValueError(f"要素重复：{item.attribute_id}")
            seen[item.attribute_id] = item
        missing = [aid for aid in ATTRIBUTE_IDS if aid not in seen]
        if missing:
            raise ValueError(f"缺少要素：{', '.join(missing)}")
        self.observations = [seen[aid] for aid in ATTRIBUTE_IDS]
        return self


class GlobalChange(_Model):
    attributes: list[str] = Field(default_factory=list)
    evidence: str = ""


class ShotChange(_Model):
    shot_code: str = Field(alias="shotCode")
    attributes: list[str] = Field(default_factory=list)
    change_text: str = Field(default="", alias="changeText")
    evidence: str = ""


class ScriptContext(_Model):
    raw_text: str = Field(alias="rawText", default="")
    global_allowed_changes: list[GlobalChange] = Field(
        default_factory=list, alias="globalAllowedChanges"
    )
    shot_changes: list[ShotChange] = Field(default_factory=list, alias="shotChanges")
    unlocated_changes: list[str] = Field(default_factory=list, alias="unlocatedChanges")
    unparsed: list[str] = Field(default_factory=list)
    rule_badge: RuleBadge = Field(alias="ruleBadge", default="严格比对 · 无豁免")
    warnings: list[str] = Field(default_factory=list)

    def allowed_for_shot(self, shot_code: str) -> set[str]:
        allowed: set[str] = set()
        for change in self.shot_changes:
            if change.shot_code == shot_code:
                allowed.update(change.attributes)
        for change in self.global_allowed_changes:
            allowed.update(change.attributes)
        return allowed


CHANGE_ATTRIBUTES: tuple[str, ...] = _ALLOWED_CHANGE_ATTRIBUTES


_ALLOWED_GENERATION_PARAMS = {"referenceImage", "seed", "size"}


class CardDrawPlan(_Model):
    batch_size: int = Field(alias="batchSize", ge=1, le=4, default=4)
    reference_shots: list[str] = Field(default_factory=list, alias="referenceShots")
    selection_criteria: list[str] = Field(alias="selectionCriteria")
    escalation: str
    supported_params: list[str] = Field(
        default_factory=lambda: ["referenceImage", "seed", "size"],
        alias="supportedParams",
    )
    negative_prompt_mode: Literal["merged"] = Field(
        default="merged", alias="negativePromptMode"
    )

    @field_validator("selection_criteria")
    @classmethod
    def _criteria(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        if not cleaned:
            raise ValueError("抽卡挑选标准不能为空")
        if len(cleaned) > 6:
            cleaned = cleaned[:6]
        return cleaned

    @field_validator("supported_params")
    @classmethod
    def _supported_params(cls, value: list[str]) -> list[str]:
        # 只保留服务实际支持的能力，避免向用户承诺不存在的参数。
        cleaned = [item for item in value if item in _ALLOWED_GENERATION_PARAMS]
        return cleaned or ["referenceImage", "seed", "size"]


class SuggestionOutput(_Model):
    revised_prompt: str = Field(alias="revisedPrompt")
    negative_prompt: str = Field(alias="negativePrompt", default="")
    key_points: list[str] = Field(alias="keyPoints")
    reference_shots: list[str] = Field(default_factory=list, alias="referenceShots")
    rationale: str
    card_draw_plan: CardDrawPlan = Field(alias="cardDrawPlan")

    @model_validator(mode="after")
    def _compact(self) -> "SuggestionOutput":
        self.revised_prompt = self.revised_prompt.strip()
        self.negative_prompt = self.negative_prompt.strip()
        self.key_points = [item.strip() for item in self.key_points if item and item.strip()]
        self.rationale = self.rationale.strip()
        if not self.revised_prompt:
            raise ValueError("修正提示词不能为空")
        if len(self.key_points) < 2:
            raise ValueError("修改要点至少 2 条")
        if not self.rationale:
            raise ValueError("必须说明修改理由")
        return self


class PrecheckCriterion(_Model):
    key: str
    name: str
    passed: bool | None = None
    evidence: str = ""

    @model_validator(mode="after")
    def _strip(self) -> "PrecheckCriterion":
        self.key = (self.key or "").strip() or "criterion"
        self.name = (self.name or "").strip()
        self.evidence = (self.evidence or "").strip()
        if not self.name:
            raise ValueError("预检标准名称不能为空")
        if self.passed is None and not self.evidence:
            self.evidence = "画面信息不足，无法判断。"
        return self


class CandidatePrecheck(_Model):
    candidate_code: str = Field(alias="candidateCode")
    overall: Literal["pass", "partial", "fail", "unknown"]
    criteria: list[PrecheckCriterion]
    summary: str = ""

    @model_validator(mode="after")
    def _compact(self) -> "CandidatePrecheck":
        self.candidate_code = self.candidate_code.strip().upper()
        self.summary = (self.summary or "").strip()
        if not self.criteria:
            raise ValueError("候选图预检必须包含逐项标准")
        return self


class PrecheckOutput(_Model):
    candidates: list[CandidatePrecheck]
    mode: Literal["batch", "per_candidate"] = "batch"

    @model_validator(mode="after")
    def _unique(self) -> "PrecheckOutput":
        seen: set[str] = set()
        for candidate in self.candidates:
            if candidate.candidate_code in seen:
                raise ValueError(f"候选编号重复：{candidate.candidate_code}")
            seen.add(candidate.candidate_code)
        return self
