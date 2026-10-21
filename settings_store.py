"""SQLite-backed settings and RSS sources for BiteSIze."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "bitesize.db"
SOURCES_FILE = BASE_DIR / "sources.json"
ENV_FILE = BASE_DIR / ".env"

SETTINGS_DEFAULTS: dict[str, tuple[str, str, Any]] = {
    "ai_backend": ("ai", "str", "antigravity"),
    "antigravity_model": ("ai", "str", "gemini-3.5-flash-high"),
    "ollama_host": ("ai", "str", "localhost:11434"),
    "ollama_model": ("ai", "str", "llama3:8b"),
    "ollama_timeout": ("ai", "int", 120),
    "claude_model": ("ai", "str", "claude-haiku-4-5-20251001"),
    "claude_timeout": ("ai", "int", 180),
    # Extended-thinking budget for the Claude backend. Every call here is
    # mechanical JSON, so thinking is pure cost: on a 10-article batch it was
    # 1,515 of 2,139 output tokens, 20.4s vs 8.7s, for identical output. 0 off.
    "claude_thinking_tokens": ("ai", "int", 0),
    "gemini_batch_size": ("ai", "int", 20),
    # Titles screened per AI call. Far larger than the summarising batch because
    # a title costs a fraction of an article preview.
    "prefilter_batch_size": ("ai", "int", 60),
    # AI-written section and global covers are decoration: a readable fallback
    # cover is built without them. They cost one call per section plus one, so
    # turning them off is the cheapest large saving available.
    "ai_covers_enabled": ("ai", "bool", True),
    "gemini_timeout": ("ai", "int", 120),
    "gemini_check_timeout": ("ai", "int", 6),
    "ai_language": ("ai", "str", "pt-BR"),
    # "" follows ai_language (upstream behaviour); "source" keeps each summary
    # in the article's own language.
    "summary_language": ("ai", "str", ""),
    "max_articles_per_feed": ("feed", "int", 10),
    "feed_timeout": ("feed", "int", 15),
    "truncate_chars": ("feed", "int", 450),
    "user_agent": (
        "feed",
        "str",
        "BiteSIze/1.0 (+https://github.com/local/bitesize)",
    ),
    "min_body_chars": ("filter", "int", 180),
    "min_summary_chars": ("filter", "int", 80),
    # Free text describing what you want to read. "" disables personalisation.
    "user_interests": ("filter", "str", ""),
    # Drop stories scoring below this (0-100). 0 keeps everything.
    "min_keep_score": ("filter", "int", 0),
    # Hard cap on stories per issue, highest score first. 0 means unlimited.
    "max_articles_per_issue": ("filter", "int", 0),
    # Fill the cap round-robin across sections instead of taking the highest
    # absolute scores. Without it, whichever sections score well every day take
    # the whole issue and narrower interests never appear.
    "balance_sections": ("filter", "bool", False),
    # Admit this many best stories from every section even when they fall below
    # min_keep_score. Without it a global threshold silently deletes whole
    # interest areas — art and agriculture rarely out-score AI commentary — and
    # section balancing then has nothing from them left to balance.
    "min_section_stories": ("filter", "int", 0),
    # Stories that cleared min_keep_score but lost their slot to balancing are
    # collected into a final section, newest-scoring first. 0 discards them.
    "overflow_section_max": ("filter", "int", 0),
    # Screen on titles first and carry only this many into the body fetch and
    # the summarising pass. 0 disables the screen (every article is summarised).
    "prefilter_keep": ("filter", "int", 0),
    "index_entries_per_page": ("epub", "int", 10),
    "top_picks_on_cover": ("epub", "int", 6),
    # Keep only the newest N EPUBs in output/. 0 keeps every issue forever.
    "output_keep_issues": ("epub", "int", 0),
    "kindle_email": ("kindle", "str", ""),
    "smtp_user": ("kindle", "str", ""),
    "smtp_password": ("kindle", "str", ""),
    "smtp_host": ("kindle", "str", "smtp.gmail.com"),
    "smtp_port": ("kindle", "int", 587),
    "kindle_delivery_enabled": ("kindle", "bool", True),
    "books_delivery_enabled": ("books", "bool", True),
    "icloud_books_dir": ("books", "str", ""),
    "integration_gmail": ("integrations", "bool", False),
    "integration_google_calendar": ("integrations", "bool", False),
    "gmail_max_threads": ("integrations", "int", 30),
    "gmail_lookback_hours": ("integrations", "int", 24),
    "calendar_lookahead_days": ("integrations", "int", 7),
    "calendar_lookback_days": ("integrations", "int", 3),
    "cli_select_all_sources": ("cli", "bool", False),
}


@dataclass
class Settings:
    ai_backend: str = "antigravity"
    antigravity_model: str = "gemini-3.5-flash-high"
    ollama_host: str = "localhost:11434"
    ollama_model: str = "llama3:8b"
    ollama_timeout: int = 120
    claude_model: str = "claude-haiku-4-5-20251001"
    claude_timeout: int = 180
    claude_thinking_tokens: int = 0
    gemini_batch_size: int = 20
    prefilter_batch_size: int = 60
    ai_covers_enabled: bool = True
    gemini_timeout: int = 120
    gemini_check_timeout: int = 6
    ai_language: str = "pt-BR"
    summary_language: str = ""
    max_articles_per_feed: int = 10
    feed_timeout: int = 15
    truncate_chars: int = 450
    user_agent: str = "BiteSIze/1.0 (+https://github.com/local/bitesize)"
    min_body_chars: int = 180
    min_summary_chars: int = 80
    user_interests: str = ""
    min_keep_score: int = 0
    max_articles_per_issue: int = 0
    balance_sections: bool = False
    min_section_stories: int = 0
    overflow_section_max: int = 0
    prefilter_keep: int = 0
    index_entries_per_page: int = 10
    top_picks_on_cover: int = 6
    output_keep_issues: int = 0
    kindle_email: str = ""
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    kindle_delivery_enabled: bool = True
    books_delivery_enabled: bool = True
    icloud_books_dir: str = ""
    integration_gmail: bool = False
    integration_google_calendar: bool = False
    gmail_max_threads: int = 30
    gmail_lookback_hours: int = 24
    calendar_lookahead_days: int = 7
    calendar_lookback_days: int = 3
    cli_select_all_sources: bool = False


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _encode_value(value: Any, value_type: str) -> str:
    if value_type == "bool":
        return "1" if value else "0"
    return str(value)


def _decode_value(raw: str, value_type: str) -> Any:
    if value_type == "int":
        return int(raw)
    if value_type == "bool":
        return raw in ("1", "true", "True", "yes")
    return raw


def init_db() -> None:
    with _get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                value_type TEXT NOT NULL,
                grp TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                sort_order INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS feeds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                UNIQUE(category_id, name)
            );
            """
        )
        existing = {
            row["key"]
            for row in conn.execute("SELECT key FROM settings").fetchall()
        }
        for key, (group, value_type, default) in SETTINGS_DEFAULTS.items():
            if key not in existing:
                conn.execute(
                    "INSERT INTO settings (key, value, value_type, grp) VALUES (?, ?, ?, ?)",
                    (key, _encode_value(default, value_type), value_type, group),
                )


def load_settings() -> Settings:
    init_db()
    with _get_connection() as conn:
        rows = conn.execute("SELECT key, value, value_type FROM settings").fetchall()
    data: dict[str, Any] = {}
    for row in rows:
        data[row["key"]] = _decode_value(row["value"], row["value_type"])
    return Settings(**{k: data[k] for k in SETTINGS_DEFAULTS if k in data})


def set_setting(key: str, value: Any) -> None:
    if key not in SETTINGS_DEFAULTS:
        raise KeyError(f"Unknown setting: {key}")
    _, value_type, _ = SETTINGS_DEFAULTS[key]
    with _get_connection() as conn:
        conn.execute(
            "UPDATE settings SET value = ? WHERE key = ?",
            (_encode_value(value, value_type), key),
        )


def update_settings(updates: dict[str, Any]) -> Settings:
    for key, value in updates.items():
        if key == "smtp_password" and not str(value or "").strip():
            continue
        set_setting(key, value)
    return load_settings()


def settings_for_api(mask_secrets: bool = True) -> dict[str, dict[str, Any]]:
    init_db()
    grouped: dict[str, dict[str, Any]] = {}
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT key, value, value_type, grp FROM settings ORDER BY grp, key"
        ).fetchall()
    for row in rows:
        key = row["key"]
        val = _decode_value(row["value"], row["value_type"])
        if mask_secrets and key == "smtp_password":
            grouped.setdefault(row["grp"], {})[key] = ""
            grouped[row["grp"]]["smtp_password_set"] = bool(val)
            continue
        grouped.setdefault(row["grp"], {})[key] = val
    return grouped


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip().strip('"').strip("'")
    return out


_ENV_TO_SETTING = {
    "AI_BACKEND": "ai_backend",
    "ANTIGRAVITY_MODEL": "antigravity_model",
    "AI_LANGUAGE": "ai_language",
    "AI_COVERS_ENABLED": "ai_covers_enabled",
    "PREFILTER_BATCH_SIZE": "prefilter_batch_size",
    "CLAUDE_MODEL": "claude_model",
    "CLAUDE_TIMEOUT": "claude_timeout",
    "CLAUDE_THINKING_TOKENS": "claude_thinking_tokens",
    "SUMMARY_LANGUAGE": "summary_language",
    "USER_INTERESTS": "user_interests",
    "MIN_KEEP_SCORE": "min_keep_score",
    "MAX_ARTICLES_PER_ISSUE": "max_articles_per_issue",
    "BALANCE_SECTIONS": "balance_sections",
    "MIN_SECTION_STORIES": "min_section_stories",
    "OVERFLOW_SECTION_MAX": "overflow_section_max",
    "PREFILTER_KEEP": "prefilter_keep",
    "OUTPUT_KEEP_ISSUES": "output_keep_issues",
    "OLLAMA_HOST": "ollama_host",
    "OLLAMA_MODEL": "ollama_model",
    "OLLAMA_TIMEOUT": "ollama_timeout",
    "KINDLE_EMAIL": "kindle_email",
    "SMTP_USER": "smtp_user",
    "SMTP_PASSWORD": "smtp_password",
    "SMTP_HOST": "smtp_host",
    "SMTP_PORT": "smtp_port",
    "GMAIL_MAX_THREADS": "gmail_max_threads",
    "GMAIL_LOOKBACK_HOURS": "gmail_lookback_hours",
    "CALENDAR_LOOKAHEAD_DAYS": "calendar_lookahead_days",
    "CALENDAR_LOOKBACK_DAYS": "calendar_lookback_days",
}


def migrate_from_files_if_empty() -> bool:
    """Import sources.json and .env on first run. Returns True if migration ran."""
    init_db()
    with _get_connection() as conn:
        feed_count = conn.execute("SELECT COUNT(*) AS n FROM feeds").fetchone()["n"]
    if feed_count > 0:
        return False

    migrated = False

    if SOURCES_FILE.exists():
        data = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        integrations = data.get("integrations", {})
        updates: dict[str, Any] = {}
        if "gmail" in integrations:
            updates["integration_gmail"] = bool(integrations["gmail"])
        if "google_calendar" in integrations:
            updates["integration_google_calendar"] = bool(integrations["google_calendar"])
        if updates:
            update_settings(updates)

        for sort_order, (cat_name, feeds) in enumerate(
            data.get("categories", {}).items()
        ):
            if not isinstance(feeds, dict):
                continue
            cat_id = add_category(cat_name, sort_order=sort_order)
            for feed_name, url in feeds.items():
                add_feed(cat_id, feed_name, url, enabled=True)
        migrated = True

    env = _parse_env_file(ENV_FILE)
    env_updates: dict[str, Any] = {}
    for env_key, setting_key in _ENV_TO_SETTING.items():
        if env_key in env and env[env_key]:
            _, value_type, _ = SETTINGS_DEFAULTS[setting_key]
            raw = env[env_key]
            if value_type == "int":
                env_updates[setting_key] = int(raw)
            else:
                env_updates[setting_key] = raw
    if env_updates:
        update_settings(env_updates)
        migrated = True

    return migrated


def load_sources_tree(enabled_only: bool = True) -> dict[str, dict[str, str]]:
    init_db()
    tree: dict[str, dict[str, str]] = {}
    with _get_connection() as conn:
        query = """
            SELECT c.name AS category, f.name AS feed, f.url, f.enabled
            FROM categories c
            JOIN feeds f ON f.category_id = c.id
            ORDER BY c.sort_order, c.name, f.name
        """
        for row in conn.execute(query).fetchall():
            if enabled_only and not row["enabled"]:
                continue
            tree.setdefault(row["category"], {})[row["feed"]] = row["url"]
    return tree


def load_sources_for_api() -> dict[str, list[dict[str, Any]]]:
    init_db()
    categories: list[dict[str, Any]] = []
    with _get_connection() as conn:
        cats = conn.execute(
            "SELECT id, name FROM categories ORDER BY sort_order, name"
        ).fetchall()
        for cat in cats:
            feeds = conn.execute(
                """
                SELECT id, name, url, enabled FROM feeds
                WHERE category_id = ? ORDER BY name
                """,
                (cat["id"],),
            ).fetchall()
            categories.append(
                {
                    "id": cat["id"],
                    "name": cat["name"],
                    "feeds": [
                        {
                            "id": f["id"],
                            "name": f["name"],
                            "url": f["url"],
                            "enabled": bool(f["enabled"]),
                        }
                        for f in feeds
                    ],
                }
            )
    return {"categories": categories}


def add_category(name: str, sort_order: int | None = None) -> int:
    init_db()
    with _get_connection() as conn:
        if sort_order is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(sort_order), -1) + 1 AS n FROM categories"
            ).fetchone()
            sort_order = row["n"]
        cur = conn.execute(
            "INSERT INTO categories (name, sort_order) VALUES (?, ?)",
            (name, sort_order),
        )
        return int(cur.lastrowid)


def update_category(category_id: int, name: str) -> None:
    with _get_connection() as conn:
        conn.execute(
            "UPDATE categories SET name = ? WHERE id = ?",
            (name, category_id),
        )


def delete_category(category_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))


def add_feed(
    category_id: int,
    name: str,
    url: str,
    enabled: bool = True,
) -> int:
    init_db()
    with _get_connection() as conn:
        cur = conn.execute(
            """
            INSERT INTO feeds (category_id, name, url, enabled)
            VALUES (?, ?, ?, ?)
            """,
            (category_id, name, url, 1 if enabled else 0),
        )
        return int(cur.lastrowid)


def update_feed(
    feed_id: int,
    *,
    name: str | None = None,
    url: str | None = None,
    enabled: bool | None = None,
) -> None:
    fields: list[str] = []
    values: list[Any] = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if url is not None:
        fields.append("url = ?")
        values.append(url)
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(1 if enabled else 0)
    if not fields:
        return
    values.append(feed_id)
    with _get_connection() as conn:
        conn.execute(
            f"UPDATE feeds SET {', '.join(fields)} WHERE id = ?",
            values,
        )


def delete_feed(feed_id: int) -> None:
    with _get_connection() as conn:
        conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
