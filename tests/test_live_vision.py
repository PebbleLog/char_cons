"""真实模型实测（默认跳过）。

启用方式（需要真实火山方舟账号，会产生调用费用）：
    set CHAR_CONS_LIVE_VISION=1
    set CHAR_CONS_ANALYSIS_MODEL=<控制台中的视觉模型 ID>
    set CHAR_CONS_ANALYSIS_API_KEY=<Key>            # 或保存到 Windows 凭据管理器
    python -m pytest tests/test_live_vision.py -s

注意：这是【待实测】能力验证，不在默认测试中自动运行。
"""

from __future__ import annotations

import os

import pytest

from app.core.config import Settings
from app.providers.doubao_vision import DoubaoVisionProvider

LIVE_ENABLED = os.environ.get("CHAR_CONS_LIVE_VISION") == "1"
MODEL_ID = (os.environ.get("CHAR_CONS_ANALYSIS_MODEL") or "").strip()

pytestmark = pytest.mark.skipif(
    not (LIVE_ENABLED and MODEL_ID),
    reason="未启用真实模型实测：需要 CHAR_CONS_LIVE_VISION=1 与 CHAR_CONS_ANALYSIS_MODEL",
)


async def test_live_profile_parse():
    settings = Settings.load()
    settings.analysis_provider = "doubao"
    settings.analysis_model = MODEL_ID
    provider = DoubaoVisionProvider(settings)

    result = await provider.parse_profile(
        "阿岚，深棕长发低侧发髻，浅米色亚麻西装外套，圆形吊坠项链（蓝紫四瓣花）。"
    )

    profile = result.value
    explicit = profile.explicit_values()
    print("\n真实模型返回：", explicit)
    print("requestId:", result.request_id, "usage:", result.usage)
    assert profile.explicit_count >= 3
    assert "hair_color" in explicit
    assert "top_color" in explicit
