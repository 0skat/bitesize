#!/usr/bin/env python3
"""
BiteSIze — AI-powered personal news digest for Kindle.

Usage:
    python3 main.py

Interactively select categories and sources, then fetches RSS feeds,
filters ads and generates AI summaries via Gemini CLI, and produces
a Kindle-friendly EPUB in the ./output/ folder.
"""

import argparse
import json
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from config import console, load_env, SOURCES_FILE, OUTPUT_DIR
from feed import fetch_feed, fetch_article_content, filter_headline_only
from gemini import process_articles, generate_section_cover, generate_global_cover
from epub import generate_epub
from kindle import send_to_kindle
from ui import all_sources, select_sources


def _log_headline_drops(dropped: list[dict]) -> None:
    if not dropped:
        return
    by_source = Counter(art["source"] for art in dropped)
    console.print(
        f"  [dim]✗  dropped {len(dropped)} headline-only "
        f"(no body text or summary):[/dim]"
    )
    for source, count in by_source.most_common():
        console.print(f"  [dim]   · {source}: {count}[/dim]")


def main() -> None:
    parser = argparse.ArgumentParser(description="BiteSIze news digest for Kindle")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all categories and sources without prompting",
    )
    args = parser.parse_args()

    load_env()

    if not SOURCES_FILE.exists():
        console.print(f"[red]Error:[/red] sources.json not found at {SOURCES_FILE}")
        sys.exit(1)

    config = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
    selected = all_sources(config) if args.all else select_sources(config)

    if not selected:
        console.print("[yellow]No sources selected — exiting.[/yellow]")
        return

    total_feeds = sum(len(v) for v in selected.values())

    # ── 1. Fetch feeds in parallel ────────────────────────────────────────────
    raw_sections: dict[str, list] = {cat: [] for cat in selected}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task(f"Fetching {total_feeds} feeds…", total=total_feeds)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = {
                pool.submit(fetch_feed, name, url): cat
                for cat, srcs in selected.items()
                for name, url in srcs.items()
            }
            for fut in as_completed(futures):
                cat = futures[fut]
                articles = fut.result()
                for art in articles:
                    art["category"] = cat
                raw_sections[cat].extend(articles)
                prog.advance(task)

    total_raw = sum(len(v) for v in raw_sections.values())
    console.print(f"[green]✓[/green]  Fetched [bold]{total_raw}[/bold] raw articles")

    # ── 2. Fetch full article content in parallel ─────────────────────────────
    flat_for_content = [art for arts in raw_sections.values() for art in arts]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as prog:
        task = prog.add_task(
            f"Fetching full content for {total_raw} articles…", total=total_raw
        )
        with ThreadPoolExecutor(max_workers=10) as pool:
            future_to_art = {
                pool.submit(fetch_article_content, art["url"]): art
                for art in flat_for_content
            }
            fetched = 0
            for fut in as_completed(future_to_art):
                art = future_to_art[fut]
                content = fut.result()
                if content:
                    art["content"] = content
                    fetched += 1
                prog.advance(task)

    console.print(
        f"[green]✓[/green]  Full content retrieved for "
        f"[bold]{fetched}[/bold] / {total_raw} articles"
        + (f" [dim]({total_raw - fetched} unavailable/paywalled)[/dim]"
           if fetched < total_raw else "")
    )

    # ── 3. AI processing (Gemini) ─────────────────────────────────────────────
    console.print()
    console.print("[cyan]🤖  Running AI processing…[/cyan]")

    flat_articles = [art for arts in raw_sections.values() for art in arts]

    with console.status("  Filtering and summarising articles…"):
        processed_flat = process_articles(flat_articles)

    # ── 3.5 Drop headline-only articles (no readable body or summary) ─────────
    kept_flat, dropped_flat = filter_headline_only(processed_flat)
    _log_headline_drops(dropped_flat)

    processed_sections: dict[str, list] = {cat: [] for cat in selected}
    for art in kept_flat:
        cat = art.get("category", "")
        if cat in processed_sections:
            processed_sections[cat].append(art)

    total_filtered = total_raw - len(kept_flat)
    console.print(
        f"  [green]✓[/green]  [bold]{len(kept_flat)}[/bold] articles kept"
        + (f", [dim]{total_filtered} filtered[/dim]" if total_filtered else "")
    )

    if not kept_flat:
        console.print("[yellow]No readable articles left — exiting.[/yellow]")
        return

    # ── 4. Generate section covers ────────────────────────────────────────────
    console.print()
    console.print("[cyan]📰  Generating section covers…[/cyan]")

    section_covers: dict[str, dict] = {}
    for cat, articles in processed_sections.items():
        if not articles:
            continue
        with console.status(f"  {cat}…"):
            section_covers[cat] = generate_section_cover(cat, articles)
        status = "✓" if section_covers[cat] else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  {cat}")

    # ── 5. Generate global cover ──────────────────────────────────────────────
    with console.status("  Global cover…"):
        global_cover = generate_global_cover(section_covers)
    console.print(
        f"  [green]{'✓' if global_cover else '⚠ fallback'}[/green]  Global cover"
    )

    # ── 6. Generate EPUB ──────────────────────────────────────────────────────
    console.print()
    now      = datetime.now()
    filename = f"News Digest - {now.strftime('%B %d %Y %H%M')}.epub"
    out_path = OUTPUT_DIR / filename

    with console.status("[cyan]Generating EPUB…[/cyan]"):
        generate_epub(processed_sections, section_covers, global_cover, out_path)

    total_final = sum(len(v) for v in processed_sections.values())
    console.print(f"\n[bold green]✅  Done![/bold green]  {total_final} articles saved.")
    console.print(f"   [dim]{out_path}[/dim]\n")

    # ── 7. Send to Kindle ─────────────────────────────────────────────────────
    console.print("[cyan]📬  Sending to Kindle…[/cyan]")
    send_to_kindle(out_path)


if __name__ == "__main__":
    main()
