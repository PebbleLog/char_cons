from __future__ import annotations

from app.core.constants import ATTRIBUTE_IDS
from app.services.judgment_engine import (
    ObservationView,
    ShotView,
    compare_values,
    judge,
)
from app.services.profile_local import parse_profile_local
from app.services.script_parser import parse_script

PROFILE = parse_profile_local(
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，"
    "紫色口袋巾，圆形吊坠项链（蓝紫四瓣花）。"
)
SCRIPT = parse_script("这些镜头为同一场戏的连续动作，无换装情节。", ["S1", "S2", "S3"])


def _obs(aid, value, visibility="visible", reason=None, evidence=None, confidence="high"):
    return ObservationView(
        attribute_id=aid,
        observed_value=value,
        visibility=visibility,
        visibility_reason=reason,
        evidence=evidence,
        confidence=confidence,
    )


def _base_observations():
    return {
        "hair_style": _obs("hair_style", "低侧发髻", evidence="低侧发髻轮廓清晰。"),
        "hair_color": _obs("hair_color", "深棕", evidence="发丝为深棕色。"),
        "top_style": _obs("top_style", "亚麻西装外套", evidence="翻领亚麻西装。"),
        "top_color": _obs("top_color", "浅米色", evidence="外套为浅暖米色。"),
        "top_pattern": _obs("top_pattern", "纯色", evidence="外套为纯色。"),
        "bottom_style": _obs("bottom_style", None, "not_visible", "下装未入画。"),
        "bottom_color": _obs("bottom_color", None, "not_visible", "下装未入画。"),
        "bottom_pattern": _obs("bottom_pattern", None, "not_visible", "下装未入画。"),
        "accessories": _obs("accessories", "蓝紫四瓣吊坠", evidence="吊坠完整可见。"),
        "shoes": _obs("shoes", None, "not_visible", "鞋履未入画。"),
        "props": _obs("props", "咖啡杯", evidence="画面下方有咖啡杯。"),
    }


def _fixture_shots():
    s1 = _base_observations()
    s2 = _base_observations()
    s2["top_color"] = _obs("top_color", "冷灰米色", evidence="外套偏冷灰。")
    s2["accessories"] = _obs(
        "accessories", None, "not_visible", "侧身角度胸前被衣领遮挡。"
    )
    s2["props"] = _obs("props", "未入画", "not_visible", "画面未包含道具。")
    s3 = _base_observations()
    s3["accessories"] = _obs("accessories", "红橙五瓣吊坠", evidence="吊坠内部为红橙五瓣。")
    return [
        ShotView("s1", "S1", 1, "v1", "ok", s1),
        ShotView("s2", "S2", 2, "v2", "ok", s2),
        ShotView("s3", "S3", 3, "v3", "ok", s3),
    ]


def test_fixed_example_33_units():
    result = judge(PROFILE, SCRIPT, _fixture_shots(), character_name="阿岚")

    assert result.stats == {
        "totalShots": 3,
        "totalUnits": 33,
        "failedShots": 0,
        "consistent": 12,
        "inconsistent": 2,
        "confirmedIssues": 2,
        "unknown": 14,
        "waived": 0,
        "observedOnly": 5,
        "suspectedIssues": 0,
    }
    assert 12 + 2 + 14 + 5 + 0 == 33
    assert [(i.unit.shot_code, i.unit.attribute_id) for i in result.issues] == [
        ("S2", "top_color"),
        ("S3", "accessories"),
    ]
    assert len(result.unknown_items) == 14
    assert len(result.suspected) == 0
    assert len(result.waivers) == 0
    assert result.shot_conclusions == {"s1": "unknown", "s2": "issue", "s3": "issue"}
    assert "2 处确定不一致" in result.summary
    assert "14 项" in result.summary


def test_color_and_style_tolerances():
    assert compare_values("top_color", "浅米色", "浅暖米色") == "match"
    assert compare_values("top_color", "深蓝", "藏青") == "match"
    assert compare_values("top_color", "深灰", "浅灰") == "suspect"
    assert compare_values("top_color", "浅米色", "红橙") == "mismatch"
    assert compare_values("top_style", "卫衣", "连帽衫") == "match"
    assert compare_values("top_style", "外套", "衬衫") == "mismatch"
    assert compare_values("hair_style", "低侧发髻（长发）", "低侧发髻") == "match"
    assert compare_values("hair_style", "低侧发髻", "高马尾") == "mismatch"
    assert compare_values("accessories", "圆形吊坠项链（蓝紫四瓣花）", "蓝紫四瓣吊坠") == "match"
    assert compare_values("accessories", "圆形吊坠项链（蓝紫四瓣花）", "红橙五瓣吊坠") == "mismatch"


def test_waiver_covers_only_named_attributes():
    script = parse_script(
        "S3 上装颜色改为深色，下装颜色改为深色，鞋履改为黑色。",
        ["S1", "S2", "S3"],
    )
    shots = _fixture_shots()
    result = judge(PROFILE, script, shots, character_name="阿岚")

    s3_top = next(
        unit for unit in result.units if unit.shot_code == "S3" and unit.attribute_id == "top_color"
    )
    assert s3_top.verdict == "waived"
    # 配饰未写明，S3 吊坠仍是不一致
    assert any(i.unit.shot_code == "S3" and i.unit.attribute_id == "accessories" for i in result.issues)
    assert result.stats["waived"] >= 1


def test_named_script_change_waives_only_that_attribute():
    script = parse_script("S2 发色变为红色。", ["S1", "S2", "S3"])
    shots = _fixture_shots()
    shots[1].observations["hair_color"] = _obs(
        "hair_color", "红色", evidence="发色为红色。"
    )
    result = judge(PROFILE, script, shots, character_name="阿岚")

    unit = next(
        unit for unit in result.units
        if unit.shot_code == "S2" and unit.attribute_id == "hair_color"
    )
    assert unit.verdict == "waived"
    assert not any(
        issue.unit.shot_code == "S2" and issue.unit.attribute_id == "hair_color"
        for issue in result.issues
    )
    # 同一镜头写明的其他要素仍按设定严格比对
    assert not script.allowed_for_shot("S2") - {"hair_color"}


def test_invisible_has_priority_over_waiver():
    script = parse_script("S3 上装颜色改为深色。", ["S1", "S2", "S3"])
    shots = _fixture_shots()
    s3 = shots[2]
    s3.observations["top_color"] = _obs(
        "top_color", None, "not_visible", "外套被遮挡。"
    )
    result = judge(PROFILE, script, shots, character_name="阿岚")
    unit = next(
        unit for unit in result.units
        if unit.shot_code == "S3" and unit.attribute_id == "top_color"
    )
    assert unit.verdict == "unknown"


def test_low_confidence_difference_is_suspected_not_confirmed():
    shots = _fixture_shots()
    shots[2].observations["accessories"] = _obs(
        "accessories", "红橙五瓣吊坠", evidence="吊坠图案模糊。", confidence="low"
    )
    result = judge(PROFILE, SCRIPT, shots, character_name="阿岚")
    unit = next(
        unit for unit in result.units
        if unit.shot_code == "S3" and unit.attribute_id == "accessories"
    )
    assert unit.verdict == "unknown"
    assert unit.is_suspected
    assert result.stats["confirmedIssues"] == 1
    assert result.stats["suspectedIssues"] == 1
    assert len(result.suspected) == 1


def test_undefined_cross_shot_difference_is_not_an_issue():
    shots = _fixture_shots()
    shots[0].observations["top_pattern"] = _obs("top_pattern", "纯色", evidence="纯色。")
    shots[1].observations["top_pattern"] = _obs("top_pattern", "条纹", evidence="条纹。")
    shots[2].observations["top_pattern"] = _obs("top_pattern", "纯色", evidence="纯色。")
    result = judge(PROFILE, SCRIPT, shots, character_name="阿岚")

    assert not [unit for unit in result.units if unit.issue_type == "cross_shot_mismatch"]
    assert not [unit for unit in result.units if unit.attribute_id == "top_pattern" and unit.verdict == "inconsistent"]
    assert {
        unit.verdict for unit in result.units if unit.attribute_id == "top_pattern"
    } == {"observed_only"}
    assert [(i.unit.shot_code, i.unit.attribute_id) for i in result.issues] == [
        ("S2", "top_color"),
        ("S3", "accessories"),
    ]


def test_undefined_invisible_is_unknown():
    result = judge(PROFILE, SCRIPT, _fixture_shots(), character_name="阿岚")
    unit = next(
        unit for unit in result.units
        if unit.shot_code == "S2" and unit.attribute_id == "props"
    )
    assert unit.verdict == "unknown"
    assert unit.observed is None
    assert unit.reason


def test_failed_shot_has_no_units():
    shots = _fixture_shots()
    shots[1] = ShotView("s2", "S2", 2, "v2", "failed", {}, "provider_timeout", "超时")
    result = judge(PROFILE, SCRIPT, shots, character_name="阿岚")
    assert result.stats["failedShots"] == 1
    assert result.stats["totalUnits"] == 22
    assert all(unit.shot_code != "S2" for unit in result.units)
    assert result.shot_conclusions["s2"] is None


def test_observed_only_units_use_all_attribute_ids():
    result = judge(PROFILE, SCRIPT, _fixture_shots(), character_name="阿岚")
    assert {unit.attribute_id for unit in result.units} == set(ATTRIBUTE_IDS)
