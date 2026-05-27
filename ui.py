import sys

import questionary
from rich.panel import Panel

from config import console


def all_sources(config: dict) -> dict[str, dict[str, str]]:
    """Return every configured RSS source under each category (used by ``--all``)."""
    out: dict[str, dict[str, str]] = {}
    for cat, feeds in config.get("categories", {}).items():
        if isinstance(feeds, dict) and feeds:
            out[cat] = dict(feeds)
    return out


def select_sources(config: dict) -> dict[str, dict[str, str]]:
    """Present checkbox prompts; return {category: {name: url}} for chosen sources."""
    all_cats = list(config["categories"].keys())

    console.print()
    console.print(Panel.fit(
        "[bold cyan]📰  BiteSIze[/bold cyan]  [dim]AI-powered news digest for Kindle[/dim]",
        border_style="cyan",
    ))
    console.print()

    selected_cats = questionary.checkbox(
        "Select categories for today's digest:",
        choices=[questionary.Choice(c, checked=True) for c in all_cats],
    ).ask()

    if not selected_cats:
        console.print("[yellow]Nothing selected — exiting.[/yellow]")
        sys.exit(0)

    result: dict[str, dict[str, str]] = {}
    for cat in selected_cats:
        all_sources = config["categories"][cat]
        names = list(all_sources.keys())

        chosen = questionary.checkbox(
            f"  {cat} — pick sources:",
            choices=[questionary.Choice(n, checked=True) for n in names],
        ).ask()

        if chosen:
            result[cat] = {n: all_sources[n] for n in chosen}

    console.print()
    return result


def select_integrations(config: dict) -> dict[str, bool]:
    """Ask user which integrations to include. Returns {name: bool}."""
    integrations = config.get("integrations", {})
    if not integrations:
        return {}

    labels = {
        "gmail":           "Gmail inbox digest",
        "google_calendar": "Google Calendar",
    }
    choices = list(integrations.keys())

    enabled = questionary.checkbox(
        "Include integrations?",
        choices=[
            questionary.Choice(labels.get(k, k), value=k, checked=integrations[k])
            for k in choices
        ],
    ).ask() or []

    return {k: (k in enabled) for k in choices}
