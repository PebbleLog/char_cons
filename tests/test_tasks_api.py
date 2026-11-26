from __future__ import annotations

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import make_image, task_payload


@pytest.fixture
def csrf(client):
    token = client.get("/api/session").json()["csrfToken"]
    return {"X-CSRF-Token": token}


def _create(client, csrf, **overrides):
    response = client.post("/api/tasks", json=task_payload(**overrides), headers=csrf)
    assert response.status_code == 201, response.text
    return response.json()


def _upload(client, csrf, task_id, files):
    response = client.post(
        f"/api/tasks/{task_id}/shots",
        files=[("files", (name, data, "image/png")) for name, data in files],
        headers=csrf,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_create_list_detail(client, csrf):
    task = _create(client, csrf)

    assert task["status"] == "idle"
    assert task["characterName"] == "阿岚"
    assert task["validation"]["ready"] is False
    assert "镜头" in task["validation"]["missing"]

    listing = client.get("/api/tasks").json()
    assert listing["total"] == 1
    row = listing["items"][0]
    assert row["id"] == task["id"]
    assert row["shotsCount"] == 0
    assert row["thumbnailUrl"] is None

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["profileRaw"].startswith("阿岚")
    assert detail["shots"] == []


def test_create_validation_errors(client, csrf):
    no_token = client.post("/api/tasks", json=task_payload())
    assert no_token.status_code == 403

    empty_profile = client.post(
        "/api/tasks",
        json=task_payload(profileRaw="   "),
        headers=csrf,
    )
    assert empty_profile.status_code == 422
    assert empty_profile.json()["error"]["code"] == "invalid_request"

    too_long = client.post(
        "/api/tasks",
        json=task_payload(profileRaw="阿" * 501),
        headers=csrf,
    )
    assert too_long.status_code == 422


def test_upload_shots_and_images(client, csrf, settings):
    task = _create(client, csrf)
    result = _upload(
        client,
        csrf,
        task["id"],
        [
            ("shot1.png", make_image(base=(210, 195, 170))),
            ("shot2.png", make_image(base=(150, 160, 180))),
            ("shot3.png", make_image(base=(220, 210, 200))),
        ],
    )

    assert result["errors"] == []
    assert [shot["shotCode"] for shot in result["shots"]] == ["S1", "S2", "S3"]

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["validation"]["ready"] is True
    assert len(detail["shots"]) == 3
    assert detail["shots"][0]["width"] == 900
    assert detail["shots"][0]["height"] == 1200

    first = detail["shots"][0]
    original = client.get(first["imageUrl"])
    assert original.status_code == 200
    assert original.headers["content-type"].startswith("image/")
    assert original.content.startswith(b"\x89PNG")

    analysis = client.get(first["analysisUrl"])
    assert analysis.status_code == 200
    assert analysis.content.startswith(b"\xff\xd8")  # JPEG

    thumb = client.get(first["thumbUrl"])
    assert thumb.status_code == 200

    files = list((settings.uploads_dir / task["id"]).rglob("*"))
    assert len([p for p in files if p.is_file()]) >= 9

    dup = _upload(client, csrf, task["id"], [("copy.png", original.content)])
    assert dup["duplicates"][0]["duplicateOf"] == "S1"


def test_upload_isolates_invalid_files(client, csrf):
    task = _create(client, csrf)
    good = make_image()
    result = _upload(
        client,
        csrf,
        task["id"],
        [("ok.png", good), ("broken.png", b"not-an-image")],
    )

    assert len(result["shots"]) == 1
    assert len(result["errors"]) == 1
    assert result["errors"][0]["filename"] == "broken.png"
    assert result["errors"][0]["code"] == "unsupported_file"

    detail = client.get(f"/api/tasks/{task['id']}").json()
    assert detail["shots"][0]["shotCode"] == "S1"


def test_reorder_note_and_delete_shot(client, csrf):
    task = _create(client, csrf)
    uploaded = _upload(
        client,
        csrf,
        task["id"],
        [
            ("a.png", make_image(base=(200, 190, 170))),
            ("b.png", make_image(base=(160, 170, 190))),
            ("c.png", make_image(base=(210, 200, 210))),
        ],
    )
    shots = uploaded["shots"]
    by_name = {shot["originalFilename"]: shot for shot in shots}

    response = client.post(
        f"/api/tasks/{task['id']}/shots/reorder",
        json={"shotIds": [by_name["c.png"]["id"], by_name["a.png"]["id"], by_name["b.png"]["id"]]},
        headers=csrf,
    )
    assert response.status_code == 200
    ordered = [(shot["shotCode"], shot["originalFilename"]) for shot in response.json()["shots"]]
    assert ordered == [("S1", "c.png"), ("S2", "a.png"), ("S3", "b.png")]

    note = client.patch(
        f"/api/tasks/{task['id']}/shots/{by_name['a.png']['id']}",
        json={"note": "侧身半身，冷光"},
        headers=csrf,
    )
    assert note.status_code == 200
    assert note.json()["shot"]["note"] == "侧身半身，冷光"

    deleted = client.delete(
        f"/api/tasks/{task['id']}/shots/{by_name['c.png']['id']}", headers=csrf
    )
    assert deleted.status_code == 200
    codes = [(shot["shotCode"], shot["originalFilename"]) for shot in deleted.json()["shots"]]
    assert codes == [("S1", "a.png"), ("S2", "b.png")]


def test_task_update_and_delete(client, csrf, settings, tmp_path):
    task = _create(client, csrf)
    _upload(client, csrf, task["id"], [("a.png", make_image())])

    updated = client.patch(
        f"/api/tasks/{task['id']}",
        json={"name": "阿岚 · 改名", "defaultBatchSize": 2},
        headers=csrf,
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "阿岚 · 改名"
    assert updated.json()["defaultBatchSize"] == 2

    task_dir = settings.uploads_dir / task["id"]
    assert task_dir.is_dir()

    removed = client.delete(f"/api/tasks/{task['id']}", headers=csrf)
    assert removed.status_code == 204
    assert client.get(f"/api/tasks/{task['id']}").status_code == 404
    assert not task_dir.exists()


def test_status_filter_and_search(client, csrf):
    _create(client, csrf, name="阿岚 · 第一幕", characterName="阿岚")
    _create(client, csrf, name="其他角色", characterName="林夏")

    idle = client.get("/api/tasks?status=idle").json()
    assert idle["total"] == 2

    completed = client.get("/api/tasks?status=completed").json()
    assert completed["total"] == 0

    searched = client.get("/api/tasks?q=林夏").json()
    assert searched["total"] == 1
    assert searched["items"][0]["characterName"] == "林夏"

    invalid = client.get("/api/tasks?status=nope")
    assert invalid.status_code == 400


def test_cross_task_shot_access_is_404(client, csrf):
    task_a = _create(client, csrf)
    task_b = _create(client, csrf)
    uploaded = _upload(client, csrf, task_a["id"], [("a.png", make_image())])
    shot = uploaded["shots"][0]

    response = client.get(f"/api/tasks/{task_b['id']}/shots/{shot['id']}/image")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_persistence_across_restart(settings):
    app1 = create_app(settings, configure_logs=False)
    with TestClient(app1) as client:
        token = client.get("/api/session").json()["csrfToken"]
        headers = {"X-CSRF-Token": token}
        task = client.post("/api/tasks", json=task_payload(), headers=headers).json()
        client.post(
            f"/api/tasks/{task['id']}/shots",
            files=[("files", ("a.png", make_image(), "image/png"))],
            headers=headers,
        )

    # 模拟重启：同一数据目录的新应用实例
    app2 = create_app(settings, configure_logs=False)
    with TestClient(app2) as client:
        listing = client.get("/api/tasks").json()
        assert listing["total"] == 1
        row = listing["items"][0]
        assert row["shotsCount"] == 1
        assert row["thumbnailUrl"] is not None
        assert "&v=" in row["thumbnailUrl"]
        detail = client.get(f"/api/tasks/{row['id']}").json()
        assert detail["shots"][0]["shotCode"] == "S1"
        assert "&v=" in detail["shots"][0]["thumbUrl"]
        assert "&v=" in detail["shots"][0]["currentUrl"]
        assert client.get(detail["shots"][0]["thumbUrl"]).status_code == 200


def test_archive_summary(client, csrf, settings):
    empty = client.get("/api/archive/summary").json()
    assert empty["liveTasks"] == 0
    assert empty["storageLocation"] == "local"

    task = _create(client, csrf)
    _upload(client, csrf, task["id"], [("a.png", make_image())])

    summary = client.get("/api/archive/summary").json()
    assert summary["liveTasks"] == 1
    assert summary["reports"] == 0
    assert summary["storageBytes"] > 0
    assert summary["earliest"]

    with sqlite3.connect(settings.db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM shots").fetchone()[0]
    assert count == 1
