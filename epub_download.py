"""Download a stored issue's EPUB from the dashboard.

iCloud Books delivery only exists on macOS. On a Linux host (the Raspberry Pi)
the phone fetches the file instead: open the dashboard, tap Download EPUB, and
Safari offers to open it in Books.

The file is found by its name inside OUTPUT_DIR, never at the stored path.
That path was written on whichever machine built the issue (often the Mac),
and trusting it would let a bad row point anywhere on this disk.

Kept in its own module so the fork's change to dashboard.py is two lines.
Auth is dashboard.check_auth's job: with a password set, these routes need a
session like every other /api/ read.
"""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, jsonify, send_file

import config
import issues as issue_store

bp = Blueprint("epub_download", __name__)


def epub_file_for(stored_path: str | None) -> Path | None:
    """The EPUB in OUTPUT_DIR with the stored path's file name, if it exists."""
    name = Path(stored_path or "").name
    if not name.lower().endswith(".epub"):
        return None
    out = Path(config.OUTPUT_DIR).resolve()
    candidate = (out / name).resolve()
    if candidate.parent != out or not candidate.is_file():
        return None
    return candidate


def _send(stored_path: str | None):
    path = epub_file_for(stored_path)
    if path is None:
        return jsonify({"error": "EPUB not on disk. Rebuild the issue to recreate it."}), 404
    resp = send_file(path, mimetype="application/epub+zip",
                     as_attachment=True, download_name=path.name)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.get("/api/issues/<int:issue_id>/epub")
def download_issue_epub(issue_id: int):
    issue = issue_store.load_issue(issue_id)
    if issue is None:
        return jsonify({"error": f"No issue {issue_id}"}), 404
    return _send(issue.get("epub_path"))


@bp.get("/api/issues/latest/epub")
def download_latest_epub():
    newest = issue_store.list_issues(1)
    if not newest:
        return jsonify({"error": "No issues recorded yet"}), 404
    return _send(newest[0]["epub_path"])
