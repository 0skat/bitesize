"""Local settings dashboard — Flask REST API + static HTML UI."""

from __future__ import annotations

import hmac
import os
import secrets
import time
from datetime import timedelta
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory, session

import auth
import issues as issue_store
import netbind
import pool as pool_store
import settings_store as store
from config import BASE_DIR, load_env, reload_settings
from kindle import send_test_email
from preview import build_source_preview
from epub_download import bp as epub_download_bp

load_env()

STATIC_DIR = Path(__file__).parent / "dashboard_static"
DEFAULT_HOST = "127.0.0.1"
PORT = 8765
TOKEN_FILE = BASE_DIR / "data" / "dashboard.token"


def _resolve_dashboard_token() -> str:
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    if token:
        return token
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    token = secrets.token_urlsafe(32)
    TOKEN_FILE.write_text(token + "\n", encoding="utf-8")
    print(f"Dashboard write token saved to {TOKEN_FILE}")
    return token


DASHBOARD_TOKEN = _resolve_dashboard_token()

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
app.register_blueprint(epub_download_bp)  # GET /api/issues/<id>/epub, /api/issues/latest/epub
app.secret_key = auth.session_secret()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
    # Off by default so logins work over plain http://127.0.0.1. Turn it on
    # when the dashboard is only ever reached over HTTPS.
    SESSION_COOKIE_SECURE=bool(store.load_settings().dashboard_cookie_secure),
)

# Routes that must answer before anyone is authenticated.
_OPEN_PATHS = frozenset({"/api/health", "/api/auth/state", "/api/login"})

# The one read that must prove credentials, so the UI can report a bad token
# or an expired session before anything destructive is clicked.
_AUTHENTICATED_READS = frozenset({"/api/auth/check"})

# Login attempts per source address, to blunt brute force over a tunnel.
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_ATTEMPTS = 10


def _login_throttled(addr: str) -> bool:
    now = time.monotonic()
    recent = [t for t in _LOGIN_ATTEMPTS.get(addr, []) if now - t < _LOGIN_WINDOW_SECONDS]
    _LOGIN_ATTEMPTS[addr] = recent
    return len(recent) >= _LOGIN_MAX_ATTEMPTS


def _record_login_attempt(addr: str) -> None:
    _LOGIN_ATTEMPTS.setdefault(addr, []).append(time.monotonic())


def _has_bearer_token() -> bool:
    header = request.headers.get("Authorization", "")
    expected = f"Bearer {DASHBOARD_TOKEN}"
    return hmac.compare_digest(header, expected)


def _is_logged_in() -> bool:
    return bool(session.get("authenticated"))


def _credentialed() -> bool:
    """A session cookie or the bearer token. Either is sufficient."""
    return _is_logged_in() or _has_bearer_token()


def _unauthorized(message: str = "Unauthorized"):
    return jsonify({"error": message, "login_required": auth.password_is_set()}), 401


@app.before_request
def check_auth():
    if request.method == "OPTIONS" or request.path in _OPEN_PATHS:
        return None

    # With a password set the dashboard is assumed reachable from elsewhere —
    # through a Tailscale tunnel, say — where the loopback bind proves nothing,
    # because the proxy makes every request look local. Reads are closed too.
    if auth.password_is_set():
        if request.path.startswith("/api/") and not _credentialed():
            return _unauthorized("Log in to use the dashboard.")
        return None

    # No password: the old model. Reads open on localhost, writes need a token.
    if request.path in _AUTHENTICATED_READS:
        return None if _credentialed() else _unauthorized()
    if request.path.startswith("/api/") and request.method != "GET":
        return None if _credentialed() else _unauthorized()
    return None


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify({"ok": True})


@app.get("/api/auth/state")
def auth_state():
    """What the UI needs to decide between a login form and a token field."""
    return jsonify(
        {
            "password_set": auth.password_is_set(),
            "logged_in": _is_logged_in(),
            "authenticated": _credentialed(),
        }
    )


@app.post("/api/login")
def login():
    if not auth.password_is_set():
        return jsonify({"error": "No dashboard password is set."}), 400

    addr = request.remote_addr or "unknown"
    if _login_throttled(addr):
        return jsonify(
            {"error": "Too many attempts. Wait a few minutes and try again."}
        ), 429

    data = request.get_json(silent=True) or {}
    if not auth.verify_password(str(data.get("password") or "")):
        _record_login_attempt(addr)
        return jsonify({"error": "Wrong password."}), 401

    session.clear()
    session["authenticated"] = True
    session.permanent = True
    _LOGIN_ATTEMPTS.pop(addr, None)
    return jsonify({"ok": True})


@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.get("/api/auth/check")
def auth_check():
    """Reached only with a valid token; check_auth rejects otherwise."""
    return jsonify({"ok": True})


@app.get("/api/settings")
def get_settings_api():
    return jsonify(store.settings_for_api())


@app.put("/api/settings")
def put_settings_api():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({"error": "Expected JSON object"}), 400
    try:
        store.update_settings(data)
        reload_settings()
    except KeyError as e:
        return jsonify({"error": str(e)}), 400
    return jsonify(store.settings_for_api())


@app.get("/api/sources")
def get_sources_api():
    return jsonify(store.load_sources_for_api())


@app.get("/api/preview")
def get_preview_api():
    max_headlines = request.args.get("max", default=5, type=int)
    max_headlines = max(1, min(int(max_headlines or 5), 12))
    return jsonify(
        build_source_preview(
            store.load_sources_for_api(),
            max_headlines=max_headlines,
        )
    )


@app.post("/api/categories")
def post_category():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    cat_id = store.add_category(name)
    return jsonify({"id": cat_id, "name": name}), 201


@app.put("/api/categories/<int:category_id>")
def put_category(category_id: int):
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    store.update_category(category_id, name)
    return jsonify({"id": category_id, "name": name})


@app.delete("/api/categories/<int:category_id>")
def delete_category(category_id: int):
    store.delete_category(category_id)
    return jsonify({"ok": True})


@app.post("/api/feeds")
def post_feed():
    data = request.get_json(silent=True) or {}
    category_id = data.get("category_id")
    name = (data.get("name") or "").strip()
    url = (data.get("url") or "").strip()
    if not category_id or not name or not url:
        return jsonify({"error": "category_id, name, and url are required"}), 400
    feed_id = store.add_feed(
        int(category_id),
        name,
        url,
        enabled=bool(data.get("enabled", True)),
    )
    return jsonify({"id": feed_id, "name": name, "url": url}), 201


@app.put("/api/feeds/<int:feed_id>")
def put_feed(feed_id: int):
    data = request.get_json(silent=True) or {}
    kwargs = {}
    if "name" in data:
        kwargs["name"] = str(data["name"]).strip()
    if "url" in data:
        kwargs["url"] = str(data["url"]).strip()
    if "enabled" in data:
        kwargs["enabled"] = bool(data["enabled"])
    store.update_feed(feed_id, **kwargs)
    return jsonify({"id": feed_id, **kwargs})


@app.delete("/api/feeds/<int:feed_id>")
def delete_feed(feed_id: int):
    store.delete_feed(feed_id)
    return jsonify({"ok": True})


@app.get("/api/issues")
def get_issues_api():
    limit = request.args.get("limit", default=20, type=int)
    limit = max(1, min(int(limit or 20), 100))
    return jsonify({"issues": issue_store.list_issues(limit)})


@app.get("/api/issues/<int:issue_id>")
def get_issue_api(issue_id: int):
    issue = issue_store.load_issue(issue_id)
    if issue is None:
        return jsonify({"error": f"No issue {issue_id}"}), 404
    return jsonify(issue)


@app.put("/api/issues/<int:issue_id>/articles")
def put_issue_articles_api(issue_id: int):
    """Exclude or restore several stored articles at once."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids must be a non-empty list"}), 400
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return jsonify({"error": "ids must be integers"}), 400
    if "excluded" not in data:
        return jsonify({"error": "excluded is required"}), 400

    changed = issue_store.set_excluded_many(ids, bool(data["excluded"]))
    issue = issue_store.load_issue(issue_id)
    if issue is None:
        return jsonify({"error": f"No issue {issue_id}"}), 404
    return jsonify({"changed": changed, "issue": issue})


@app.post("/api/issues/<int:issue_id>/rebuild")
def post_issue_rebuild_api(issue_id: int):
    """Rewrite the EPUB without the excluded articles. Costs no AI calls."""
    data = request.get_json(silent=True) or {}
    deliver = bool(data.get("deliver", True))
    result = issue_store.rebuild_issue(issue_id, deliver=deliver)
    return jsonify(result), (200 if result.get("ok") else 400)


@app.delete("/api/issues/<int:issue_id>")
def delete_issue_api(issue_id: int):
    if not issue_store.delete_issue(issue_id):
        return jsonify({"error": f"No issue {issue_id}"}), 404
    return jsonify({"ok": True})


@app.get("/api/pools")
def get_pools_api():
    limit = request.args.get("limit", default=20, type=int)
    return jsonify({"pools": pool_store.list_pools(max(1, min(int(limit or 20), 100)))})


@app.get("/api/pools/<int:pool_id>")
def get_pool_api(pool_id: int):
    pool = pool_store.load_pool(pool_id)
    if pool is None:
        return jsonify({"error": f"No pool {pool_id}"}), 404
    return jsonify(pool)


@app.put("/api/pools/<int:pool_id>/picks")
def put_pool_picks_api(pool_id: int):
    """Mark cards keep / skip / undecided."""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids")
    pick = data.get("pick")
    if not isinstance(ids, list) or not ids:
        return jsonify({"error": "ids must be a non-empty list"}), 400
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return jsonify({"error": "ids must be integers"}), 400
    try:
        changed = pool_store.set_picks(ids, str(pick))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    pool = pool_store.load_pool(pool_id)
    if pool is None:
        return jsonify({"error": f"No pool {pool_id}"}), 404
    return jsonify({"changed": changed, "pool": pool})


@app.post("/api/pools/refresh")
def post_pool_refresh_api():
    """Fetch and screen a fresh pool. Two AI calls, no article downloads."""
    import main as digest

    settings = store.load_settings()
    tree = store.load_sources_tree(enabled_only=True)
    if not tree:
        return jsonify({"error": "No RSS sources configured"}), 400

    pool_id = digest.run_pool(tree, settings)
    if pool_id is None:
        return jsonify({"error": "No candidates found"}), 400
    return jsonify({"ok": True, "pool": pool_store.load_pool(pool_id)}), 201


@app.post("/api/pools/<int:pool_id>/build")
def post_pool_build_api(pool_id: int):
    """Summarise the kept articles and publish them. Costs AI calls."""
    import main as digest

    data = request.get_json(silent=True) or {}
    deliver = bool(data.get("deliver", True))
    settings = store.load_settings()

    result = digest.run_build(
        pool_id, settings, no_kindle=not deliver, no_books=not deliver
    )
    if result is None:
        return jsonify({"error": "Nothing built — pick some articles first"}), 400

    out_path, issue_id = result
    return jsonify(
        {
            "ok": True,
            "issue_id": issue_id,
            "epub_name": out_path.name,
            "pool": pool_store.load_pool(pool_id),
        }
    )


@app.delete("/api/pools/<int:pool_id>")
def delete_pool_api(pool_id: int):
    if not pool_store.delete_pool(pool_id):
        return jsonify({"error": f"No pool {pool_id}"}), 404
    return jsonify({"ok": True})


@app.post("/api/kindle/test")
def kindle_test():
    settings = store.load_settings()
    ok, message = send_test_email(settings)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "message": message}), status


def resolve_bind() -> tuple[str, list[str]]:
    """Where to listen, plus anything the operator should be told.

    Binding past loopback is the point at which the password stops being
    optional: the bind itself was the only thing keeping reads private. Rather
    than warn and carry on, refuse and stay on loopback.
    """
    notes: list[str] = []
    configured = store.load_settings().dashboard_host
    host, problem = netbind.resolve_host(configured)
    if problem:
        notes.append(problem)

    if not netbind.is_loopback(host) and not auth.password_is_set():
        notes.append(
            f"REFUSING to bind {host}: no dashboard password is set, so every "
            "read would be open to that network. Run ./run.sh set-password "
            "first. Staying on 127.0.0.1."
        )
        return DEFAULT_HOST, notes

    if host == "0.0.0.0":
        notes.append(
            "Listening on every interface, not just your tailnet. There is no "
            "TLS in this app — prefer dashboard_host=tailscale."
        )
    return host, notes


def main() -> None:
    store.init_db()
    store.migrate_from_files_if_empty()
    issue_store.init_db()
    pool_store.init_db()

    host, notes = resolve_bind()
    for note in notes:
        print(f"  ! {note}")

    scheme_note = "" if auth.password_is_set() else "  (no password — reads are open)"
    print(f"BiteSIze dashboard → http://{host}:{PORT}{scheme_note}")
    if not netbind.is_loopback(host):
        print("  Reachable from your other tailnet devices at this address.")
    app.run(host=host, port=PORT, debug=False)


if __name__ == "__main__":
    main()
