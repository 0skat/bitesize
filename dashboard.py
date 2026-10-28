"""Local settings dashboard — Flask REST API + static HTML UI."""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

import issues as issue_store
import settings_store as store
from config import BASE_DIR, load_env, reload_settings
from kindle import send_test_email
from preview import build_source_preview

load_env()

STATIC_DIR = Path(__file__).parent / "dashboard_static"
HOST = "127.0.0.1"
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


def _require_auth():
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {DASHBOARD_TOKEN}":
        return jsonify({"error": "Unauthorized"}), 401
    return None


@app.before_request
def check_auth():
    if request.method == "OPTIONS" or request.path == "/api/health":
        return None
    if request.path.startswith("/api/") and request.method != "GET":
        return _require_auth()
    return None


@app.get("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.get("/api/health")
def health():
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


@app.post("/api/kindle/test")
def kindle_test():
    settings = store.load_settings()
    ok, message = send_test_email(settings)
    status = 200 if ok else 400
    return jsonify({"ok": ok, "message": message}), status


def main() -> None:
    store.init_db()
    store.migrate_from_files_if_empty()
    issue_store.init_db()
    print(f"BiteSIze dashboard → http://{HOST}:{PORT}")
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()
