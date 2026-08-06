"""Helpers for building the CLI source selection from SQLite settings."""

from __future__ import annotations

import argparse

from settings_store import Settings
from ui import all_sources, select_sources


def sources_config_from_settings(
    settings: Settings,
    sources_tree: dict[str, dict[str, str]],
) -> dict:
    return {
        "categories": sources_tree,
        "integrations": {
            "gmail": settings.integration_gmail,
            "google_calendar": settings.integration_google_calendar,
        },
    }


def build_selected_sources(
    settings: Settings,
    args: argparse.Namespace,
    sources_tree: dict[str, dict[str, str]],
) -> dict[str, dict[str, str]]:
    config = sources_config_from_settings(settings, sources_tree)
    if args.all or settings.cli_select_all_sources:
        return all_sources(config)
    return select_sources(config)
