"""真实 Seedream 生成实测（默认跳过，会产生费用）。

启用：
    set CHAR_CONS_LIVE_GENERATION=1
    set CHAR_CONS_GENERATION_MODEL=<控制台模型 ID>
    set CHAR_CONS_GENERATION_API_KEY=<生成服务 Key>
    python -m pytest tests/test_live_generation.py -s
"""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from app.core.config import Settings
from app.providers.doubao_seedream import DoubaoSeedreamProvider

LIVE_ENABLED = os.environ.get("CHAR_CONS_LIVE_GENERATION") == "1"
MODEL_ID = (os.environ.get("CHAR_CONS_GENERATION_MODEL") or "").strip()

pytestmark = pytest.mark.skipif(
    not (LIVE_ENABLED and MODEL_ID),
    reason="未启用真实生成实测：需要 CHAR_CONS_LIVE_GENERATION=1 与 CHAR_CONS_GENERATION_MODEL",
)


async def test_live_single_candidate():
    settings = Settings.load()
    settings.generation_provider = "doubao"
    settings.generation_model = MODEL_ID
    provider = DoubaoSeedreamProvider(settings)
    generated = await provider.generate(
        prompt="纯色浅灰背景，无人物、无文字，本地连通性测试。",
        references=[],
        size=None,
        seed=1,
    )
    assert generated.image_bytes
    with Image.open(io.BytesIO(generated.image_bytes)) as image:
        image.verify()
    print(
        "\n真实生成返回："
        f"requestId={generated.request_id} model={generated.model} "
        f"bytes={len(generated.image_bytes)}"
    )
