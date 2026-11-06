#!/usr/bin/env python3
"""See what Brave Search actually returns, before wiring it into a run.

Writes nothing, stores nothing, makes no AI calls. One HTTP request per
section, so a full probe of ten sections costs about five cents' worth of the
monthly credit.

    ./scripts/brave-probe.py                      # every configured query
    ./scripts/brave-probe.py Agriculture Soccer   # just these sections
    ./scripts/brave-probe.py --query "Liverpool transfer news"
    ./scripts/brave-probe.py --freshness pw --count 10
    ./scripts/brave-probe.py --seen               # mark what is already known

The key comes from BRAVE_API_KEY or the brave_api_key setting.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import brave_news  # noqa: E402
import settings_store as store  # noqa: E402
from config import load_env  # noqa: E402

# A starting point when brave_queries is empty, matching the sections this
# install already has. Edit the setting to make them yours.
DEFAULT_QUERIES = {
    "Agriculture": "agriculture farming crops livestock news",
    "Tech": "technology industry news",
    "Science": "science research biology chemistry news",
    "Soccer": "Premier League Champions League Liverpool transfer news",
    "World": "world news site:reuters.com",
    "US Politics": "United States politics news",
    "México": "México noticias política",
    "Art": "art exhibition museum news",
    "Opinion": "AI economy opinion essay analysis",
    "Español": "noticias internacionales español",
}


def human_age(ts: int) -> str:
    if not ts:
        return "unknown"
    hours = (time.time() - ts) / 3600
    if hours < 1:
        return f"{int(hours * 60)}m"
    if hours < 48:
        return f"{int(hours)}h"
    return f"{int(hours / 24)}d"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sections", nargs="*", help="limit to these sections")
    ap.add_argument("--query", help="run one ad-hoc query instead")
    ap.add_argument("--freshness", default=None, choices=sorted(brave_news.FRESHNESS))
    ap.add_argument("--count", type=int, default=None)
    ap.add_argument("--seen", action="store_true",
                    help="flag results already offered in an earlier pool")
    args = ap.parse_args()

    load_env()
    settings = store.load_settings()

    key = brave_news.api_key(settings)
    if not key:
        print("No Brave API key. Set BRAVE_API_KEY in .env, or brave_api_key "
              "in the dashboard.", file=sys.stderr)
        return 1
    print(f"key: …{key[-4:]}  ({len(key)} chars)")

    count = args.count or settings.brave_count
    freshness = args.freshness or settings.brave_freshness
    print(f"freshness={freshness} ({brave_news.FRESHNESS.get(freshness, '?')})  "
          f"count={count}  country={settings.brave_country}  "
          f"lang={settings.brave_search_lang}")

    if args.query:
        queries = {"ad-hoc": args.query}
    else:
        queries = brave_news.parse_queries(settings.brave_queries) or DEFAULT_QUERIES
        if not settings.brave_queries:
            print("(brave_queries is empty — using the built-in starting set)")
        if args.sections:
            wanted = {s.lower() for s in args.sections}
            queries = {k: v for k, v in queries.items() if k.lower() in wanted}
            if not queries:
                print(f"No such section. Known: {', '.join(sorted(queries))}",
                      file=sys.stderr)
                return 1

    known: set[str] = set()
    if args.seen:
        import seen as seen_store

        known = seen_store.seen_urls(settings.seen_memory_days)
        print(f"({len(known)} URLs already on record)")

    total = fresh = 0
    for section, query in queries.items():
        print(f"\n\033[1m{section}\033[0m  q={query!r}")
        started = time.time()
        results = brave_news.search_news(
            query,
            count=count,
            freshness=freshness,
            country=settings.brave_country,
            search_lang=settings.brave_search_lang,
            key=key,
        )
        elapsed = time.time() - started
        print(f"  {len(results)} results in {elapsed:.1f}s")
        total += len(results)

        for art in results:
            mark = "  "
            if art["url"] in known:
                mark = "=="        # already offered in a previous pool
            else:
                fresh += 1
            print(f"  {mark} [{human_age(art['published_ts']):>7}] "
                  f"{art['source'][:22]:<22} {art['title'][:68]}")

        undated = sum(1 for a in results if not a["published_ts"])
        if undated:
            print(f"  [dim]{undated} with no readable date[/dim]")

    print(f"\n{len(queries)} request(s), {total} results"
          + (f", {fresh} not previously offered" if args.seen else ""))
    print(f"approx cost: ${len(queries) * 5 / 1000:.3f} "
          f"(Search plan, $5 per 1,000 requests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
