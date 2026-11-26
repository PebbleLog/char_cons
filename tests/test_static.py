from __future__ import annotations


def test_frontend_index_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Character Consistency Studio" in response.text


def test_static_assets_served(client):
    css = client.get("/styles.css")
    assert css.status_code == 200
    assert "text/css" in css.headers.get("content-type", "")

    image = client.get("/assets/shot-1.jpg")
    assert image.status_code == 200
    assert image.headers.get("content-type", "").startswith("image/")

    main_js = client.get("/js/main.js")
    assert main_js.status_code == 200
    assert "initSession" in main_js.text
    api_js = client.get("/js/core/api.js")
    assert api_js.status_code == 200
    assert "/api/tasks" in api_js.text


def test_static_traversal_rejected(client):
    response = client.get("/assets/..%2f..%2fapp%2fmain.py")
    assert response.status_code in (403, 404)
    assert "create_app" not in response.text
