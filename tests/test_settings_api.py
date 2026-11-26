from __future__ import annotations

import json

import pytest

from app.providers.errors import ProviderError
from app.providers.mock import MockVisionProvider
from app.services import settings_service
from tests.test_report import _create_task


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


@pytest.fixture
def no_keys(monkeypatch):
    captured = {}

    def fake_status(service):
        return {"hasKey": False, "source": "none"}

    def fake_set(service, key):
        captured.setdefault("saved", []).append((service, key))

    def fake_delete(service):
        captured.setdefault("deleted", []).append(service)

    monkeypatch.setattr(settings_service, "key_status", fake_status)
    monkeypatch.setattr(settings_service, "set_api_key", fake_set)
    monkeypatch.setattr(settings_service, "delete_api_key", fake_delete)
    return captured


def test_settings_view_has_no_secret_or_path(client, no_keys, settings):
    response = client.get("/api/settings")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["services"]["analysis"]["provider"] == "mock"
    assert data["services"]["analysis"]["configured"] is True
    assert data["services"]["analysis"]["state"] == "ready"
    assert data["services"]["analysis"]["keyMasked"] == "未配置"
    assert data["services"]["generation"]["capabilities"]["singleImagePerRequest"] is True
    assert data["services"]["generation"]["capabilities"]["negativePrompt"] is False
    assert data["security"]["keyInBrowserStorage"] is False
    assert data["privacyAcknowledged"] is False
    serialized = json.dumps(data, ensure_ascii=False)
    assert '"apiKey":' not in serialized
    assert "sk-" not in serialized
    assert str(settings.home_dir) not in serialized
    assert "char_cons.db" not in serialized


def test_update_general_limits_and_privacy(client, csrf, no_keys, settings):
    response = client.put(
        "/api/settings",
        json={
            "defaultBatchSize": 2,
            "uploadMaxMb": 30,
            "generationSize": "2K",
            "privacyAcknowledged": True,
        },
        headers=csrf,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["limits"]["defaultBatchSize"] == 2
    assert data["limits"]["uploadMaxMb"] == 30
    assert data["limits"]["generationSize"] == "2K"
    assert data["privacyAcknowledged"] is True
    assert settings.default_batch_size == 2
    assert settings.upload_max_mb == 30
    assert settings.generation_size == "2K"
    session = client.get("/api/session").json()
    assert session["defaultBatchSize"] == 2
    # 再次读取仍持久化
    assert client.get("/api/settings").json()["privacyAcknowledged"] is True


def test_update_service_stores_key_backend_only(client, csrf, no_keys, caplog):
    response = client.put(
        "/api/settings/services/analysis",
        json={
            "provider": "doubao",
            "model": "vision-test-model",
            "baseUrl": "https://ark.example/api/v3",
            "apiKey": "sk-secret-value",
        },
        headers=csrf,
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert "sk-secret-value" not in body
    assert no_keys["saved"] == [("analysis", "sk-secret-value")]
    assert "sk-secret-value" not in caplog.text
    data = response.json()
    assert data["services"]["analysis"]["model"] == "vision-test-model"
    assert data["services"]["analysis"]["baseUrl"] == "https://ark.example/api/v3"

    deleted = client.delete("/api/settings/keys/analysis", headers=csrf)
    assert deleted.status_code == 200
    assert no_keys["deleted"] == ["analysis"]
    assert "sk-secret-value" not in deleted.text


def test_service_test_mock_success_and_failure(client, csrf, no_keys, app):
    ok = client.post("/api/settings/test", json={"service": "analysis"}, headers=csrf)
    assert ok.status_code == 200, ok.text
    result = ok.json()["result"]
    assert result["ok"] is True
    assert result["mock"] is True
    assert "连接成功" in result["message"]
    view = client.get("/api/settings").json()
    assert view["services"]["analysis"]["state"] == "connected"

    gen = client.post("/api/settings/test", json={"service": "generation"}, headers=csrf)
    assert gen.status_code == 200
    assert gen.json()["result"]["ok"] is True
    assert gen.json()["settings"]["services"]["generation"]["state"] == "connected"

    class FailingProvider(MockVisionProvider):
        async def test_connection(self):
            raise ProviderError("auth_failed", "鉴权失败：sk-leaked123 无效，请检查 Key。")

    app.state.vision_provider_factory = lambda _settings: FailingProvider()
    failed = client.post("/api/settings/test", json={"service": "analysis"}, headers=csrf)
    assert failed.status_code == 200
    result = failed.json()["result"]
    assert result["ok"] is False
    assert result["code"] == "auth_failed"
    assert "sk-leaked123" not in failed.text
    assert "***" in result["message"]
    assert client.get("/api/settings").json()["services"]["analysis"]["state"] == "failed"


def test_storage_summary_and_clear_data(client, csrf, no_keys, settings):
    task = _create_task(client, csrf)
    client.put(
        "/api/settings",
        json={"privacyAcknowledged": True},
        headers=csrf,
    )
    storage = client.get("/api/settings/storage").json()
    assert storage["liveTasks"] == 1
    assert storage["storageBytes"] > 0
    assert storage["storageLocation"] == "local"
    assert str(settings.home_dir) not in json.dumps(storage, ensure_ascii=False)

    rejected = client.post(
        "/api/settings/clear-data", json={"confirm": False}, headers=csrf
    )
    assert rejected.status_code == 400

    cleared = client.post(
        "/api/settings/clear-data", json={"confirm": True}, headers=csrf
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["liveTasks"] == 0
    assert cleared.json()["candidates"] == 0
    assert client.get("/api/tasks").json()["total"] == 0
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    # 设置与隐私确认不属于任务数据，应保留
    assert client.get("/api/settings").json()["privacyAcknowledged"] is True
    assert settings.uploads_dir.is_dir()
    assert settings.generated_dir.is_dir()


def test_settings_writes_require_csrf(client):
    response = client.put("/api/settings", json={"defaultBatchSize": 4})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_keys_are_separate_and_ark_generic_not_reused(monkeypatch):
    from app.core import keyring_store

    monkeypatch.setattr(
        keyring_store.keyring, "get_password", lambda *_args, **_kwargs: None
    )
    for name in (
        "CHAR_CONS_ANALYSIS_API_KEY",
        "CHAR_CONS_GENERATION_API_KEY",
        "ARK_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    monkeypatch.setenv("ARK_API_KEY", "sk-shared")
    assert keyring_store.key_status("analysis")["hasKey"] is False
    assert keyring_store.key_status("generation")["hasKey"] is False

    monkeypatch.setenv("CHAR_CONS_ANALYSIS_API_KEY", "sk-analysis")
    assert keyring_store.key_status("analysis") == {"hasKey": True, "source": "env"}
    assert keyring_store.key_status("generation")["hasKey"] is False
    assert keyring_store.get_api_key("generation") is None


def test_clear_data_rejects_active_task(client, csrf, no_keys, settings):
    import sqlite3

    task = _create_task(client, csrf)
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("UPDATE tasks SET status = 'running' WHERE id = ?", (task["id"],))
        conn.commit()
    response = client.post(
        "/api/settings/clear-data", json={"confirm": True}, headers=csrf
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    with sqlite3.connect(settings.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM tasks WHERE id = ?", (task["id"],)).fetchone()[0]
    assert count == 1


def test_service_url_rejects_embedded_credentials(client, csrf, no_keys):
    response = client.put(
        "/api/settings/services/analysis",
        json={"provider": "doubao", "model": "m", "baseUrl": "https://user:pass@ark.example/api/v3"},
        headers=csrf,
    )
    assert response.status_code == 400
    assert "用户名或密码" in response.json()["error"]["message"]
