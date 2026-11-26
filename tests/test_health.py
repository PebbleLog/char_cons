from __future__ import annotations


def test_health_ok(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"] == {"database": "ok", "storage": "ok"}
    assert body["version"]
    assert body["schemaVersion"] == "1.3"
    assert body["uptimeSeconds"] >= 0
    assert response.headers["X-Request-Id"]


def test_health_echoes_safe_request_id(client):
    response = client.get("/api/health", headers={"X-Request-Id": "trace-123"})
    assert response.headers["X-Request-Id"] == "trace-123"


def test_health_replaces_unsafe_request_id(client):
    response = client.get("/api/health", headers={"X-Request-Id": "bad value!"})
    echoed = response.headers["X-Request-Id"]
    assert echoed != "bad value!"
    assert len(echoed) == 32


def test_session_exposes_csrf_only(client):
    response = client.get("/api/session")

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["csrfToken"], str) and len(body["csrfToken"]) >= 20
    assert body["mode"] == "live"
    assert body["defaultBatchSize"] == 4
    # 没有配置的服务状态时不应返回任何 Key 字段
    assert not any("key" in name.lower() and name != "csrfToken" for name in body)


def test_unknown_api_returns_json_404(client):
    response = client.get("/api/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
