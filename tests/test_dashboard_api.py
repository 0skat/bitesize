import pytest

import dashboard
import settings_store as store


@pytest.fixture
def client(tmp_path, monkeypatch):
    db = tmp_path / "dash.db"
    token_file = tmp_path / "dashboard.token"
    monkeypatch.setattr(store, "DB_PATH", db)
    monkeypatch.setattr(store, "SOURCES_FILE", tmp_path / "sources.json")
    monkeypatch.setattr(store, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setattr(dashboard, "TOKEN_FILE", token_file)
    monkeypatch.setattr(dashboard, "DASHBOARD_TOKEN", "test-token")
    store.init_db()
    dashboard.app.config["TESTING"] = True
    return dashboard.app.test_client()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_get_settings(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.get_json()
    assert "ai" in data
    assert data["ai"]["ai_backend"] in ("gemini", "ollama", "antigravity")


def test_put_settings(client):
    r = client.put(
        "/api/settings",
        json={"ai_backend": "ollama"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    assert store.load_settings().ai_backend == "ollama"


def test_sources_crud(client):
    auth = {"Authorization": "Bearer test-token"}
    r = client.post("/api/categories", json={"name": "Tech"}, headers=auth)
    assert r.status_code == 201
    cat_id = r.get_json()["id"]

    r = client.post(
        "/api/feeds",
        json={"category_id": cat_id, "name": "HN", "url": "https://hnrss.org/frontpage"},
        headers=auth,
    )
    assert r.status_code == 201
    feed_id = r.get_json()["id"]

    r = client.get("/api/sources")
    cats = r.get_json()["categories"]
    assert cats[0]["feeds"][0]["name"] == "HN"

    r = client.put("/api/feeds/" + str(feed_id), json={"enabled": False}, headers=auth)
    assert r.status_code == 200

    r = client.delete("/api/feeds/" + str(feed_id), headers=auth)
    assert r.status_code == 200


def test_kindle_test_missing_settings(client, monkeypatch):
    monkeypatch.setattr(
        dashboard,
        "send_test_email",
        lambda s: (False, "Missing settings: kindle_email"),
    )
    r = client.post("/api/kindle/test", headers={"Authorization": "Bearer test-token"})
    assert r.status_code == 400
    assert r.get_json()["ok"] is False


def test_get_settings_masks_smtp_password(client):
    store.set_setting("smtp_password", "super-secret")
    r = client.get("/api/settings")
    assert r.get_json()["kindle"]["smtp_password"] == ""
    assert r.get_json()["kindle"]["smtp_password_set"] is True


def test_put_settings_requires_token(client):
    r = client.put("/api/settings", json={"ai_backend": "ollama"})
    assert r.status_code == 401
    r = client.put(
        "/api/settings",
        json={"ai_backend": "gemini"},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200


def test_resolve_dashboard_token_from_file(tmp_path, monkeypatch):
    token_file = tmp_path / "dashboard.token"
    token_file.write_text("file-token\n", encoding="utf-8")
    monkeypatch.delenv("DASHBOARD_TOKEN", raising=False)
    monkeypatch.setattr(dashboard, "TOKEN_FILE", token_file)
    assert dashboard._resolve_dashboard_token() == "file-token"


def test_put_settings_skips_blank_smtp_password(client):
    store.set_setting("smtp_password", "keep-me")
    r = client.put(
        "/api/settings",
        json={"smtp_password": ""},
        headers={"Authorization": "Bearer test-token"},
    )
    assert r.status_code == 200
    assert store.load_settings().smtp_password == "keep-me"
