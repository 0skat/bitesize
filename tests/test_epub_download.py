"""Downloading a stored issue's EPUB from the dashboard.

On a Linux host there is no iCloud Books library, so the phone fetches the
file instead. The file is looked up by name inside OUTPUT_DIR: the stored path
was written on whichever machine built the issue, and must never be trusted
as a location on this one.
"""

from pathlib import Path

import pytest

import issues


def _sections():
    art = {
        "title": "t1", "url": "http://example.test/t1", "source": "S",
        "summary": "One. Two.", "content": "body " * 40, "published": "09:00",
        "tipo": "artigo-completo", "temas": ["tecnologia"],
        "relevance": 90, "relevance_source": "ai",
    }
    return {"Tech": [art]}


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    import config

    out = tmp_path / "output"
    out.mkdir()
    monkeypatch.setattr(config, "OUTPUT_DIR", out)
    return out


@pytest.fixture
def client(isolated_store, out_dir, tmp_path, monkeypatch):
    import auth
    import dashboard
    import settings_store as store

    monkeypatch.setattr(auth, "AUTH_FILE", tmp_path / "dashboard_auth.json")
    monkeypatch.setattr(auth, "SECRET_FILE", tmp_path / "dashboard_secret")
    dashboard._LOGIN_ATTEMPTS.clear()
    store.init_db()
    dashboard.app.config.update(TESTING=True)
    return dashboard.app.test_client()


def _issue_on_another_machine(out_dir: Path, name: str = "News Digest - November 05 2026 0807.epub") -> int:
    """An issue recorded on the Mac, its file copied here by name."""
    (out_dir / name).write_bytes(b"PK\x03\x04 fake epub")
    mac_path = Path("/Users/someone/dev/bitesize/output") / name
    return issues.record_issue(mac_path, _sections())


def test_download_finds_the_file_by_name(client, out_dir):
    iid = _issue_on_another_machine(out_dir)
    r = client.get(f"/api/issues/{iid}/epub")
    assert r.status_code == 200
    assert r.mimetype == "application/epub+zip"
    assert r.data.startswith(b"PK")
    assert "attachment" in r.headers["Content-Disposition"]
    assert "November 05 2026" in r.headers["Content-Disposition"]


def test_latest_is_the_newest_issue(client, out_dir):
    _issue_on_another_machine(out_dir, "old.epub")
    newest = _issue_on_another_machine(out_dir, "new.epub")
    r = client.get("/api/issues/latest/epub")
    assert r.status_code == 200
    assert "new.epub" in r.headers["Content-Disposition"]
    assert newest == issues.list_issues(1)[0]["id"]


def test_pruned_file_is_404(client, out_dir):
    iid = _issue_on_another_machine(out_dir)
    for f in out_dir.iterdir():
        f.unlink()
    assert client.get(f"/api/issues/{iid}/epub").status_code == 404


def test_unknown_issue_is_404(client):
    assert client.get("/api/issues/999/epub").status_code == 404
    assert client.get("/api/issues/latest/epub").status_code == 404


def test_stored_path_cannot_point_outside_output(client, out_dir, tmp_path):
    secret = tmp_path / "secret.epub"
    secret.write_bytes(b"not yours")
    iid = issues.record_issue(secret, _sections())
    # Same name absent from OUTPUT_DIR: the stored absolute path is ignored.
    assert client.get(f"/api/issues/{iid}/epub").status_code == 404

    iid = issues.record_issue(Path("../../etc/passwd"), _sections())
    assert client.get(f"/api/issues/{iid}/epub").status_code == 404


def test_download_needs_login_once_a_password_is_set(client, out_dir):
    import auth

    iid = _issue_on_another_machine(out_dir)
    auth.set_password("a long enough password")
    assert client.get(f"/api/issues/{iid}/epub").status_code == 401
