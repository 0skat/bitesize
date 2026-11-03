"""Dashboard password auth: hashing, and the two access models.

Without a password the dashboard trusts its loopback bind: reads are open and
writes need the bearer token. With one set it fails closed on every API route,
because a tunnel (`tailscale serve`) proxies to loopback and makes a remote
request indistinguishable from a local one.
"""

import json
import os
import stat

import pytest

import auth


@pytest.fixture
def auth_files(tmp_path, monkeypatch):
    """Point auth at throwaway files so a real password is never touched."""
    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "dashboard_auth.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "dashboard_secret")
    return tmp_path


# ── Hashing ─────────────────────────────────────────────────────────────────


def test_password_round_trip(auth_files):
    assert auth.password_is_set() is False
    auth.set_password("correct horse battery")
    assert auth.password_is_set() is True
    assert auth.verify_password("correct horse battery") is True


def test_wrong_and_empty_passwords_are_refused(auth_files):
    auth.set_password("correct horse battery")
    assert auth.verify_password("Correct horse battery") is False
    assert auth.verify_password("") is False
    assert auth.verify_password("x") is False


def test_short_passwords_are_rejected(auth_files):
    with pytest.raises(ValueError):
        auth.set_password("short")
    assert auth.password_is_set() is False


def test_the_password_itself_is_never_stored(auth_files):
    secret = "correct horse battery"
    auth.set_password(secret)
    raw = auth.AUTH_FILE.read_text(encoding="utf-8")
    assert secret not in raw
    stored = json.loads(raw)
    assert stored["algo"] == "scrypt"
    assert stored["salt"] and stored["hash"]


def test_the_same_password_hashes_differently_each_time(auth_files):
    """A per-password salt, so identical passwords do not share a hash."""
    auth.set_password("correct horse battery")
    first = json.loads(auth.AUTH_FILE.read_text())["hash"]
    auth.set_password("correct horse battery")
    second = json.loads(auth.AUTH_FILE.read_text())["hash"]
    assert first != second
    assert auth.verify_password("correct horse battery") is True


def test_credential_files_are_owner_only(auth_files):
    auth.set_password("correct horse battery")
    auth.session_secret()
    for path in (auth.AUTH_FILE, auth.SECRET_FILE):
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, path


def test_verify_survives_a_corrupt_auth_file(auth_files):
    auth.AUTH_FILE.write_text("not json at all", encoding="utf-8")
    assert auth.password_is_set() is False
    assert auth.verify_password("anything") is False


def test_clear_password_reports_whether_there_was_one(auth_files):
    assert auth.clear_password() is False
    auth.set_password("correct horse battery")
    assert auth.clear_password() is True
    assert auth.password_is_set() is False


def test_session_secret_is_stable_and_long_enough(auth_files):
    first = auth.session_secret()
    assert len(first) == 32
    assert auth.session_secret() == first


def test_session_secret_survives_a_corrupt_file(auth_files):
    auth.SECRET_FILE.write_text("not hex", encoding="utf-8")
    assert len(auth.session_secret()) == 32


# ── The two access models ───────────────────────────────────────────────────


@pytest.fixture
def client(isolated_store, auth_files, monkeypatch):
    import dashboard
    import settings_store as store

    store.init_db()
    monkeypatch.setattr(dashboard.auth, "AUTH_FILE", auth_files / "dashboard_auth.json")
    monkeypatch.setattr(dashboard.auth, "SECRET_FILE", auth_files / "dashboard_secret")
    dashboard._LOGIN_ATTEMPTS.clear()
    dashboard.app.config.update(TESTING=True)
    return dashboard.app.test_client()


@pytest.fixture
def token():
    import dashboard

    return dashboard.DASHBOARD_TOKEN


def test_without_a_password_reads_stay_open(client):
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/pools").status_code == 200


def test_without_a_password_writes_need_the_token(client, token):
    assert client.delete("/api/categories/999").status_code == 401
    assert (
        client.delete(
            "/api/categories/999", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 200
    )


def test_with_a_password_reads_are_closed_too(client):
    """The loopback bind proves nothing behind a proxy, so fail closed."""
    auth.set_password("correct horse battery")
    assert client.get("/api/settings").status_code == 401
    assert client.get("/api/pools").status_code == 401
    assert client.get("/api/issues").status_code == 401


def test_the_login_page_itself_stays_reachable(client):
    """Closing everything would lock the operator out of the login form."""
    auth.set_password("correct horse battery")
    assert client.get("/").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/auth/state").status_code == 200


def test_auth_state_tells_the_ui_which_model_is_active(client):
    assert client.get("/api/auth/state").get_json()["password_set"] is False
    auth.set_password("correct horse battery")
    body = client.get("/api/auth/state").get_json()
    assert body["password_set"] is True
    assert body["logged_in"] is False


def test_login_then_read(client):
    auth.set_password("correct horse battery")
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401
    assert (
        client.post("/api/login", json={"password": "correct horse battery"}).status_code
        == 200
    )
    assert client.get("/api/settings").status_code == 200
    assert client.get("/api/auth/state").get_json()["logged_in"] is True


def test_logout_closes_the_session(client):
    auth.set_password("correct horse battery")
    client.post("/api/login", json={"password": "correct horse battery"})
    assert client.get("/api/settings").status_code == 200
    client.post("/api/logout")
    assert client.get("/api/settings").status_code == 401


def test_the_bearer_token_still_works_with_a_password_set(client, token):
    """Scripts and curl must not need a browser session."""
    auth.set_password("correct horse battery")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/settings", headers=headers).status_code == 200
    assert client.delete("/api/categories/999", headers=headers).status_code == 200


def test_login_is_refused_when_no_password_is_set(client):
    assert client.post("/api/login", json={"password": "anything"}).status_code == 400


def test_repeated_wrong_passwords_are_throttled(client):
    import dashboard

    auth.set_password("correct horse battery")
    for _ in range(dashboard._LOGIN_MAX_ATTEMPTS):
        assert client.post("/api/login", json={"password": "nope"}).status_code == 401
    # Further attempts are refused outright, including a correct one.
    assert client.post("/api/login", json={"password": "nope"}).status_code == 429
    assert (
        client.post("/api/login", json={"password": "correct horse battery"}).status_code
        == 429
    )


def test_a_successful_login_clears_the_attempt_count(client):
    import dashboard

    auth.set_password("correct horse battery")
    for _ in range(dashboard._LOGIN_MAX_ATTEMPTS - 1):
        client.post("/api/login", json={"password": "nope"})
    assert (
        client.post("/api/login", json={"password": "correct horse battery"}).status_code
        == 200
    )
    client.post("/api/logout")
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401


def test_the_session_cookie_is_http_only(client):
    auth.set_password("correct horse battery")
    res = client.post("/api/login", json={"password": "correct horse battery"})
    cookie = res.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


# ── Where the dashboard is allowed to listen ────────────────────────────────


def test_default_bind_is_loopback(client, monkeypatch):
    import dashboard

    host, notes = dashboard.resolve_bind()
    assert host == "127.0.0.1"
    assert notes == []


def test_a_tailnet_bind_is_refused_without_a_password(client, monkeypatch):
    """The bind was the only thing keeping reads private — refuse, don't warn."""
    import dashboard
    import settings_store as store

    store.set_setting("dashboard_host", "tailscale")
    monkeypatch.setattr(dashboard.netbind, "tailscale_address", lambda: "100.64.1.2")

    host, notes = dashboard.resolve_bind()
    assert host == "127.0.0.1", "must not expose reads without a password"
    assert any("REFUSING" in n for n in notes)


def test_a_tailnet_bind_is_allowed_once_a_password_is_set(client, monkeypatch):
    import dashboard
    import settings_store as store

    store.set_setting("dashboard_host", "tailscale")
    monkeypatch.setattr(dashboard.netbind, "tailscale_address", lambda: "100.64.1.2")
    auth.set_password("correct horse battery")

    host, notes = dashboard.resolve_bind()
    assert host == "100.64.1.2"
    assert not any("REFUSING" in n for n in notes)


def test_bind_falls_back_when_tailscale_is_not_connected(client, monkeypatch):
    import dashboard
    import settings_store as store

    store.set_setting("dashboard_host", "tailscale")
    monkeypatch.setattr(dashboard.netbind, "tailscale_address", lambda: None)
    auth.set_password("correct horse battery")

    host, notes = dashboard.resolve_bind()
    assert host == "127.0.0.1"
    assert any("no tailnet address" in n for n in notes)


def test_binding_every_interface_is_called_out(client, monkeypatch):
    import dashboard
    import settings_store as store

    store.set_setting("dashboard_host", "0.0.0.0")
    auth.set_password("correct horse battery")

    host, notes = dashboard.resolve_bind()
    assert host == "0.0.0.0"
    assert any("every interface" in n for n in notes)


def test_a_nonsense_host_falls_back_rather_than_crashing(client, monkeypatch):
    import dashboard
    import settings_store as store

    store.set_setting("dashboard_host", "not-a-real-host")
    auth.set_password("correct horse battery")

    host, notes = dashboard.resolve_bind()
    assert host == "127.0.0.1"
    assert notes


def test_tailnet_detection_recognises_the_cgnat_range():
    import netbind

    assert netbind.is_loopback("127.0.0.1") is True
    assert netbind.is_loopback("localhost") is True
    assert netbind.is_loopback("100.108.223.67") is False
