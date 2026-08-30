import html
import re
from datetime import datetime

import certifi
import feedparser
import requests
import trafilatura
from bs4 import BeautifulSoup

from config import console, get_settings


def _download_url(url: str, quiet: bool = False) -> bytes | None:
    """Fetch URL bytes using certifi-backed TLS (macOS Python venv safe)."""
    settings = get_settings()
    try:
        response = requests.get(
            url,
            timeout=settings.feed_timeout,
            headers={"User-Agent": settings.user_agent},
            verify=certifi.where(),
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.content
    except requests.RequestException as exc:
        if not quiet:
            console.print(f"  [yellow]⚠  fetch failed {url}: {exc}[/yellow]")
        return None


def clean_html(raw: str) -> str:
    """Strip HTML tags, remove boilerplate nodes, collapse whitespace."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "lxml")
    for tag in soup.find_all(["script", "style", "nav", "footer", "aside",
                               "figure", "figcaption", "noscript", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, max_chars: int | None = None) -> str:
    """Trim to max_chars, breaking on a word boundary."""
    if max_chars is None:
        max_chars = get_settings().truncate_chars
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "…"


def _normalize_body(body: str, title: str) -> str:
    """Return body text, treating title-echo snippets as empty."""
    body = (body or "").strip()
    title = (title or "").strip()
    if not body:
        return ""
    if title and body.lower() == title.lower():
        return ""
    if len(body) < 80 and title and body.lower() in title.lower():
        return ""
    return body


def has_readable_content(
    article: dict,
    min_body: int | None = None,
    min_summary: int | None = None,
) -> bool:
    """True when an article has enough body text or an AI/RSS summary to read."""
    s = get_settings()
    if min_body is None:
        min_body = s.min_body_chars
    if min_summary is None:
        min_summary = s.min_summary_chars
    body = _normalize_body(article.get("content", ""), article.get("title", ""))
    summary = (article.get("summary") or "").strip()
    return len(body) >= min_body or len(summary) >= min_summary


def filter_headline_only(
    articles: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split articles into kept vs headline-only (unreadable on Kindle)."""
    kept: list[dict] = []
    dropped: list[dict] = []
    for art in articles:
        if has_readable_content(art):
            kept.append(art)
        else:
            dropped.append(art)
    return kept, dropped


def fetch_article_content(url: str) -> str:
    """
    Fetch the full text of an article using trafilatura.
    Falls back to archive mirrors when direct fetch fails or hits a paywall.
    Returns extracted plain text, or empty string on failure.
    """
    from paywall import fetch_with_paywall_bypass

    text, _source = fetch_with_paywall_bypass(url)
    return text


def fetch_feed(
    source_name: str,
    url: str,
    max_articles: int | None = None,
) -> list[dict]:
    """Fetch one RSS feed; return a list of cleaned article dicts."""
    if max_articles is None:
        max_articles = get_settings().max_articles_per_feed
    try:
        raw = _download_url(url)
        if raw is None:
            return []
        feed = feedparser.parse(raw)
        if feed.bozo and not feed.entries:
            exc = getattr(feed, "bozo_exception", None)
            if exc:
                console.print(f"  [yellow]⚠  {source_name}: {exc}[/yellow]")
            return []
        articles = []
        for entry in feed.entries[:max_articles]:
            content = ""
            if getattr(entry, "content", None):
                content = entry.content[0].get("value", "")
            if not content:
                content = getattr(entry, "summary", "") or getattr(entry, "description", "")

            title   = html.unescape((entry.get("title") or "").strip())
            link    = entry.get("link", "")
            content_clean = clean_html(content)

            published = ""
            published_ts = 0
            if getattr(entry, "published_parsed", None):
                dt = datetime(*entry.published_parsed[:6])
                published = dt.strftime("%H:%M")
                published_ts = int(dt.timestamp())

            if title:
                articles.append({
                    "source":    source_name,
                    "category":  "",   # set by caller after fetch
                    "title":     title,
                    "content":   content_clean,
                    "rss_snippet": content_clean,
                    "url":       link,
                    "published": published,
                    "published_ts": published_ts,
                    "summary":   "",
                })
        return articles

    except Exception as exc:
        console.print(f"  [yellow]⚠  {source_name}: {exc}[/yellow]")
        return []
