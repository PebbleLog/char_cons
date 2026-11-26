"""测试公共夹具。

注意：先设置 CHAR_CONS_HOME，再导入 app.main，避免模块级 ``app = create_app()``
在真实 %APPDATA% 下创建目录。
"""

from __future__ import annotations

import os
import tempfile

_TEST_HOME = tempfile.mkdtemp(prefix="char_cons_pytest_home_")
os.environ["CHAR_CONS_HOME"] = _TEST_HOME
os.environ.pop("CHAR_CONS_PORT", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import PROJECT_ROOT, Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings(tmp_path) -> Settings:
    settings = Settings(
        home_dir=tmp_path / "home",
        frontend_dir=PROJECT_ROOT / "frontend",
        migrations_dir=PROJECT_ROOT / "app" / "migrations",
    )
    # 测试默认使用 Mock 视觉与生成 Provider：不联网、结果固定且明确标注 mock
    settings.analysis_provider = "mock"
    settings.analysis_model = "mock-vision"
    settings.generation_provider = "mock"
    settings.generation_model = "mock-seedream"
    return settings


@pytest.fixture
def app(settings: Settings):
    return create_app(settings, configure_logs=False)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
