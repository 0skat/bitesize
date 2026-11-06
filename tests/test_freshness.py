"""Stop offering the same stories every morning.

Two independent causes, measured over seven real pools: feeds serve evergreen
and back-issue items with no age bound, and nothing remembered what had
already been offered, so anything still in a feed was a fresh candidate again
the next day. Nine URLs appeared in all seven pools.
"""

import time

import pytest

import seen
from feed import filter_by_age


def _art(title, *, url=None, age_days=None, section="Tech"):
    """An article `age_days` old, or with no date at all when age_days is None."""
    ts = 0 if age_days is None else int(time.time() - age_days * 86400)
    return {
        "title": title,
        "url": url or f"http://example.test/{title}",
        "category": section,
        "published_ts": ts,
    }


# ── The age filter ──────────────────────────────────────────────────────────


def test_zero_days_disables_the_check():
    """Upstream behaviour has to survive untouched."""
    arts = [_art("old", age_days=400), _art("new", age_days=0)]
    kept, dropped = filter_by_age(arts, 0)
    assert len(kept) == 2
    assert dropped == []


def test_older_than_the_window_is_dropped():
    arts = [_art("fresh", age_days=1), _art("april", age_days=200)]
    kept, dropped = filter_by_age(arts, 3)
    assert [a["title"] for a in kept] == ["fresh"]
    assert [a["title"] for a in dropped] == ["april"]


def test_an_article_with_no_date_is_kept():
    """Several feeds publish no dates; treating unknown as ancient kills them."""
    kept, dropped = filter_by_age([_art("undated", age_days=None)], 1)
    assert [a["title"] for a in kept] == ["undated"]
    assert dropped == []


def test_the_boundary_keeps_rather_than_drops():
    now = time.time()
    exactly = {"title": "edge", "url": "u", "published_ts": int(now - 2 * 86400)}
    kept, dropped = filter_by_age([exactly], 2, now=now)
    assert kept and not dropped


def test_the_real_offenders_are_what_this_removes():
    """Modelled on the measured pool: evergreen posts and Substack back issues."""
    arts = [
        _art("April Seed Starting", age_days=200, section="Agriculture"),
        _art("Maine Farm sheep", age_days=190, section="Agriculture"),
        _art("Crop Progress today", age_days=0, section="Agriculture"),
        _art("Import AI 474", age_days=42, section="Opinion"),
        _art("Import AI 479", age_days=1, section="Opinion"),
    ]
    kept, dropped = filter_by_age(arts, 3)
    assert {a["title"] for a in kept} == {"Crop Progress today", "Import AI 479"}
    assert len(dropped) == 3


# ── The seen record ─────────────────────────────────────────────────────────


def test_nothing_is_suppressed_before_anything_is_recorded(isolated_store):
    seen.init_db()
    arts = [_art("a"), _art("b")]
    kept, dropped = seen.filter_seen(arts)
    assert len(kept) == 2
    assert dropped == []


def test_an_offered_story_is_never_offered_again(isolated_store):
    arts = [_art("a"), _art("b")]
    assert seen.record_seen(arts) == 2

    kept, dropped = seen.filter_seen([_art("a"), _art("c")])
    assert [a["title"] for a in kept] == ["c"]
    assert [a["title"] for a in dropped] == ["a"]


def test_recording_the_same_url_twice_adds_nothing(isolated_store):
    seen.record_seen([_art("a")])
    assert seen.record_seen([_art("a")]) == 0
    assert seen.count_seen() == 1


def test_re_recording_does_not_extend_the_suppression(isolated_store):
    """The first sighting's date must win, or expiry slides forever."""
    seen.record_seen([_art("a")])
    with_old_date = "2020-01-01T00:00:00"
    from settings_store import _get_connection

    with _get_connection() as conn:
        conn.execute("UPDATE seen_urls SET first_seen = ?", (with_old_date,))

    seen.record_seen([_art("a")])  # seen again today
    assert seen.prune_seen(30) == 1, "the original date should still be prunable"


def test_an_article_without_a_url_is_kept(isolated_store):
    seen.record_seen([_art("a")])
    nameless = {"title": "no url", "url": "", "category": "Tech"}
    kept, dropped = seen.filter_seen([nameless])
    assert kept == [nameless]
    assert dropped == []


def test_the_window_bounds_how_far_back_it_remembers(isolated_store):
    seen.record_seen([_art("a")])
    from settings_store import _get_connection

    with _get_connection() as conn:
        conn.execute("UPDATE seen_urls SET first_seen = '2020-01-01T00:00:00'")

    # Inside a 7-day window that old sighting is irrelevant...
    kept, dropped = seen.filter_seen([_art("a")], 7)
    assert [a["title"] for a in kept] == ["a"]
    # ...but with no window it is still on record.
    kept, dropped = seen.filter_seen([_art("a")], 0)
    assert [a["title"] for a in dropped] == ["a"]


def test_forget_lets_one_story_back_in(isolated_store):
    art = _art("a")
    seen.record_seen([art])
    assert seen.forget(art["url"]) is True
    assert seen.filter_seen([art])[0] == [art]
    assert seen.forget(art["url"]) is False


def test_prune_drops_only_what_is_past_the_window(isolated_store):
    seen.record_seen([_art("old"), _art("new")])
    from settings_store import _get_connection

    with _get_connection() as conn:
        conn.execute(
            "UPDATE seen_urls SET first_seen = '2020-01-01T00:00:00' WHERE url LIKE ?",
            ("%old",),
        )
    assert seen.prune_seen(30) == 1
    assert seen.count_seen() == 1
    assert seen.prune_seen(0) == 0, "0 must keep everything"


# ── Both, in the pipeline ───────────────────────────────────────────────────


def test_the_pool_remembers_what_it_offered(isolated_store, monkeypatch):
    """A second run must not re-offer the first run's headlines."""
    import config
    import main
    import settings_store as store

    store.init_db()
    store.set_setting("seen_memory_days", "30")
    monkeypatch.setattr(config, "_settings", None)
    settings = store.load_settings()
    assert settings.seen_memory_days == 30

    batch = [_art("a"), _art("b"), _art("c")]
    monkeypatch.setattr(main, "fetch_and_screen", lambda sel, s: list(batch))

    first = main.run_pool({"Tech": {}}, settings)
    assert first is not None

    import pool as pool_store

    assert pool_store.load_pool(first)["stored"] == 3

    # The same headlines come round again; none of them should be stored.
    kept, dropped = seen.filter_seen(batch, settings.seen_memory_days)
    assert kept == []
    assert len(dropped) == 3


def test_screened_out_headlines_are_not_remembered(isolated_store, monkeypatch):
    """Only what was *offered* is suppressed; the screen's rejects may return."""
    import config
    import main
    import settings_store as store

    store.init_db()
    store.set_setting("seen_memory_days", "30")
    monkeypatch.setattr(config, "_settings", None)
    settings = store.load_settings()

    offered = [_art("shown")]
    monkeypatch.setattr(main, "fetch_and_screen", lambda sel, s: list(offered))
    main.run_pool({"Tech": {}}, settings)

    never_shown = _art("screened-out")
    kept, _ = seen.filter_seen([never_shown], settings.seen_memory_days)
    assert kept == [never_shown]


def test_the_memory_is_off_by_default(isolated_store, monkeypatch):
    """Zero means upstream behaviour: nothing recorded, nothing suppressed."""
    import config
    import main
    import settings_store as store

    store.init_db()
    monkeypatch.setattr(config, "_settings", None)
    settings = store.load_settings()
    assert settings.seen_memory_days == 0

    batch = [_art("a")]
    monkeypatch.setattr(main, "fetch_and_screen", lambda sel, s: list(batch))
    main.run_pool({"Tech": {}}, settings)
    assert seen.count_seen() == 0
