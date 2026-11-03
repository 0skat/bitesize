"""The candidate pool: screened headlines awaiting a human pick.

The expensive half of a run is fetching article bodies and summarising them,
and until now that happened to everything the title screen kept — eighty
articles to publish twenty-five. Curating between the two phases is both
cheaper and more controllable: only what you keep gets fetched and summarised.

A pool holds the screened headlines with no bodies and no summaries, so
building one costs two AI calls. `main.py --pool` writes one, the dashboard
picks through it, and `main.py --build` turns the keepers into an issue.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from settings_store import _get_connection

# Pick states. Undecided is distinct from skipped so the dashboard can show
# how much of a pool has actually been reviewed.
UNDECIDED = 0
KEEP = 1
SKIP = -1

_PICKS = {"keep": KEEP, "skip": SKIP, "undecided": UNDECIDED}


def init_db() -> None:
    """Create the pool tables. Safe to call repeatedly."""
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                candidate_count INTEGER NOT NULL DEFAULT 0,
                built_issue_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS pool_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER NOT NULL
                    REFERENCES pools(id) ON DELETE CASCADE,
                section TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0,
                pick INTEGER NOT NULL DEFAULT 0,
                title TEXT NOT NULL DEFAULT '',
                url TEXT NOT NULL DEFAULT '',
                source TEXT NOT NULL DEFAULT '',
                published TEXT NOT NULL DEFAULT '',
                rss_snippet TEXT NOT NULL DEFAULT '',
                prefilter_score INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_pool_articles_pool
                ON pool_articles(pool_id);
            """
        )


def record_pool(candidates: list[dict]) -> int:
    """Store screened headlines as a new pool. Returns its id.

    Candidates arrive ranked, and that order is preserved so the dashboard can
    present the strongest first without re-sorting.
    """
    init_db()
    created = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with _get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO pools (created_at, candidate_count) VALUES (?, ?)",
            (created, len(candidates)),
        )
        pool_id = int(cur.lastrowid)
        conn.executemany(
            """
            INSERT INTO pool_articles (
                pool_id, section, position, title, url, source, published,
                rss_snippet, prefilter_score
            ) VALUES (?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    pool_id,
                    str(art.get("category") or ""),
                    position,
                    str(art.get("title") or ""),
                    str(art.get("url") or ""),
                    str(art.get("source") or ""),
                    str(art.get("published") or ""),
                    str(art.get("rss_snippet") or art.get("content") or ""),
                    int(art.get("prefilter_score") or 0),
                )
                for position, art in enumerate(candidates)
            ],
        )
    return pool_id


def latest_pool_id() -> int | None:
    init_db()
    with _get_connection() as conn:
        row = conn.execute("SELECT id FROM pools ORDER BY id DESC LIMIT 1").fetchone()
    return int(row["id"]) if row else None


def list_pools(limit: int = 20) -> list[dict[str, Any]]:
    """Newest pools first, with live pick tallies."""
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT p.id, p.created_at, p.candidate_count, p.built_issue_id,
                   COUNT(a.id) AS stored,
                   SUM(CASE WHEN a.pick = 1 THEN 1 ELSE 0 END) AS kept,
                   SUM(CASE WHEN a.pick = -1 THEN 1 ELSE 0 END) AS skipped
            FROM pools p
            LEFT JOIN pool_articles a ON a.pool_id = p.id
            GROUP BY p.id
            ORDER BY p.id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    out = []
    for r in rows:
        stored = r["stored"] or 0
        kept = r["kept"] or 0
        skipped = r["skipped"] or 0
        out.append(
            {
                "id": r["id"],
                "created_at": r["created_at"],
                "stored": stored,
                "kept": kept,
                "skipped": skipped,
                "undecided": stored - kept - skipped,
                "built_issue_id": r["built_issue_id"],
            }
        )
    return out


def _row_to_card(row: sqlite3.Row) -> dict[str, Any]:
    pick = row["pick"]
    return {
        "id": row["id"],
        "section": row["section"],
        "title": row["title"],
        "url": row["url"],
        "source": row["source"],
        "published": row["published"],
        "snippet": row["rss_snippet"][:400],
        "prefilter_score": row["prefilter_score"],
        "pick": "keep" if pick == KEEP else "skip" if pick == SKIP else "undecided",
    }


def load_pool(pool_id: int) -> dict[str, Any] | None:
    """One pool as a ranked card list, for picking."""
    init_db()
    with _get_connection() as conn:
        pool = conn.execute(
            "SELECT id, created_at, candidate_count, built_issue_id "
            "FROM pools WHERE id = ?",
            (int(pool_id),),
        ).fetchone()
        if pool is None:
            return None
        rows = conn.execute(
            "SELECT * FROM pool_articles WHERE pool_id = ? ORDER BY position",
            (int(pool_id),),
        ).fetchall()

    cards = [_row_to_card(r) for r in rows]
    return {
        "id": pool["id"],
        "created_at": pool["created_at"],
        "built_issue_id": pool["built_issue_id"],
        "stored": len(cards),
        "kept": sum(1 for c in cards if c["pick"] == "keep"),
        "skipped": sum(1 for c in cards if c["pick"] == "skip"),
        "undecided": sum(1 for c in cards if c["pick"] == "undecided"),
        "sections": sorted({c["section"] for c in cards if c["section"]}),
        "articles": cards,
    }


def set_picks(article_ids: list[int], pick: str) -> int:
    """Mark cards keep / skip / undecided. Returns rows changed."""
    if pick not in _PICKS:
        raise ValueError(f"pick must be one of {sorted(_PICKS)}, got {pick!r}")
    if not article_ids:
        return 0
    init_db()
    marks = ",".join("?" for _ in article_ids)
    with _get_connection() as conn:
        cur = conn.execute(
            f"UPDATE pool_articles SET pick = ? WHERE id IN ({marks})",
            [_PICKS[pick], *(int(i) for i in article_ids)],
        )
        return cur.rowcount


def picked_articles(pool_id: int) -> list[dict[str, Any]]:
    """Kept cards as article dicts the pipeline can carry forward.

    `content` is seeded with the RSS snippet so an article whose body fetch
    fails still has the text the feed gave us, exactly as the normal path does.
    """
    init_db()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM pool_articles
            WHERE pool_id = ? AND pick = ?
            ORDER BY position
            """,
            (int(pool_id), KEEP),
        ).fetchall()
    return [
        {
            "title": r["title"],
            "url": r["url"],
            "source": r["source"],
            "published": r["published"],
            "category": r["section"],
            "content": r["rss_snippet"],
            "rss_snippet": r["rss_snippet"],
            "prefilter_score": r["prefilter_score"],
        }
        for r in rows
    ]


def mark_built(pool_id: int, issue_id: int) -> None:
    """Record which issue a pool produced."""
    init_db()
    with _get_connection() as conn:
        conn.execute(
            "UPDATE pools SET built_issue_id = ? WHERE id = ?",
            (int(issue_id), int(pool_id)),
        )


def delete_pool(pool_id: int) -> bool:
    init_db()
    with _get_connection() as conn:
        conn.execute("DELETE FROM pool_articles WHERE pool_id = ?", (int(pool_id),))
        cur = conn.execute("DELETE FROM pools WHERE id = ?", (int(pool_id),))
        return cur.rowcount > 0


def prune_pools(keep: int) -> int:
    """Keep only the newest `keep` pools. 0 keeps everything."""
    if keep <= 0:
        return 0
    init_db()
    with _get_connection() as conn:
        stale = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM pools ORDER BY id DESC LIMIT -1 OFFSET ?",
                (int(keep),),
            ).fetchall()
        ]
        if not stale:
            return 0
        marks = ",".join("?" for _ in stale)
        conn.execute(f"DELETE FROM pool_articles WHERE pool_id IN ({marks})", stale)
        conn.execute(f"DELETE FROM pools WHERE id IN ({marks})", stale)
    return len(stale)
