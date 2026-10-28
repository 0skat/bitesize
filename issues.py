"""Stored issues: what each run actually picked, so it can be reviewed.

A run's article list only ever existed in memory, so once the EPUB was written
there was no way to see what had been chosen or to drop something unwanted
without regenerating the whole digest and paying for the AI again. Each issue
is recorded here instead, and the dashboard edits it in place: excluding a
story and rebuilding costs no AI calls, because the summaries are already here.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from settings_store import _get_connection

# Fields of an article dict that the EPUB writer needs back. `content` is the
# rendered body, so it has to be stored in full for a rebuild to work.
_ARTICLE_FIELDS = (
    "title",
    "url",
    "source",
    "summary",
    "content",
    "published",
    "tipo",
    "relevance",
    "relevance_source",
)


def init_db() -> None:
    """Create the issue tables. Safe to call repeatedly."""
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                epub_path TEXT NOT NULL,
                article_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS issue_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER NOT NULL
                    REFERENCES issues(id) ON DELETE CASCADE,
                section TEXT NOT NULL,
                section_order INTEGER NOT NULL DEFAULT 0,
                section_kind TEXT NOT NULL DEFAULT 'main',
                position INTEGER NOT NULL DEFAULT 0,
                excluded INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                summary TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                published TEXT NOT NULL DEFAULT '',
                tipo TEXT NOT NULL DEFAULT '',
                temas TEXT NOT NULL DEFAULT '[]',
                relevance INTEGER NOT NULL DEFAULT 0,
                relevance_source TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_issue_articles_issue
                ON issue_articles(issue_id);
            """
        )


def record_issue(
    epub_path: Path,
    sections: dict[str, list[dict]],
    overflow_section: str = "",
) -> int:
    """Store one run's picks. Returns the new issue id."""
    init_db()
    created = ""
    try:
        from datetime import datetime

        created = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:  # pragma: no cover - datetime cannot realistically fail
        pass

    total = sum(len(v) for v in sections.values())
    with _get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO issues (created_at, epub_path, article_count) VALUES (?, ?, ?)",
            (created, str(epub_path), total),
        )
        issue_id = int(cur.lastrowid)

        rows = []
        for order, (section, articles) in enumerate(sections.items()):
            kind = "overflow" if section == overflow_section else "main"
            for position, art in enumerate(articles):
                rows.append(
                    (
                        issue_id,
                        section,
                        order,
                        kind,
                        position,
                        str(art.get("title") or ""),
                        str(art.get("url") or ""),
                        str(art.get("source") or ""),
                        str(art.get("summary") or ""),
                        str(art.get("content") or ""),
                        str(art.get("published") or ""),
                        str(art.get("tipo") or ""),
                        json.dumps(art.get("temas") or [], ensure_ascii=False),
                        int(art.get("relevance") or 0),
                        str(art.get("relevance_source") or ""),
                    )
                )
        conn.executemany(
            """
            INSERT INTO issue_articles (
                issue_id, section, section_order, section_kind, position,
                title, url, source, summary, content, published, tipo, temas,
                relevance, relevance_source
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
    return issue_id


def list_issues(limit: int = 20) -> list[dict[str, Any]]:
    """Newest issues first, with live kept/excluded counts."""
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT i.id, i.created_at, i.epub_path, i.article_count,
                   SUM(CASE WHEN a.excluded = 1 THEN 1 ELSE 0 END) AS excluded,
                   COUNT(a.id) AS stored
            FROM issues i
            LEFT JOIN issue_articles a ON a.issue_id = i.id
            GROUP BY i.id
            ORDER BY i.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    out = []
    for r in rows:
        stored = r["stored"] or 0
        excluded = r["excluded"] or 0
        out.append(
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "epub_path": r["epub_path"],
                "epub_name": Path(r["epub_path"]).name,
                "epub_exists": Path(r["epub_path"]).exists(),
                "stored": stored,
                "excluded": excluded,
                "kept": stored - excluded,
            }
        )
    return out


def _row_to_article(row: sqlite3.Row) -> dict[str, Any]:
    try:
        temas = json.loads(row["temas"])
    except (json.JSONDecodeError, TypeError):
        temas = []
    art: dict[str, Any] = {f: row[f] for f in _ARTICLE_FIELDS}
    art["temas"] = temas if isinstance(temas, list) else []
    return art


def load_issue(issue_id: int) -> dict[str, Any] | None:
    """One issue as section groups, for the dashboard. Bodies are omitted."""
    init_db()
    with _get_connection() as conn:
        issue = conn.execute(
            "SELECT id, created_at, epub_path, article_count FROM issues WHERE id = ?",
            (int(issue_id),),
        ).fetchone()
        if issue is None:
            return None
        rows = conn.execute(
            """
            SELECT * FROM issue_articles
            WHERE issue_id = ?
            ORDER BY section_order, position
            """,
            (int(issue_id),),
        ).fetchall()

    sections: list[dict[str, Any]] = []
    index: dict[str, dict[str, Any]] = {}
    for r in rows:
        sec = index.get(r["section"])
        if sec is None:
            sec = {"name": r["section"], "kind": r["section_kind"], "articles": []}
            index[r["section"]] = sec
            sections.append(sec)
        sec["articles"].append(
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "source": r["source"],
                "summary": r["summary"],
                "published": r["published"],
                "tipo": r["tipo"],
                "temas": _row_to_article(r)["temas"],
                "relevance": r["relevance"],
                "relevance_source": r["relevance_source"],
                "excluded": bool(r["excluded"]),
            }
        )

    return {
        "id": issue["id"],
        "created_at": issue["created_at"],
        "epub_path": issue["epub_path"],
        "epub_name": Path(issue["epub_path"]).name,
        "epub_exists": Path(issue["epub_path"]).exists(),
        "sections": sections,
    }


def set_excluded(article_id: int, excluded: bool) -> bool:
    """Mark one stored article in or out. False if the id is unknown."""
    init_db()
    with _get_connection() as conn:
        cur = conn.execute(
            "UPDATE issue_articles SET excluded = ? WHERE id = ?",
            (1 if excluded else 0, int(article_id)),
        )
        return cur.rowcount > 0


def set_excluded_many(article_ids: list[int], excluded: bool) -> int:
    """Mark several at once. Returns how many rows changed."""
    if not article_ids:
        return 0
    init_db()
    marks = ",".join("?" for _ in article_ids)
    with _get_connection() as conn:
        cur = conn.execute(
            f"UPDATE issue_articles SET excluded = ? WHERE id IN ({marks})",
            [1 if excluded else 0, *(int(i) for i in article_ids)],
        )
        return cur.rowcount


def issue_sections_for_epub(issue_id: int) -> tuple[dict[str, list[dict]], str]:
    """Kept articles as the shape generate_epub wants, plus the overflow name.

    Sections left empty by exclusions are dropped, so removing a whole section
    does not leave a blank front page behind.
    """
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM issue_articles
            WHERE issue_id = ? AND excluded = 0
            ORDER BY section_order, position
            """,
            (int(issue_id),),
        ).fetchall()

    sections: dict[str, list[dict]] = {}
    overflow = ""
    for r in rows:
        sections.setdefault(r["section"], []).append(_row_to_article(r))
        if r["section_kind"] == "overflow":
            overflow = r["section"]
    return sections, overflow


def delete_issue(issue_id: int) -> bool:
    """Forget one stored issue. Does not touch the EPUB on disk."""
    init_db()
    with _get_connection() as conn:
        cur = conn.execute("DELETE FROM issue_articles WHERE issue_id = ?", (int(issue_id),))
        cur2 = conn.execute("DELETE FROM issues WHERE id = ?", (int(issue_id),))
        return cur2.rowcount > 0 or cur.rowcount > 0


def prune_issues(keep: int) -> int:
    """Keep only the newest `keep` stored issues. 0 keeps everything."""
    if keep <= 0:
        return 0
    init_db()
    with _get_connection() as conn:
        stale = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM issues ORDER BY id DESC LIMIT -1 OFFSET ?",
                (int(keep),),
            ).fetchall()
        ]
        if not stale:
            return 0
        marks = ",".join("?" for _ in stale)
        conn.execute(f"DELETE FROM issue_articles WHERE issue_id IN ({marks})", stale)
        conn.execute(f"DELETE FROM issues WHERE id IN ({marks})", stale)
    return len(stale)


def rebuild_issue(issue_id: int, deliver: bool = True) -> dict[str, Any]:
    """Rewrite an issue's EPUB from its kept articles.

    No AI is involved: summaries, tags and scores are already stored, and
    covers fall back to the non-AI layout. That is the point of recording the
    issue — dropping a story costs nothing but a rewrite.
    """
    from config import console, get_settings
    from epub import generate_epub

    issue = load_issue(issue_id)
    if issue is None:
        return {"ok": False, "error": f"No stored issue {issue_id}"}

    sections, _overflow = issue_sections_for_epub(issue_id)
    total = sum(len(v) for v in sections.values())
    if total == 0:
        return {"ok": False, "error": "Every article is excluded — nothing to build"}

    out_path = Path(issue["epub_path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    generate_epub(sections, {}, {}, out_path)

    result: dict[str, Any] = {
        "ok": True,
        "issue_id": issue_id,
        "epub_path": str(out_path),
        "epub_name": out_path.name,
        "articles": total,
        "sections": len(sections),
        "delivered": False,
    }

    if deliver:
        settings = get_settings()
        if settings.books_delivery_enabled:
            from books import copy_to_icloud_books

            result["delivered"] = copy_to_icloud_books(out_path, settings)
        else:
            console.print("  [dim]Books delivery disabled — EPUB rewritten only.[/dim]")
    return result
