import html
import re
from datetime import datetime

import feedparser
import trafilatura
from bs4 import BeautifulSoup

from config import (
    console,
    MAX_ARTICLES_PER_FEED,
    MIN_BODY_CHARS,
    MIN_SUMMARY_CHARS,
    TRUNCATE_CHARS,
)


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


def truncate(text: str, max_chars: int = TRUNCATE_CHARS) -> str:
    """Trim to max_chars, breaking on a word boundary."""
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
    min_body: int = MIN_BODY_CHARS,
    min_summary: int = MIN_SUMMARY_CHARS,
) -> bool:
    """True when an article has enough body text or an AI/RSS summary to read."""
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
    Returns the extracted plain text, or empty string on failure (paywall, timeout, etc.).
    """
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                no_fallback=False,
                include_comments=False,
                include_tables=False,
            )
            return text or ""
    except Exception:
        pass
    return ""


def fetch_feed(source_name: str, url: str, max_articles: int = MAX_ARTICLES_PER_FEED) -> list[dict]:
    """Fetch one RSS feed; return a list of cleaned article dicts."""
    try:
        feed = feedparser.parse(url)
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
            if getattr(entry, "published_parsed", None):
                dt = datetime(*entry.published_parsed[:6])
                published = dt.strftime("%H:%M")

            if title:
                articles.append({
                    "source":    source_name,
                    "category":  "",   # set by caller after fetch
                    "title":     title,
                    "content":   content_clean,
                    "url":       link,
                    "published": published,
                    "summary":   "",
                })
        return articles

    except Exception as exc:
        console.print(f"  [yellow]⚠  {source_name}: {exc}[/yellow]")
        return []
