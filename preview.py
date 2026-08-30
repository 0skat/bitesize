"""RSS headline preview for the settings dashboard."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from feed import fetch_feed

FetchFn = Callable[..., list[dict]]


def build_source_preview(
    sources: dict,
    fetch_fn: FetchFn | None = None,
    max_headlines: int = 5,
) -> dict:
    """Return categories/feeds with recent headlines so a reader can keep or drop sources."""
    fetch = fetch_fn or fetch_feed
    categories_out: list[dict] = []
    jobs: list[tuple[dict, dict]] = []

    for cat in sources.get("categories", []):
        cat_copy = {
            "id": cat["id"],
            "name": cat["name"],
            "feeds": [],
        }
        categories_out.append(cat_copy)
        for feed in cat.get("feeds", []):
            feed_copy = {
                "id": feed["id"],
                "name": feed["name"],
                "url": feed["url"],
                "enabled": bool(feed.get("enabled", True)),
                "headlines": [],
                "error": "",
            }
            cat_copy["feeds"].append(feed_copy)
            jobs.append((feed_copy, feed))

    def _run(feed_meta: dict) -> tuple[list[dict], str]:
        try:
            articles = fetch(
                feed_meta["name"],
                feed_meta["url"],
                max_articles=max_headlines,
            )
        except Exception as exc:
            return [], str(exc)
        headlines = [
            {
                "title": art.get("title") or "",
                "url": art.get("url") or "",
                "published": art.get("published") or "",
            }
            for art in (articles or [])[:max_headlines]
            if art.get("title")
        ]
        return headlines, ""

    if jobs:
        with ThreadPoolExecutor(max_workers=min(10, len(jobs))) as pool:
            futures = {pool.submit(_run, feed): dest for dest, feed in jobs}
            for fut in as_completed(futures):
                dest = futures[fut]
                headlines, error = fut.result()
                dest["headlines"] = headlines
                dest["error"] = error

    return {"categories": categories_out}
