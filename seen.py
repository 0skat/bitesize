"""Which stories have already been offered, so they are never offered twice.

`feed.dedupe_articles` only ever looked inside a single run, so anything still
sitting in a feed was a fresh candidate again the next morning. Measured over
seven pools, nine URLs appeared in every single one — six consecutive Import AI
issues, and a Modern Farmer piece from April that kept scoring in the
seventies in November.

This is deliberately a table of its own rather than a query over
`pool_articles`, because pools are pruned. Reading history out of rows that get
deleted would quietly resurrect every old story the moment a prune ran.

A URL is remembered when it is *shown* — recorded into a pool — not when it is
fetched. Something the title screen dropped was never offered to anyone, so it
is free to come back tomorrow.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from settings_store import _get_connection


def init_db() -> None:
    """Create the seen table. Safe to call repeatedly."""
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS seen_urls (
                url TEXT PRIMARY KEY,
                first_seen TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                section TEXT NOT NULL DEFAULT ''
            );
            CREATE INDEX IF NOT EXISTS idx_seen_urls_first_seen
                ON seen_urls(first_seen);
            """
        )


def record_seen(articles: Iterable[dict[str, Any]]) -> int:
    """Remember these articles as offered. Returns how many are newly stored.

    The first sighting's timestamp is kept: re-recording a URL must not push
    its expiry further out, or a story that keeps reappearing in a feed would
    stay suppressed forever by accident rather than by policy.
    """
    init_db()
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    rows = [
        (
            (art.get("url") or "").strip(),
            now,
            str(art.get("title") or "")[:300],
            str(art.get("category") or ""),
        )
        for art in articles
    ]
    rows = [r for r in rows if r[0]]
    if not rows:
        return 0
    with _get_connection() as conn:
        before = conn.execute("SELECT COUNT(*) FROM seen_urls").fetchone()[0]
        conn.executemany(
            """
            INSERT INTO seen_urls (url, first_seen, title, section)
            VALUES (?,?,?,?)
            ON CONFLICT(url) DO NOTHING
            """,
            rows,
        )
        after = conn.execute("SELECT COUNT(*) FROM seen_urls").fetchone()[0]
    return after - before


def seen_urls(within_days: int = 0) -> set[str]:
    """URLs already offered. `within_days` 0 means every one on record."""
    init_db()
    with _get_connection() as conn:
        if within_days > 0:
            cutoff = (datetime.now() - timedelta(days=within_days)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
            rows = conn.execute(
                "SELECT url FROM seen_urls WHERE first_seen >= ?", (cutoff,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT url FROM seen_urls").fetchall()
    return {r[0] for r in rows}


def filter_seen(
    articles: list[dict[str, Any]], within_days: int = 0
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split articles into never-offered vs already-offered.

    An article with no URL cannot be tracked, so it is kept rather than
    dropped: losing it silently would be worse than showing it twice.
    """
    known = seen_urls(within_days)
    if not known:
        return list(articles), []
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for art in articles:
        url = (art.get("url") or "").strip()
        (dropped if url and url in known else kept).append(art)
    return kept, dropped


def forget(url: str) -> bool:
    """Drop one URL from the record, so it can be offered again."""
    init_db()
    with _get_connection() as conn:
        cur = conn.execute("DELETE FROM seen_urls WHERE url = ?", ((url or "").strip(),))
    return cur.rowcount > 0


def prune_seen(keep_days: int) -> int:
    """Forget sightings older than `keep_days`. 0 keeps everything."""
    init_db()
    if keep_days <= 0:
        return 0
    cutoff = (datetime.now() - timedelta(days=keep_days)).strftime("%Y-%m-%dT%H:%M:%S")
    with _get_connection() as conn:
        cur = conn.execute("DELETE FROM seen_urls WHERE first_seen < ?", (cutoff,))
    return cur.rowcount


def count_seen() -> int:
    init_db()
    with _get_connection() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM seen_urls").fetchone()[0])
