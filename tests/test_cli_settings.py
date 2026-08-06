import argparse

import settings_store as store
from settings_store import Settings
from sources_selection import build_selected_sources


def test_build_selected_sources_from_db(isolated_store, monkeypatch):
    store.init_db()
    cat_id = store.add_category("Tech")
    store.add_feed(cat_id, "HN", "https://hnrss.org/frontpage")
    store.update_settings({"cli_select_all_sources": True})
    settings = store.load_settings()

    class Args:
        all = False

    selected = build_selected_sources(
        settings,
        Args(),
        store.load_sources_tree(enabled_only=True),
    )
    assert selected == {"Tech": {"HN": "https://hnrss.org/frontpage"}}


def test_build_selected_sources_respects_disabled_feed(isolated_store):
    store.init_db()
    cat_id = store.add_category("Tech")
    feed_id = store.add_feed(cat_id, "HN", "https://hnrss.org/frontpage")
    store.update_feed(feed_id, enabled=False)
    store.update_settings({"cli_select_all_sources": True})
    settings = store.load_settings()

    class Args:
        all = False

    selected = build_selected_sources(
        settings,
        Args(),
        store.load_sources_tree(enabled_only=True),
    )
    assert selected == {}
