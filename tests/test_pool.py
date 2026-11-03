"""The candidate pool: storing screened headlines and picking through them."""

import pytest

import pool as pool_store


def _cand(title, section, score, **kw):
    base = {
        "title": title,
        "url": f"http://example.test/{title}",
        "source": "Source",
        "published": "09:00",
        "category": section,
        "content": f"{title} snippet text from the feed",
        "prefilter_score": score,
    }
    base.update(kw)
    return base


def _pool():
    return [
        _cand("a", "Tech", 90),
        _cand("b", "Tech", 80),
        _cand("c", "Soccer", 75),
        _cand("d", "Art", 60),
    ]


# ── Recording ───────────────────────────────────────────────────────────────


def test_record_preserves_rank_order(isolated_store):
    pid = pool_store.record_pool(_pool())
    loaded = pool_store.load_pool(pid)
    assert [a["title"] for a in loaded["articles"]] == ["a", "b", "c", "d"]
    assert loaded["stored"] == 4
    assert loaded["undecided"] == 4
    assert loaded["kept"] == 0


def test_record_keeps_the_fields_a_card_needs(isolated_store):
    pid = pool_store.record_pool(_pool())
    card = pool_store.load_pool(pid)["articles"][0]
    assert card["section"] == "Tech"
    assert card["prefilter_score"] == 90
    assert card["source"] == "Source"
    assert card["snippet"].startswith("a snippet")
    assert card["pick"] == "undecided"


def test_sections_are_listed_for_filtering(isolated_store):
    pid = pool_store.record_pool(_pool())
    assert pool_store.load_pool(pid)["sections"] == ["Art", "Soccer", "Tech"]


def test_unknown_pool_is_none(isolated_store):
    pool_store.init_db()
    assert pool_store.load_pool(404) is None


def test_latest_pool_id_tracks_the_newest(isolated_store):
    pool_store.init_db()
    assert pool_store.latest_pool_id() is None
    first = pool_store.record_pool(_pool())
    second = pool_store.record_pool(_pool())
    assert pool_store.latest_pool_id() == second
    assert second != first


# ── Picking ─────────────────────────────────────────────────────────────────


def test_keep_and_skip_are_tracked_separately(isolated_store):
    """Undecided must stay distinct from skipped, or progress is unreadable."""
    pid = pool_store.record_pool(_pool())
    cards = pool_store.load_pool(pid)["articles"]

    pool_store.set_picks([cards[0]["id"]], "keep")
    pool_store.set_picks([cards[1]["id"]], "skip")

    loaded = pool_store.load_pool(pid)
    assert loaded["kept"] == 1
    assert loaded["skipped"] == 1
    assert loaded["undecided"] == 2


def test_a_pick_can_be_taken_back(isolated_store):
    pid = pool_store.record_pool(_pool())
    first = pool_store.load_pool(pid)["articles"][0]["id"]

    pool_store.set_picks([first], "keep")
    assert pool_store.load_pool(pid)["kept"] == 1
    pool_store.set_picks([first], "undecided")

    loaded = pool_store.load_pool(pid)
    assert loaded["kept"] == 0
    assert loaded["undecided"] == 4


def test_picking_several_at_once(isolated_store):
    pid = pool_store.record_pool(_pool())
    ids = [a["id"] for a in pool_store.load_pool(pid)["articles"]]
    assert pool_store.set_picks(ids, "keep") == 4
    assert pool_store.load_pool(pid)["kept"] == 4
    assert pool_store.set_picks([], "keep") == 0


def test_an_invalid_pick_is_refused(isolated_store):
    pid = pool_store.record_pool(_pool())
    ids = [a["id"] for a in pool_store.load_pool(pid)["articles"]]
    with pytest.raises(ValueError):
        pool_store.set_picks(ids, "maybe")


# ── Handing picks to the build ──────────────────────────────────────────────


def test_picked_articles_returns_only_keepers_in_order(isolated_store):
    pid = pool_store.record_pool(_pool())
    cards = pool_store.load_pool(pid)["articles"]
    pool_store.set_picks([cards[2]["id"], cards[0]["id"]], "keep")
    pool_store.set_picks([cards[1]["id"]], "skip")

    picked = pool_store.picked_articles(pid)
    assert [a["title"] for a in picked] == ["a", "c"]


def test_picked_articles_seed_content_from_the_snippet(isolated_store):
    """A failed body fetch must still leave the feed's text to work with."""
    pid = pool_store.record_pool(_pool())
    first = pool_store.load_pool(pid)["articles"][0]["id"]
    pool_store.set_picks([first], "keep")

    art = pool_store.picked_articles(pid)[0]
    assert art["content"]
    assert art["rss_snippet"] == art["content"]
    assert art["category"] == "Tech"
    assert art["url"]


def test_picked_articles_is_empty_when_nothing_is_kept(isolated_store):
    """This is what makes "no book until I pick" hold."""
    pid = pool_store.record_pool(_pool())
    assert pool_store.picked_articles(pid) == []


# ── Housekeeping ────────────────────────────────────────────────────────────


def test_mark_built_links_the_issue(isolated_store):
    pid = pool_store.record_pool(_pool())
    pool_store.mark_built(pid, 77)
    assert pool_store.load_pool(pid)["built_issue_id"] == 77
    assert pool_store.list_pools(5)[0]["built_issue_id"] == 77


def test_list_pools_is_newest_first_with_tallies(isolated_store):
    first = pool_store.record_pool(_pool())
    second = pool_store.record_pool(_pool())
    ids = [a["id"] for a in pool_store.load_pool(second)["articles"]][:2]
    pool_store.set_picks(ids, "keep")

    rows = pool_store.list_pools(5)
    assert [r["id"] for r in rows] == [second, first]
    assert rows[0]["kept"] == 2
    assert rows[0]["undecided"] == 2


def test_delete_pool_takes_its_cards(isolated_store):
    pid = pool_store.record_pool(_pool())
    assert pool_store.delete_pool(pid) is True
    assert pool_store.load_pool(pid) is None
    assert pool_store.delete_pool(pid) is False


def test_prune_keeps_the_newest_pools(isolated_store):
    made = [pool_store.record_pool(_pool()) for _ in range(5)]
    assert pool_store.prune_pools(2) == 3
    assert [r["id"] for r in pool_store.list_pools(10)] == made[-1:-3:-1]
    assert pool_store.load_pool(made[0]) is None


def test_prune_zero_keeps_everything(isolated_store):
    for _ in range(3):
        pool_store.record_pool(_pool())
    assert pool_store.prune_pools(0) == 0
    assert len(pool_store.list_pools(10)) == 3


# ── The build refuses to invent a book ──────────────────────────────────────


def test_build_refuses_an_empty_pool(isolated_store, monkeypatch):
    """"No book until I pick" must be enforced, not just documented."""
    import config
    import main
    import settings_store as store

    store.init_db()
    monkeypatch.setattr(config, "_settings", None)
    pid = pool_store.record_pool(_pool())

    called = []
    monkeypatch.setattr(main, "fetch_bodies", lambda arts: called.append(1) or 0)

    assert main.run_build(pid, store.load_settings()) is None
    assert called == [], "nothing may be fetched when nothing is picked"


def test_build_refuses_when_no_pool_exists(isolated_store, monkeypatch):
    import config
    import main
    import settings_store as store

    store.init_db()
    pool_store.init_db()
    monkeypatch.setattr(config, "_settings", None)
    assert main.run_build(None, store.load_settings()) is None
