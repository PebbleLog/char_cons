"""受控回归样本（合成）——不是真实金色样本。

说明：这里通过受控的设定/观察值验证 R1～R10 的确定性判定与统计，
不调用视觉模型，也不能替代「真实模型 + 人工复核标准答案」的金色样本。
真实金色样本仍需 12～20 组人工标注素材，并在真实模型下另行实测与人工复核。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.constants import ATTRIBUTE_IDS
from app.providers.schemas import CharacterProfile, ProfileAttribute
from app.services.judgment_engine import ObservationView, ShotView, judge
from app.services.script_parser import parse_script

BASE_VALUES = {
    "hair_style": "低侧发髻（长发）",
    "hair_color": "深棕",
    "top_style": "亚麻西装外套",
    "top_color": "浅米色",
    "top_pattern": "纯色",
    "bottom_style": "直筒长裤",
    "bottom_color": "黑色",
    "bottom_pattern": "纯色",
    "accessories": "圆形吊坠项链（蓝紫四瓣花）",
    "shoes": "黑色皮鞋",
    "props": "咖啡杯",
}


@dataclass
class SyntheticCase:
    name: str
    purpose: str
    values: dict[str, str] = field(default_factory=lambda: dict(BASE_VALUES))
    script: str = "同一场戏的连续动作，无换装情节。"
    overrides: dict[str, dict] = field(default_factory=dict)
    failed_shots: set[str] = field(default_factory=set)
    expected: dict = field(default_factory=dict)


def _profile(values: dict[str, str]) -> CharacterProfile:
    return CharacterProfile(
        rawText="合成回归样本",
        attributes=[
            ProfileAttribute(
                id=aid,
                value=values.get(aid),
                source="explicit" if values.get(aid) else "undefined",
            )
            for aid in ATTRIBUTE_IDS
        ],
    )


def _shot(
    code: str,
    values: dict[str, str],
    overrides: dict,
    failed: bool,
) -> ShotView:
    if failed:
        return ShotView(
            shot_id=code,
            shot_code=code,
            seq=int(code[1:]),
            version_id=f"ver-{code}",
            analysis_status="failed",
            observations={},
            error_code="provider_timeout",
            error_message="合成回归：该镜头观察失败",
        )
    observations: dict[str, ObservationView] = {}
    for aid in ATTRIBUTE_IDS:
        if aid in overrides:
            observations[aid] = ObservationView(attribute_id=aid, **overrides[aid])
        elif values.get(aid):
            observations[aid] = ObservationView(
                attribute_id=aid,
                observed_value=values[aid],
                visibility="visible",
                evidence="合成回归：画面可见。",
                confidence="high",
            )
        else:
            observations[aid] = ObservationView(
                attribute_id=aid,
                observed_value=None,
                visibility="not_visible",
                visibility_reason="合成回归：该要素未入画。",
            )
    return ShotView(
        shot_id=code,
        shot_code=code,
        seq=int(code[1:]),
        version_id=f"ver-{code}",
        analysis_status="ok",
        observations=observations,
    )


def run_case(case: SyntheticCase):
    profile = _profile(case.values)
    script = parse_script(case.script, ["S1", "S2"])
    shots = [
        _shot(code, case.values, case.overrides.get(code, {}), code in case.failed_shots)
        for code in ("S1", "S2")
    ]
    return judge(profile, script, shots, character_name="合成角色")


def mismatch(value: str, *, confidence: str = "high") -> dict:
    return {
        "observed_value": value,
        "visibility": "visible",
        "evidence": "合成回归：观察值与设定不同。",
        "confidence": confidence,
    }


def invisible(reason: str = "合成回归：被遮挡。") -> dict:
    return {
        "observed_value": None,
        "visibility": "not_visible",
        "visibility_reason": reason,
    }


def no_evidence(value: str) -> dict:
    return {
        "observed_value": value,
        "visibility": "visible",
        "evidence": None,
        "confidence": "high",
    }


def _case(
    name: str,
    purpose: str,
    *,
    values=None,
    script=None,
    overrides=None,
    failed=None,
    consistent=22,
    inconsistent=0,
    unknown=0,
    waived=0,
    observed_only=0,
    issues=(),
    suspected=0,
    conclusions=None,
    failed_shots=0,
):
    return SyntheticCase(
        name=name,
        purpose=purpose,
        values=dict(values or BASE_VALUES),
        script=script or "同一场戏的连续动作，无换装情节。",
        overrides=overrides or {},
        failed_shots=failed or set(),
        expected={
            "totalUnits": consistent + inconsistent + unknown + waived + observed_only,
            "consistent": consistent,
            "inconsistent": inconsistent,
            "unknown": unknown,
            "waived": waived,
            "observedOnly": observed_only,
            "confirmedIssues": len(issues),
            "suspectedIssues": suspected,
            "failedShots": failed_shots,
            "issues": list(issues),
            "conclusions": conclusions or {"S1": "ok", "S2": "ok"},
        },
    )


NO_SHOES = {key: value for key, value in BASE_VALUES.items() if key != "shoes"}

CASES = [
    _case("G01", "全部要素与设定一致", consistent=22),
    _case(
        "G02", "上装颜色不一致",
        overrides={"S2": {"top_color": mismatch("深灰色")}},
        consistent=21, inconsistent=1, issues=[("S2", "top_color")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G03", "配饰图案不一致",
        overrides={"S2": {"accessories": mismatch("蓝紫五瓣吊坠")}},
        consistent=21, inconsistent=1, issues=[("S2", "accessories")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G04", "发型造型不一致",
        overrides={"S2": {"hair_style": mismatch("高马尾（长发）")}},
        consistent=21, inconsistent=1, issues=[("S2", "hair_style")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G05", "发色不一致",
        overrides={"S2": {"hair_color": mismatch("浅金色")}},
        consistent=21, inconsistent=1, issues=[("S2", "hair_color")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G06", "上装款式大类不一致",
        overrides={"S2": {"top_style": mismatch("棉质衬衫")}},
        consistent=21, inconsistent=1, issues=[("S2", "top_style")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G07", "上装图案不一致",
        overrides={"S2": {"top_pattern": mismatch("条纹")}},
        consistent=21, inconsistent=1, issues=[("S2", "top_pattern")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G08", "下装颜色不一致",
        overrides={"S2": {"bottom_color": mismatch("藏青色")}},
        consistent=21, inconsistent=1, issues=[("S2", "bottom_color")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G09", "鞋履颜色不一致",
        overrides={"S2": {"shoes": mismatch("白色运动鞋")}},
        consistent=21, inconsistent=1, issues=[("S2", "shoes")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G10", "道具不一致",
        overrides={"S2": {"props": mismatch("手机")}},
        consistent=21, inconsistent=1, issues=[("S2", "props")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G11", "写明服装要素：七项豁免",
        script="S2 上装款式、上装颜色、上装图案、下装款式、下装颜色、下装图案、鞋履允许变化。",
        overrides={
            "S2": {
                "top_style": mismatch("风衣"),
                "top_color": mismatch("深灰色"),
                "top_pattern": mismatch("格纹"),
            }
        },
        consistent=15, waived=7,
    ),
    _case(
        "G12", "场景切换本身不豁免",
        script="镜头切换到户外场景，光线变冷。",
        overrides={"S2": {"top_color": mismatch("深灰色")}},
        consistent=21, inconsistent=1, issues=[("S2", "top_color")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G13", "低置信度差异 → 疑似问题",
        overrides={"S2": {"top_color": mismatch("深灰色", confidence="low")}},
        consistent=21, unknown=1, suspected=1,
        conclusions={"S1": "ok", "S2": "unknown"},
    ),
    _case(
        "G14", "同色系明显明暗差 → 疑似问题",
        values={**BASE_VALUES, "top_color": "深米色"},
        overrides={"S2": {"top_color": mismatch("浅米色")}},
        consistent=21, unknown=1, suspected=1,
        conclusions={"S1": "ok", "S2": "unknown"},
    ),
    _case(
        "G15", "设定已定义但不可见 → 无法判断",
        overrides={"S2": {"accessories": invisible("胸前被衣领遮挡。")}},
        consistent=21, unknown=1,
        conclusions={"S1": "ok", "S2": "unknown"},
    ),
    _case(
        "G16", "设定未定义但可见 → 仅记录",
        values=NO_SHOES,
        overrides={
            "S1": {"shoes": mismatch("黑色皮鞋")},
            "S2": {"shoes": mismatch("黑色皮鞋")},
        },
        consistent=20, observed_only=2,
    ),
    _case(
        "G17", "设定未定义且镜头间冲突 → 不生成问题",
        values=NO_SHOES,
        overrides={
            "S1": {"shoes": mismatch("黑色皮鞋")},
            "S2": {"shoes": mismatch("白色运动鞋")},
        },
        consistent=20, observed_only=2,
    ),
    _case(
        "G18", "同一镜头多处问题",
        overrides={
            "S2": {
                "top_color": mismatch("深灰色"),
                "accessories": mismatch("蓝紫五瓣吊坠"),
            }
        },
        consistent=20, inconsistent=2,
        issues=[("S2", "top_color"), ("S2", "accessories")],
        conclusions={"S1": "ok", "S2": "issue"},
    ),
    _case(
        "G19", "单镜头观察失败隔离",
        failed={"S2"}, consistent=11, failed_shots=1,
        conclusions={"S1": "ok"},
    ),
    _case(
        "G20", "可见但缺少证据 → 无法判断",
        overrides={"S2": {"accessories": no_evidence("红橙五瓣吊坠")}},
        consistent=21, unknown=1,
        conclusions={"S1": "ok", "S2": "unknown"},
    ),
]
