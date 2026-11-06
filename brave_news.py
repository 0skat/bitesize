"""Brave Search as an article source, alongside or instead of RSS.

RSS is what a publisher chooses to syndicate. Some of the sources worth
reading do not offer a usable feed at all — Reuters retired its public ones,
which is why this fork fell back to Guardian World and Deutsche Welle — and the
feeds that do exist carry whatever the publisher leaves in them, including
evergreen posts from April.

Brave's news endpoint inverts both problems: results are query-driven, so a
section can ask for exactly what it wants, and `freshness=pd` bounds them to
the last 24 hours at the source instead of filtering afterwards. `site:` in a
query pins a publisher that has no feed.

Articles come back in the same shape `feed.fetch_feed` returns, so everything
downstream — dedupe, the age filter, the title screen, the pool — is unchanged.

Costs money per call, so nothing here runs unless `brave_enabled` is on and a
key is present. Search is $5 per 1,000 requests against $5 of monthly credit,
which at one query per section per day is about $1.50 a month.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlsplit

import requests

from config import console, get_settings

ENDPOINT = "https://api.search.brave.com/res/v1/news/search"

# Brave's own cap. Asking for more is rejected rather than clamped.
MAX_COUNT = 50

FRESHNESS = {"pd": "past 24 hours", "pw": "past week", "pm": "past month", "py": "past year"}


def api_key(settings: Any = None) -> str:
    """The key, from the settings database or the environment.

    Checked in that order so the dashboard can hold it, while a shell or a
    systemd unit can override without touching the database.
    """
    settings = settings or get_settings()
    return (
        os.environ.get("BRAVE_API_KEY")
        or getattr(settings, "brave_api_key", "")
        or ""
    ).strip()


def _publisher(result: dict[str, Any]) -> str:
    """A readable source name: Brave's own label, else the hostname."""
    meta = result.get("meta_url") or {}
    for candidate in (
        (result.get("profile") or {}).get("name"),
        meta.get("netloc"),
        meta.get("hostname"),
    ):
        if candidate:
            return str(candidate).removeprefix("www.")
    host = urlsplit(result.get("url") or "").netloc
    return host.removeprefix("www.") or "Brave Search"


_AGE_UNITS = {
    "second": 1, "seconds": 1, "minute": 60, "minutes": 60,
    "hour": 3600, "hours": 3600, "day": 86400, "days": 86400,
    "week": 604800, "weeks": 604800, "month": 2592000, "months": 2592000,
    "year": 31536000, "years": 31536000,
}


def _timestamp(result: dict[str, Any], *, now: float | None = None) -> int:
    """Seconds since the epoch for a result, or 0 when it cannot be read.

    Brave gives `page_age` as an ISO timestamp on most results and `age` as
    prose ("3 hours ago") on some. 0 means unknown, which the age filter
    treats as keep — the same contract as an RSS entry with no date.
    """
    raw = (result.get("page_age") or "").strip()
    if raw:
        try:
            text = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            try:
                return int(parsedate_to_datetime(raw).timestamp())
            except (TypeError, ValueError):
                pass

    prose = (result.get("age") or "").strip().lower()
    if prose.endswith(" ago"):
        parts = prose[:-4].split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1] in _AGE_UNITS:
            delta = int(parts[0]) * _AGE_UNITS[parts[1]]
            return int((time.time() if now is None else now) - delta)
    return 0


def _to_article(result: dict[str, Any]) -> dict[str, Any] | None:
    """One Brave result in the shape the rest of the pipeline expects."""
    title = (result.get("title") or "").strip()
    url = (result.get("url") or "").strip()
    if not title or not url:
        return None

    snippet = (result.get("description") or "").strip()
    extra = result.get("extra_snippets") or []
    if extra:
        snippet = " ".join([snippet, *[str(x) for x in extra]]).strip()

    ts = _timestamp(result)
    return {
        "source": _publisher(result),
        "category": "",          # set by the caller, as with fetch_feed
        "title": title,
        "content": snippet,
        "rss_snippet": snippet,
        "url": url,
        "published": datetime.fromtimestamp(ts).strftime("%H:%M") if ts else "",
        "published_ts": ts,
        "summary": "",
        "via": "brave",          # so a pool row can say where it came from
    }


def search_news(
    query: str,
    *,
    count: int = 20,
    freshness: str = "pd",
    country: str = "us",
    search_lang: str = "en",
    key: str | None = None,
    timeout: int | None = None,
) -> list[dict[str, Any]]:
    """One news search. Returns article dicts, or [] on any failure.

    Never raises: a paid API being down, rate-limited or misconfigured must
    degrade the morning run to its RSS sources, not abort it.
    """
    query = (query or "").strip()
    if not query:
        return []
    token = key if key is not None else api_key()
    if not token:
        console.print("  [yellow]⚠  Brave: no API key (BRAVE_API_KEY)[/yellow]")
        return []

    settings = get_settings()
    params = {
        "q": query,
        "count": max(1, min(int(count), MAX_COUNT)),
        "country": country,
        "search_lang": search_lang,
    }
    if freshness:
        params["freshness"] = freshness

    try:
        response = requests.get(
            ENDPOINT,
            params=params,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": token,
            },
            timeout=timeout or getattr(settings, "feed_timeout", 15),
        )
    except requests.RequestException as exc:
        console.print(f"  [yellow]⚠  Brave: {exc}[/yellow]")
        return []

    if response.status_code == 429:
        console.print("  [yellow]⚠  Brave: rate limited (429)[/yellow]")
        return []
    if response.status_code == 401:
        console.print("  [yellow]⚠  Brave: key rejected (401)[/yellow]")
        return []
    if not response.ok:
        console.print(
            f"  [yellow]⚠  Brave: HTTP {response.status_code} for {query!r}[/yellow]"
        )
        return []

    try:
        payload = response.json()
    except ValueError:
        console.print("  [yellow]⚠  Brave: response was not JSON[/yellow]")
        return []

    results = payload.get("results")
    if not isinstance(results, list):
        return []

    articles = []
    for result in results:
        if isinstance(result, dict):
            art = _to_article(result)
            if art:
                articles.append(art)
    return articles


def parse_queries(raw: str) -> dict[str, str]:
    """`Section = query` lines into a mapping. Blank lines and # are ignored.

    Plain text rather than JSON because this is edited by hand in a textarea,
    and a missing brace should not cost someone their morning run.
    """
    queries: dict[str, str] = {}
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        section, _, query = line.partition("=")
        section, query = section.strip(), query.strip()
        if section and query:
            queries[section] = query
    return queries


def fetch_sections(
    queries: dict[str, str],
    *,
    count: int = 20,
    freshness: str = "pd",
    country: str = "us",
    search_lang: str = "en",
    key: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Run one search per section. Returns {section: [articles]}.

    Sequential on purpose: this is a handful of calls against a paid, rate
    limited API, and the whole point is that it is cheap and predictable.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for section, query in queries.items():
        articles = search_news(
            query,
            count=count,
            freshness=freshness,
            country=country,
            search_lang=search_lang,
            key=key,
        )
        for art in articles:
            art["category"] = section
        out[section] = articles
    return out
