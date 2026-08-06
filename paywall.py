"""Paywall bypass via archive mirrors (macOS Shortcut: Remove Paywall)."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import Callable
from urllib.parse import quote

import trafilatura

from config import OUTPUT_DIR, get_settings

# Order: most recommended first (matches Shortcut's archive.is recommendation).
MIRRORS: list[tuple[str, Callable[[str], str]]] = [
    (
        "archive.is",
        lambda url: f"https://archive.is/newest/{url}",
    ),
    (
        "1ft.io",
        lambda url: f"https://1ft.io/{url}",
    ),
    (
        "archive.org",
        lambda url: f"https://web.archive.org/web/2/{url}",
    ),
    (
        "removepaywall.com",
        lambda url: f"https://www.removepaywall.com/search?url={quote(url, safe='')}",
    ),
]

_lock = threading.Lock()
_stats: dict[str, int | float] = {
    "articles": 0,
    "direct_attempts": 0,
    "direct_success": 0,
    "mirror_attempts": 0,
    "mirror_success": 0,
}
_mirror_detail: dict[str, dict[str, int]] = {
    name: {"attempts": 0, "success": 0} for name, _ in MIRRORS
}


def reset_stats() -> None:
    with _lock:
        _stats.update(
            articles=0,
            direct_attempts=0,
            direct_success=0,
            mirror_attempts=0,
            mirror_success=0,
        )
        for detail in _mirror_detail.values():
            detail["attempts"] = 0
            detail["success"] = 0


def _record_direct(attempt: bool, success: bool = False) -> None:
    with _lock:
        if attempt:
            _stats["direct_attempts"] += 1
        if success:
            _stats["direct_success"] += 1


def _record_mirror(name: str, attempt: bool, success: bool = False) -> None:
    with _lock:
        if attempt:
            _stats["mirror_attempts"] += 1
            _mirror_detail[name]["attempts"] += 1
        if success:
            _stats["mirror_success"] += 1
            _mirror_detail[name]["success"] += 1


def _record_article() -> None:
    with _lock:
        _stats["articles"] += 1


def snapshot_stats() -> dict:
    with _lock:
        return {
            "articles": int(_stats["articles"]),
            "direct_attempts": int(_stats["direct_attempts"]),
            "direct_success": int(_stats["direct_success"]),
            "mirror_attempts": int(_stats["mirror_attempts"]),
            "mirror_success": int(_stats["mirror_success"]),
            "mirrors": {
                name: dict(detail) for name, detail in _mirror_detail.items()
            },
        }


def _success_rate(success: int, attempts: int) -> float:
    if attempts <= 0:
        return 0.0
    return round(100.0 * success / attempts, 1)


def format_summary() -> str:
    s = snapshot_stats()
    total = int(s["articles"])
    direct_ok = int(s["direct_success"])
    mirror_ok = int(s["mirror_success"])
    any_ok = direct_ok + mirror_ok
    overall = _success_rate(any_ok, total) if total else 0.0
    direct_rate = _success_rate(direct_ok, int(s["direct_attempts"]))
    mirror_rate = _success_rate(mirror_ok, int(s["mirror_attempts"]))

    lines = [
        f"Paywall fetch: {any_ok}/{total} articles with full text ({overall}%)",
        f"  direct: {direct_ok}/{s['direct_attempts']} ({direct_rate}%)",
        f"  mirrors: {mirror_ok}/{s['mirror_attempts']} ({mirror_rate}%)",
    ]
    for name, detail in s["mirrors"].items():
        att = detail["attempts"]
        if att:
            ok = detail["success"]
            lines.append(f"    · {name}: {ok}/{att} ({_success_rate(ok, att)}%)")
    return "\n".join(lines)


def log_summary(console=None) -> None:
    """Append paywall stats to output/logs and print a one-line summary."""
    summary = format_summary()
    log_dir = OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "paywall-stats.log"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"[{stamp}]\n{summary}\n\n")

    if console is not None:
        console.print(f"[dim]{summary.replace(chr(10), chr(10) + '  ')}[/dim]")


def _extract_text(html: bytes) -> str:
    try:
        text = trafilatura.extract(
            html,
            no_fallback=False,
            include_comments=False,
            include_tables=False,
        )
        return (text or "").strip()
    except Exception:
        return ""


def _usable(text: str, min_chars: int | None = None) -> bool:
    if min_chars is None:
        min_chars = get_settings().min_body_chars
    return len((text or "").strip()) >= min_chars


def fetch_with_paywall_bypass(url: str) -> tuple[str, str | None]:
    """
    Fetch article body: direct URL first, then archive mirrors.

    Returns (text, source) where source is 'direct', a mirror name, or None.
    """
    if not url.strip():
        return "", None

    from feed import _download_url

    _record_article()
    min_chars = get_settings().min_body_chars

    _record_direct(attempt=True)
    raw = _download_url(url, quiet=True)
    if raw:
        text = _extract_text(raw)
        if _usable(text, min_chars):
            _record_direct(attempt=False, success=True)
            return text, "direct"

    for name, build_mirror in MIRRORS:
        mirror_url = build_mirror(url)
        _record_mirror(name, attempt=True)
        raw = _download_url(mirror_url, quiet=True)
        if not raw:
            continue
        text = _extract_text(raw)
        if _usable(text, min_chars):
            _record_mirror(name, attempt=False, success=True)
            return text, name

    return "", None
