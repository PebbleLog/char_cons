"""仅供 E2E 测试的固定观察 Provider 服务器（不用于生产）。

- 初始分析返回定稿示例的受控观察（S2 上装偏冷灰、S3 配饰红橙五瓣）；
- 采用候选后的第二次观察返回 Mock 的设定值，模拟复检修正成功；
- 仍明确使用 Mock 生成服务，不联网、不冒充真实模型。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.providers.mock import MockVisionProvider  # noqa: E402
from tests.test_report import FixedProvider  # noqa: E402


class E2EProvider(FixedProvider):
    def __init__(self) -> None:
        self.seen: dict[str, int] = {}

    async def observe_shot(self, image, *, shot_code, **kwargs):
        self.seen[shot_code] = self.seen.get(shot_code, 0) + 1
        if self.seen[shot_code] > 1:
            return await MockVisionProvider().observe_shot(
                image, shot_code=shot_code, **kwargs
            )
        return await super().observe_shot(image, shot_code=shot_code, **kwargs)


settings = Settings.load()
app = create_app(settings)
_provider = E2EProvider()
app.state.vision_provider_factory = lambda _settings: _provider
