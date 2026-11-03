"""Which dashboard routes demand the write token, and which stay open.

A DELETE that 401s reads as a broken API rather than a bad token, so the UI
needs a way to prove the token before anything destructive is clicked.
"""

import pytest


@pytest.fixture
def client(isolated_store, tmp_path, monkeypatch):
    """A client bound to a throwaway database and throwaway credentials.

    These tests create and delete categories, so they must not be able to
    leave residue in the operator's real config. They also assert the
    no-password model, which means they must not see a real dashboard
    password either — otherwise setting one breaks the suite.
    """
    import auth
    import dashboard
    import settings_store as store

    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "dashboard_auth.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "dashboard_secret")
    dashboard._LOGIN_ATTEMPTS.clear()
    store.init_db()
    dashboard.app.config.update(TESTING=True)
    return dashboard.app.test_client()


@pytest.fixture
def token():
    import dashboard

    return dashboard.DASHBOARD_TOKEN


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── The token probe ─────────────────────────────────────────────────────────


def test_auth_check_accepts_the_real_token(client, token):
    assert client.get("/api/auth/check", headers=_auth(token)).status_code == 200


def test_auth_check_rejects_a_wrong_token(client):
    assert client.get("/api/auth/check", headers=_auth("nonsense")).status_code == 401


def test_auth_check_rejects_a_missing_token(client):
    """This is the one GET that must not be open, or it proves nothing."""
    assert client.get("/api/auth/check").status_code == 401


# ── Reads stay open on localhost ────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    ["/api/health", "/api/settings", "/api/sources", "/api/issues", "/api/pools"],
)
def test_reads_do_not_need_a_token(client, path):
    assert client.get(path).status_code == 200


# ── Writes always need one ──────────────────────────────────────────────────


def test_delete_category_without_a_token_is_refused(client):
    assert client.delete("/api/categories/99999").status_code == 401


def test_delete_category_with_a_token_is_allowed(client, token):
    """The reported 401 was the token, not the route: with one it works."""
    made = client.post(
        "/api/categories", json={"name": "ZZ-Auth-Probe"}, headers=_auth(token)
    )
    assert made.status_code == 201
    cat_id = made.get_json()["id"]

    assert client.delete(f"/api/categories/{cat_id}", headers=_auth(token)).status_code == 200

    names = {c["name"] for c in client.get("/api/sources").get_json()["categories"]}
    assert "ZZ-Auth-Probe" not in names


@pytest.mark.parametrize(
    "method,path",
    [
        ("put", "/api/settings"),
        ("post", "/api/categories"),
        ("put", "/api/categories/1"),
        ("delete", "/api/categories/1"),
        ("post", "/api/feeds"),
        ("put", "/api/feeds/1"),
        ("delete", "/api/feeds/1"),
        ("put", "/api/issues/1/articles"),
        ("post", "/api/issues/1/rebuild"),
        ("delete", "/api/issues/1"),
        ("put", "/api/pools/1/picks"),
        ("post", "/api/pools/1/build"),
        ("post", "/api/pools/refresh"),
        ("delete", "/api/pools/1"),
    ],
)
def test_every_write_route_requires_a_token(client, method, path):
    assert getattr(client, method)(path, json={}).status_code == 401


# ── The field itself ────────────────────────────────────────────────────────


def test_token_field_is_not_a_password_input():
    """A password input invites autofill, which silently overwrites the token."""
    import pathlib

    html = (
        pathlib.Path(__file__).parent.parent / "dashboard_static" / "index.html"
    ).read_text(encoding="utf-8")
    field = html[html.index('id="dashboard-token"') - 40 :][:400]
    assert 'type="text"' in field
    assert 'autocomplete="off"' in field


def test_the_hidden_attribute_beats_the_stylesheet():
    """`gate.hidden = true` must actually hide the login overlay.

    `.gate` sets `display: grid`, and an author rule outranks the UA
    stylesheet's `[hidden] { display: none }`. Without an explicit override
    the gate stayed pinned over the dashboard after a successful login and
    ate every click, which read as a broken login rather than broken CSS.
    The same applied to `.token-field`, which inherits `display: grid` from
    `.field`.
    """
    import pathlib
    import re

    static = pathlib.Path(__file__).parent.parent / "dashboard_static"
    css = (static / "style.css").read_text(encoding="utf-8")
    # Comments quote the very selector under test, so drop them first.
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    js = (static / "app.js").read_text(encoding="utf-8")

    rule = re.search(r"\[hidden\]\s*\{([^}]*)\}", css)
    assert rule, "no [hidden] rule: JS toggles would be overridden"
    body = rule.group(1)
    assert "display" in body and "none" in body and "!important" in body, body

    # And the JS must still be toggling the attribute, not a class.
    assert ".hidden =" in js
