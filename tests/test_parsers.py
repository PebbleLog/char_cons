from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.constants import ATTRIBUTE_IDS
from app.providers.schemas import (
    CharacterProfile,
    ObservationItem,
    ShotObservation,
)
from app.services.profile_local import parse_profile_local
from app.services.script_parser import parse_script

PROFILE_TEXT = (
    "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，黑色丝质衬衫，"
    "紫色口袋巾，圆形吊坠项链（蓝紫四瓣花）。"
)


def test_local_profile_fixed_example():
    profile = parse_profile_local(PROFILE_TEXT)

    assert len(profile.attributes) == 11
    assert [a.attribute_id for a in profile.attributes] == list(ATTRIBUTE_IDS)
    values = {a.attribute_id: a for a in profile.attributes}

    assert values["hair_color"].value == "深棕"
    assert "低侧发髻" in values["hair_style"].value
    assert values["top_style"].value == "亚麻西装外套"
    assert values["top_color"].value == "浅米色"
    assert "项链" in values["accessories"].value
    assert "蓝紫四瓣花" in values["accessories"].value
    assert values["bottom_style"].source == "undefined"
    assert values["bottom_color"].source == "undefined"
    assert values["shoes"].source == "undefined"
    assert values["props"].source == "undefined"
    assert values["top_pattern"].source == "undefined"


def test_local_profile_does_not_infer():
    profile = parse_profile_local("阿岚，短发，穿黄色外套。")
    values = {a.attribute_id: a for a in profile.attributes}

    assert values["hair_style"].value == "短发"
    assert values["top_color"].value == "黄色"
    assert values["hair_color"].source == "undefined"
    assert values["accessories"].source == "undefined"


def test_profile_schema_fills_missing_as_undefined():
    profile = CharacterProfile(
        rawText="只有外套",
        attributes=[
            {"id": "top_style", "value": "外套", "source": "explicit"},
        ],
    )
    assert len(profile.attributes) == 11
    assert profile.explicit_count == 1


def _observation(attribute_id: str, **overrides):
    payload = {
        "attributeId": attribute_id,
        "observedValue": "值",
        "visibility": "visible",
        "evidence": "证据",
        "confidence": "high",
    }
    payload.update(overrides)
    return payload


def test_observation_requires_all_attributes():
    with pytest.raises(ValidationError):
        ShotObservation(observations=[_observation("hair_style")])


def test_observation_requires_reason_for_not_visible():
    items = [_observation(aid) for aid in ATTRIBUTE_IDS]
    items[0] = _observation("hair_style", observedValue=None, visibility="not_visible", evidence=None)
    with pytest.raises(ValidationError):
        ShotObservation(observations=items)


def test_observation_requires_evidence_when_visible():
    items = [_observation(aid) for aid in ATTRIBUTE_IDS]
    items[0] = _observation("hair_style", evidence=None)
    with pytest.raises(ValidationError):
        ShotObservation(observations=items)


def test_observation_orders_attributes():
    items = [_observation(aid) for aid in reversed(ATTRIBUTE_IDS)]
    observation = ShotObservation(observations=items)
    assert [item.attribute_id for item in observation.observations] == list(ATTRIBUTE_IDS)


@pytest.mark.parametrize(
    "text, badge, changed_shots, unlocated",
    [
        ("这些镜头为同一场戏的连续动作，无换装情节。", "严格比对 · 无豁免", [], []),
        ("S3 上装款式改为深色外套。", "局部豁免 · 其余严格", ["S3"], []),
        ("第三个镜头把上装款式换成蓝色卫衣。", "局部豁免 · 其余严格", ["S3"], []),
        ("S3 换装为深色外套。", "严格比对 · 无豁免", [], []),
        ("换装为深色外套。", "待定位 · 暂不豁免", [], ["换装为深色外套"]),
        ("S2 发色变为红褐色。", "局部豁免 · 其余严格", ["S2"], []),
        ("场景切换到夜晚。", "严格比对 · 无豁免", [], []),
    ],
)
def test_script_rules(text, badge, changed_shots, unlocated):
    context = parse_script(text, ["S1", "S2", "S3"])
    assert context.rule_badge == badge
    assert [change.shot_code for change in context.shot_changes] == changed_shots
    assert context.unlocated_changes == unlocated


def test_script_named_clothing_waived():
    context = parse_script(
        "S3 上装款式、上装颜色、上装图案、下装款式、下装颜色、下装图案、鞋履允许变化。",
        ["S1", "S2", "S3"],
    )
    allowed = context.allowed_for_shot("S3")
    assert "top_style" in allowed
    assert "bottom_color" in allowed
    assert "shoes" in allowed
    assert "hair_style" not in allowed
    assert "hair_color" not in allowed
    assert "accessories" not in allowed
    assert "props" not in allowed


def test_script_blanket_word_does_not_expand_unlisted_items():
    context = parse_script(
        "S3 进入咖啡馆后换装，上装款式改为黑色高领毛衣，上装颜色改为黑色。",
        ["S1", "S2", "S3"],
    )
    assert context.allowed_for_shot("S3") == {"top_style", "top_color"}
    assert "bottom_style" not in context.allowed_for_shot("S3")
    assert "shoes" not in context.allowed_for_shot("S3")


def test_script_change_without_elements_is_not_waived():
    context = parse_script("S3 换装。", ["S1", "S2", "S3"])
    assert context.rule_badge == "严格比对 · 无豁免"
    assert context.shot_changes == []
    assert any("没有写明具体要素" in warning for warning in context.warnings)


def test_script_no_change_wins_conflict():
    context = parse_script("无换装。但 S3 上装款式改为深色外套。", ["S1", "S2", "S3"])
    assert context.rule_badge == "严格比对 · 无豁免"
    assert context.shot_changes == []
    assert any("同时出现" in warning for warning in context.warnings)


def test_script_named_attribute_waived_only_for_that_attribute():
    context = parse_script("S2 把发型改为短发。", ["S1", "S2", "S3"])
    assert [change.shot_code for change in context.shot_changes] == ["S2"]
    assert context.allowed_for_shot("S2") == {"hair_style"}
    assert context.allowed_for_shot("S1") == set()


def test_script_hair_color_change_waived():
    context = parse_script("s2 发色变为红色", ["S1", "S2", "S3"])
    assert context.allowed_for_shot("S2") == {"hair_color"}


def test_script_accessory_change_waived():
    context = parse_script("S3 摘下项链。", ["S1", "S2", "S3"])
    assert context.allowed_for_shot("S3") == {"accessories"}


def test_script_change_mixing_costume_and_named_attribute():
    context = parse_script("S2 换装，发色改为红色。", ["S1", "S2", "S3"])
    allowed = context.allowed_for_shot("S2")
    assert allowed == {"hair_color"}


def test_script_unknown_shot_is_ignored_with_warning():
    context = parse_script("S9 上装款式改为深色外套。", ["S1", "S2", "S3"])
    assert context.shot_changes == []
    assert any("S9" in warning for warning in context.warnings)


def test_script_named_change_without_shot_is_unlocated():
    context = parse_script("发色变为红色。", ["S1", "S2", "S3"])
    assert context.rule_badge == "待定位 · 暂不豁免"
    assert context.shot_changes == []
    assert context.unlocated_changes == ["发色变为红色"]


def test_script_negated_change_is_not_waived():
    context = parse_script("S2 发色没有变为红色。", ["S1", "S2", "S3"])
    assert context.shot_changes == []
    assert context.allowed_for_shot("S2") == set()


def test_script_list_style_waives_each_named_attribute():
    context = parse_script(
        "S1、S2、S3 发型、发色、上装款式、上装颜色、配饰允许变化。",
        ["S1", "S2", "S3"],
    )
    expected = {"hair_style", "hair_color", "top_style", "top_color", "accessories"}
    assert context.allowed_for_shot("S2") == expected
    assert [change.shot_code for change in context.shot_changes] == ["S1", "S2", "S3"]


def test_script_all_attributes_waiver():
    context = parse_script("S2 所有要素允许变化。", ["S1", "S2", "S3"])
    assert context.allowed_for_shot("S2") == set(ATTRIBUTE_IDS)
