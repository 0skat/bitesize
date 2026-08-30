"""Measure trafilatura vs readability-lxml on the same GET, for real URLs.

Task 2 experiment (see docs/superpowers/plans/2026-08-30-tags-reader-scoring.md).
Does NOT run the daily digest pipeline: it only downloads article pages and
runs the two static extractors, to decide whether `reader_extract.py` is
worth wiring into `paywall.fetch_with_paywall_bypass`.

Usage:
    .venv/bin/python scripts/measure_reader_extract.py [--limit N] [--out PATH]

Picks up to N articles per configured RSS source (spread across the
Brazil / Tech / World categories in sources.json) until it has a sample of
roughly 15-25 URLs, downloads each once, then reports for both extractors:
character count and whether it clears `min_body_chars`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feed
import paywall
import reader_extract
from config import get_settings

DEFAULT_SAMPLE_SIZE = 20
PER_SOURCE_CAP = 2


def collect_urls(sample_size: int) -> list[tuple[str, str, str]]:
    """Return [(category, source, url), ...] pulled from sources.json feeds.

    Round-robins one feed per category at a time so a small sample still
    covers Brazil/Tech/World, instead of exhausting one category first.
    """
    sources = json.loads(Path("sources.json").read_text(encoding="utf-8"))
    categories = sources.get("categories", {})
    per_category_sources = {
        category: list(feeds.items()) for category, feeds in categories.items()
    }
    max_sources = max((len(v) for v in per_category_sources.values()), default=0)

    picked: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    for i in range(max_sources):
        for category, feeds in per_category_sources.items():
            if i >= len(feeds) or len(picked) >= sample_size:
                continue
            source_name, feed_url = feeds[i]
            articles = feed.fetch_feed(source_name, feed_url, max_articles=PER_SOURCE_CAP)
            for art in articles:
                url = art.get("url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                picked.append((category, source_name, url))
                if len(picked) >= sample_size:
                    break
        if len(picked) >= sample_size:
            break
    return picked


def measure_one(url: str, min_chars: int) -> dict:
    raw = feed._download_url(url, quiet=True)
    if raw is None:
        return {
            "url": url,
            "fetched": False,
            "trafilatura_chars": 0,
            "trafilatura_usable": False,
            "readability_chars": 0,
            "readability_usable": False,
        }

    trafilatura_text = paywall._extract_text(raw)
    readability_text = reader_extract.extract_article_text(raw)

    return {
        "url": url,
        "fetched": True,
        "trafilatura_chars": len(trafilatura_text),
        "trafilatura_usable": len(trafilatura_text) >= min_chars,
        "readability_chars": len(readability_text),
        "readability_usable": len(readability_text) >= min_chars,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--out", type=Path, default=None, help="Optional JSON dump path")
    args = parser.parse_args()

    min_chars = get_settings().min_body_chars
    targets = collect_urls(args.limit)
    print(f"Sampled {len(targets)} URLs across enabled feeds (min_body_chars={min_chars})\n")

    rows = []
    for category, source_name, url in targets:
        result = measure_one(url, min_chars)
        result["category"] = category
        result["source"] = source_name
        rows.append(result)
        status = "ok" if result["fetched"] else "FETCH FAILED"
        print(
            f"[{category:6}] {source_name:16} traf={result['trafilatura_chars']:6} "
            f"({'usable' if result['trafilatura_usable'] else 'teaser'})  "
            f"read={result['readability_chars']:6} "
            f"({'usable' if result['readability_usable'] else 'teaser'})  {status}"
        )

    fetched = [r for r in rows if r["fetched"]]
    n = len(fetched)
    traf_usable = sum(1 for r in fetched if r["trafilatura_usable"])
    read_usable = sum(1 for r in fetched if r["readability_usable"])
    both = sum(1 for r in fetched if r["trafilatura_usable"] and r["readability_usable"])
    read_only = sum(1 for r in fetched if r["readability_usable"] and not r["trafilatura_usable"])
    traf_only = sum(1 for r in fetched if r["trafilatura_usable"] and not r["readability_usable"])

    print("\n--- summary ---")
    print(f"fetched:               {n}/{len(rows)}")
    print(f"trafilatura usable:    {traf_usable}/{n}")
    print(f"readability usable:    {read_usable}/{n}")
    print(f"both usable:           {both}/{n}")
    print(f"readability-only wins: {read_only}/{n}")
    print(f"trafilatura-only wins: {traf_only}/{n}")
    if traf_usable:
        delta_pct = round(100.0 * (read_usable - traf_usable) / traf_usable, 1)
        print(f"readability vs trafilatura usable-count delta: {delta_pct:+}%")

    if args.out:
        args.out.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nWrote raw results to {args.out}")


if __name__ == "__main__":
    main()
