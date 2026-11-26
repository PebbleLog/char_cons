from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import AppError
from app.core.security import (
    origin_allowed,
    request_source_allowed,
    safe_join,
)


def _make_symlink(link, target) -> bool:
    try:
        link.symlink_to(target, target_is_directory=True)
        return True
    except (OSError, NotImplementedError):
        return False


def test_safe_join_accepts_relative_path(tmp_path):
    root = tmp_path / "root"
    (root / "task" / "S1").mkdir(parents=True)
    resolved = safe_join(root, "task/S1/thumb.jpg")
    assert resolved == (root / "task" / "S1" / "thumb.jpg").resolve()


@pytest.mark.parametrize(
    "bad",
    [
        "../secret.txt",
        "task/../../secret.txt",
        "C:/Windows/win.ini",
        "/etc/passwd",
        "\\\\server\\share\\x.jpg",
        "",
        "bad\x00name.jpg",
    ],
)
def test_safe_join_rejects_escapes(tmp_path, bad):
    with pytest.raises(AppError) as exc_info:
        safe_join(tmp_path, bad)
    assert exc_info.value.code == "invalid_request"


def test_safe_join_rejects_symlink(tmp_path):
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    if not _make_symlink(root / "link", outside):
        pytest.skip("当前系统不允许创建符号链接")
    with pytest.raises(AppError):
        safe_join(root, "link/secret.txt")


def test_origin_rules():
    assert origin_allowed(None, 8765)
    assert origin_allowed("http://127.0.0.1:8765", 8765)
    assert origin_allowed("http://localhost:8765", 8765)
    assert not origin_allowed("http://127.0.0.1:9999", 8765)
    assert not origin_allowed("http://evil.example:8765", 8765)
    assert not origin_allowed("file://127.0.0.1", 8765)
    assert not origin_allowed("not a url", 8765)


def test_request_source_prefers_origin():
    assert request_source_allowed(None, None, 8765)
    assert request_source_allowed(None, "http://127.0.0.1:8765/x", 8765)
    assert not request_source_allowed(None, "http://evil.example/x", 8765)
    assert not request_source_allowed(
        "http://evil.example", "http://127.0.0.1:8765/x", 8765
    )


def _register_write_route(app) -> None:
    @app.post("/api/_test_write")
    async def _test_write():
        return {"ok": True}

    # /api/{rest:path} 兜底路由已注册，测试专用路由需移到它之前；
    # 正式业务路由都在 create_app 中先于兜底注册，不受影响。
    route = app.router.routes.pop()
    fallback_index = next(
        index
        for index, item in enumerate(app.router.routes)
        if getattr(item, "path", None) == "/api/{rest:path}"
    )
    app.router.routes.insert(fallback_index, route)


def test_csrf_required_for_writes(app, settings):
    _register_write_route(app)

    with TestClient(app) as client:
        assert client.post("/api/_test_write").status_code == 403

        token = client.get("/api/session").json()["csrfToken"]
        assert (
            client.post("/api/_test_write", headers={"X-CSRF-Token": "wrong"}).status_code
            == 403
        )

        ok = client.post("/api/_test_write", headers={"X-CSRF-Token": token})
        assert ok.status_code == 200

        same_origin = client.post(
            "/api/_test_write",
            headers={
                "X-CSRF-Token": token,
                "Origin": f"http://127.0.0.1:{settings.port}",
            },
        )
        assert same_origin.status_code == 200

        foreign = client.post(
            "/api/_test_write",
            headers={
                "X-CSRF-Token": token,
                "Origin": "http://evil.example",
            },
        )
        assert foreign.status_code == 403
        assert foreign.json()["error"]["code"] == "csrf_failed"

        bad_referer = client.post(
            "/api/_test_write",
            headers={
                "X-CSRF-Token": token,
                "Referer": "http://127.0.0.1:9999/page",
            },
        )
        assert bad_referer.status_code == 403


def test_csrf_uses_actual_request_port(app, settings):
    """实际监听端口与配置默认值不同时（如命令行 --port），同源校验仍应通过。"""
    _register_write_route(app)
    with TestClient(app, base_url="http://127.0.0.1:8799") as client:
        token = client.get("/api/session").json()["csrfToken"]
        response = client.post(
            "/api/_test_write",
            headers={
                "X-CSRF-Token": token,
                "Origin": "http://127.0.0.1:8799",
            },
        )
        assert response.status_code == 200
        assert settings.port != 8799
