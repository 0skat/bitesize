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
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

from ai_locale import epub_label, format_digest_timestamp
from config import console, get_settings, load_env, OUTPUT_DIR
from feed import (
    dedupe_articles,
    fetch_article_content,
    fetch_feed,
    filter_headline_only,
)
from paywall import log_summary, reset_stats
from gemini import (
    article_relevance,
    generate_global_cover,
    generate_section_cover,
    prefilter_by_title,
    process_articles,
)
from magazine_layers import article_rank_sort_key
from epub import generate_epub
from books import copy_to_icloud_books
from kindle import send_to_kindle
from gmail import get_gmail_threads
from gmail_processor import process_email_threads, generate_inbox_cover
from calendar_fetch import get_calendar_events
from calendar_processor import format_calendar_section, generate_calendar_cover
import settings_store
from sources_selection import build_selected_sources, sources_config_from_settings
from ui import select_integrations

_CUSTOM_COVER_SECTIONS = {"Inbox", "Calendar"}


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


def _log_dedupe(dropped: list[dict]) -> None:
    if not dropped:
        return
    by_source = Counter(art.get("source", "?") for art in dropped)
    console.print(f"  [dim]✗  dropped {len(dropped)} duplicate(s):[/dim]")
    for source, count in by_source.most_common(5):
        console.print(f"  [dim]   · {source}: {count}[/dim]")


# A threshold set too high would otherwise produce an empty book; keep this
# many top-scored stories so the run still yields something to calibrate on.
_MIN_FLOOR_ARTICLES = 5


def _apply_interest_filter(articles: list[dict]) -> list[dict]:
    """Drop stories below min_keep_score, then cap at max_articles_per_issue."""
    settings = get_settings()
    threshold = settings.min_keep_score
    cap = settings.max_articles_per_issue

    if threshold <= 0 and cap <= 0:
        return articles

    kept = articles
    if threshold > 0:
        kept = [art for art in articles if article_relevance(art) >= threshold]
        dropped = len(articles) - len(kept)
        if not kept and articles:
            kept = sorted(articles, key=article_rank_sort_key)[:_MIN_FLOOR_ARTICLES]
            console.print(
                f"  [yellow]⚠  nothing scored ≥ {threshold} — keeping the top "
                f"{len(kept)} so the issue is not empty. Lower min_keep_score.[/yellow]"
            )
        elif dropped:
            console.print(
                f"  [dim]✗  dropped {dropped} below min_keep_score={threshold}[/dim]"
            )

    if cap > 0 and len(kept) > cap:
        over = len(kept) - cap
        kept = sorted(kept, key=article_rank_sort_key)[:cap]
        console.print(
            f"  [dim]✂  capped to {cap} stories (trimmed {over})[/dim]"
        )

    return kept


def _prune_old_issues(keep: int) -> None:
    """Keep only the newest `keep` EPUBs in OUTPUT_DIR. 0 keeps everything."""
    if keep <= 0 or not OUTPUT_DIR.is_dir():
        return
    issues = sorted(
        OUTPUT_DIR.glob("*.epub"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    for stale in issues[keep:]:
        try:
            stale.unlink()
            console.print(f"  [dim]🗑  pruned {stale.name}[/dim]")
        except OSError as e:
            console.print(f"  [yellow]⚠  could not prune {stale.name}: {e}[/yellow]")


def main() -> None:
    parser = argparse.ArgumentParser(description="BiteSIze news digest for Kindle")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all categories and sources without prompting",
    )
    parser.add_argument(
        "--no-kindle",
        action="store_true",
        help="Write EPUB only; skip SMTP delivery to Kindle",
    )
    parser.add_argument(
        "--no-books",
        action="store_true",
        help="Skip copying the EPUB to the iCloud Books library",
    )
    args = parser.parse_args()

    load_env()
    settings = get_settings()
    sources_tree = settings_store.load_sources_tree(enabled_only=True)
    full_config = sources_config_from_settings(settings, sources_tree or {})
    integrations = dict(full_config.get("integrations", {}))
    if not (args.all or settings.cli_select_all_sources):
        integrations = select_integrations(full_config)

    if not sources_tree and not any(integrations.values()):
        console.print(
            "[red]Error:[/red] No RSS sources configured. "
            "Run [bold]python dashboard.py[/bold] to add feeds."
        )
        sys.exit(1)

    selected = build_selected_sources(settings, args, sources_tree or {})

    if not selected and not any(integrations.values()):
        console.print("[yellow]No sources selected — exiting.[/yellow]")
        return

    inbox_articles: list[dict] = []
    if integrations.get("gmail"):
        console.print("[cyan]Fetching Gmail…[/cyan]")
        with console.status("  Fetching threads…"):
            threads = get_gmail_threads(
                settings.gmail_max_threads,
                settings.gmail_lookback_hours,
            )
        if threads:
            console.print(f"  [green]✓[/green]  {len(threads)} threads fetched")
            with console.status("  Triaging inbox…"):
                inbox_articles = process_email_threads(threads)
            if inbox_articles:
                console.print(
                    f"  [green]✓[/green]  {len(inbox_articles)} threads kept"
                )
        else:
            console.print(
                "  [yellow]⚠  No Gmail threads — skipping Inbox section[/yellow]"
            )

    calendar_articles: list[dict] = []
    if integrations.get("google_calendar"):
        console.print("[cyan]Fetching Google Calendar…[/cyan]")
        with console.status("  Fetching events…"):
            events = get_calendar_events(
                settings.calendar_lookahead_days,
                settings.calendar_lookback_days,
            )
        total_events = len(events.get("today", [])) + len(events.get("upcoming", []))
        if total_events:
            console.print(f"  [green]✓[/green]  {total_events} events fetched")
            with console.status("  Formatting calendar…"):
                calendar_articles = format_calendar_section(events)
        else:
            console.print(
                "  [yellow]⚠  No calendar events — skipping Calendar section[/yellow]"
            )

    total_feeds = sum(len(v) for v in selected.values())

    # ── 1. Fetch feeds in parallel ────────────────────────────────────────────
    raw_sections: dict[str, list] = {cat: [] for cat in selected}
    total_raw = 0
    fetched = 0

    if selected:
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
    if selected:
        console.print(f"[green]✓[/green]  Fetched [bold]{total_raw}[/bold] raw articles")

        # ── 1.5 Drop cross-feed duplicates, then screen on titles ─────────────
        # Both run before the body fetch so a rejected story costs neither a
        # network round trip nor an AI call.
        flat_raw = [art for arts in raw_sections.values() for art in arts]
        flat_raw, dupes = dedupe_articles(flat_raw)
        _log_dedupe(dupes)

        screened, screened_out = prefilter_by_title(
            flat_raw, settings.prefilter_keep
        )
        if screened_out:
            console.print(
                f"  [dim]✗  screened out {len(screened_out)} by title "
                f"(kept {len(screened)})[/dim]"
            )

        raw_sections = {cat: [] for cat in selected}
        for art in screened:
            cat = art.get("category", "")
            if cat in raw_sections:
                raw_sections[cat].append(art)
        total_raw = sum(len(v) for v in raw_sections.values())

    # ── 2. Fetch full article content in parallel ─────────────────────────────
    if selected:
        flat_for_content = [art for arts in raw_sections.values() for art in arts]
        reset_stats()

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
                        if not art.get("rss_snippet"):
                            art["rss_snippet"] = art.get("content", "")
                        art["content"] = content
                        fetched += 1
                    prog.advance(task)

        console.print(
            f"[green]✓[/green]  Full content retrieved for "
            f"[bold]{fetched}[/bold] / {total_raw} articles"
            + (f" [dim]({total_raw - fetched} unavailable/paywalled)[/dim]"
               if fetched < total_raw else "")
        )
        log_summary(console)

    # ── 3. AI processing (Gemini) ─────────────────────────────────────────────
    kept_flat: list[dict] = []
    processed_sections: dict[str, list] = {}

    if selected:
        console.print()
        console.print("[cyan]🤖  Running AI processing…[/cyan]")

        flat_articles = [art for arts in raw_sections.values() for art in arts]

        with console.status("  Filtering and summarising articles…"):
            processed_flat = process_articles(flat_articles)

        # ── 3.5 Drop headline-only articles (no readable body or summary) ─────────
        kept_flat, dropped_flat = filter_headline_only(processed_flat)
        _log_headline_drops(dropped_flat)
        kept_flat = _apply_interest_filter(kept_flat)

        processed_sections = {cat: [] for cat in selected}
        for art in kept_flat:
            cat = art.get("category", "")
            if cat in processed_sections:
                processed_sections[cat].append(art)

        # Highest relevance first within each section (Kindle spine + indexes follow this order).
        for cat in processed_sections:
            processed_sections[cat].sort(key=article_rank_sort_key)

        total_filtered = total_raw - len(kept_flat)
        console.print(
            f"  [green]✓[/green]  [bold]{len(kept_flat)}[/bold] articles kept"
            + (f", [dim]{total_filtered} filtered[/dim]" if total_filtered else "")
        )

    if inbox_articles:
        processed_sections["Inbox"] = inbox_articles
    if calendar_articles:
        processed_sections["Calendar"] = calendar_articles

    if not kept_flat and not inbox_articles and not calendar_articles:
        console.print("[yellow]No readable articles left — exiting.[/yellow]")
        return

    # ── 4. Generate section covers ────────────────────────────────────────────
    console.print()
    console.print("[cyan]📰  Generating section covers…[/cyan]")

    section_covers: dict[str, dict] = {}
    for cat, articles in processed_sections.items():
        if cat in _CUSTOM_COVER_SECTIONS or not articles:
            continue
        with console.status(f"  {cat}…"):
            section_covers[cat] = generate_section_cover(cat, articles)
        status = "✓" if section_covers[cat] else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  {cat}")

    if inbox_articles:
        with console.status("  Inbox…"):
            section_covers["Inbox"] = generate_inbox_cover(inbox_articles)
        status = "✓" if section_covers.get("Inbox") else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  Inbox")

    if calendar_articles:
        with console.status("  Calendar…"):
            section_covers["Calendar"] = generate_calendar_cover(calendar_articles)
        status = "✓" if section_covers.get("Calendar") else "⚠ fallback"
        console.print(f"  [green]{status}[/green]  Calendar")

    # ── 5. Generate global cover ──────────────────────────────────────────────
    with console.status("  Global cover…"):
        global_cover = generate_global_cover(section_covers)
    console.print(
        f"  [green]{'✓' if global_cover else '⚠ fallback'}[/green]  Global cover"
    )

    # ── 6. Generate EPUB ──────────────────────────────────────────────────────
    console.print()
    now      = datetime.now()
    filename = f"{epub_label('digest_title')} - {format_digest_timestamp(now)}.epub"
    out_path = OUTPUT_DIR / filename

    with console.status("[cyan]Generating EPUB…[/cyan]"):
        generate_epub(processed_sections, section_covers, global_cover, out_path)

    _prune_old_issues(settings.output_keep_issues)

    total_final = sum(len(v) for v in processed_sections.values())
    console.print(f"\n[bold green]✅  Done![/bold green]  {total_final} articles saved.")
    console.print(f"   [dim]{out_path}[/dim]\n")

    # ── 7. Send to Kindle ─────────────────────────────────────────────────────
    if args.no_kindle or not settings.kindle_delivery_enabled:
        reason = "--no-kindle" if args.no_kindle else "kindle_delivery_enabled=false"
        console.print(f"[dim]  Skipped Kindle delivery ({reason}).[/dim]")
    else:
        console.print("[cyan]📬  Sending to Kindle…[/cyan]")
        send_to_kindle(out_path, settings)

    # ── 8. Copy to iCloud Books (syncs to iPhone via iCloud) ──────────────────
    if args.no_books or not settings.books_delivery_enabled:
        reason = "--no-books" if args.no_books else "books_delivery_enabled=false"
        console.print(f"[dim]  Skipped iCloud Books copy ({reason}).[/dim]")
    else:
        console.print("[cyan]📚  Copying to iCloud Books…[/cyan]")
        copy_to_icloud_books(out_path, settings)


if __name__ == "__main__":
    main()
