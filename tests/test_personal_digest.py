"""Interests-aware scoring, the keep-list, issue pruning, and Spanish labels."""

import config
import settings_store as store
from ai_locale import EPUB_LABELS, ai_summary_language_rule, epub_label


def _reload(monkeypatch):
    monkeypatch.setattr(config, "_settings", None)


# ── Settings defaults keep upstream behaviour ────────────────────────────────


def test_new_knobs_default_to_upstream_behaviour():
    s = store.Settings()
    assert s.user_interests == ""
    assert s.min_keep_score == 0
    assert s.max_articles_per_issue == 0
    assert s.output_keep_issues == 0
    assert s.summary_language == ""


# ── Relevance rule ──────────────────────────────────────────────────────────


def test_relevance_rule_without_interests_is_batch_relative(isolated_store, monkeypatch):
    store.init_db()
    _reload(monkeypatch)

    import gemini

    rule = gemini._relevance_rule()
    assert "THIS batch" in rule
    assert "at most one in five" in rule


def test_relevance_rule_with_interests_scores_the_reader(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "self-hosting and espresso")
    _reload(monkeypatch)

    import gemini

    rule = gemini._relevance_rule()
    assert "self-hosting and espresso" in rule
    assert "THIS READER" in rule
    # Absolute scoring: no curve, no forced spread.
    assert "do NOT grade on a curve" in rule
    assert "at most one in five" not in rule


def test_clustered_remap_is_skipped_when_interests_are_set(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "space launches")
    _reload(monkeypatch)

    import gemini

    called = []
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: called.append(a) or None)

    # Twenty identically scored stories would normally trigger the listwise pass.
    batch = [
        {"title": f"Story {i}", "relevance": 20, "relevance_source": "ai"}
        for i in range(20)
    ]
    gemini._maybe_remap_clustered_batch(batch)

    assert called == [], "listwise remap should not fire when interests drive the scale"
    assert all(art["relevance"] == 20 for art in batch)


def test_clustered_remap_still_fires_without_interests(isolated_store, monkeypatch):
    store.init_db()
    _reload(monkeypatch)

    import gemini

    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: None)
    batch = [
        {"title": f"Story {i}", "relevance": 20, "relevance_source": "ai"}
        for i in range(20)
    ]
    # Returns early on the empty response, but only after attempting the call.
    gemini._maybe_remap_clustered_batch(batch)


# ── Keep-list ───────────────────────────────────────────────────────────────


def _art(title, score):
    return {"title": title, "relevance": score, "relevance_source": "ai"}


def test_filter_is_a_noop_when_unconfigured(isolated_store, monkeypatch):
    store.init_db()
    _reload(monkeypatch)

    import main

    articles = [_art("a", 10), _art("b", 90)]
    assert main._apply_interest_filter(articles) == articles


def test_filter_drops_below_threshold(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 60)
    _reload(monkeypatch)

    import main

    kept = main._apply_interest_filter([_art("low", 20), _art("high", 80)])
    assert [a["title"] for a in kept] == ["high"]


def test_filter_caps_and_keeps_the_best(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("max_articles_per_issue", 2)
    _reload(monkeypatch)

    import main

    kept = main._apply_interest_filter(
        [_art("mid", 50), _art("best", 95), _art("worst", 5), _art("good", 70)]
    )
    assert [a["title"] for a in kept] == ["best", "good"]


def test_threshold_too_high_falls_back_to_a_floor(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 99)
    _reload(monkeypatch)

    import main

    articles = [_art(f"s{i}", i) for i in range(10)]
    kept = main._apply_interest_filter(articles)
    assert len(kept) == main._MIN_FLOOR_ARTICLES
    # Highest scores survive.
    assert kept[0]["title"] == "s9"


def test_threshold_and_cap_compose(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 40)
    store.set_setting("max_articles_per_issue", 2)
    _reload(monkeypatch)

    import main

    kept = main._apply_interest_filter(
        [_art("a", 95), _art("b", 10), _art("c", 60), _art("d", 45)]
    )
    assert [a["title"] for a in kept] == ["a", "c"]


# ── Pruning ─────────────────────────────────────────────────────────────────


def test_prune_keeps_the_newest_issues(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    for i in range(5):
        f = tmp_path / f"issue{i}.epub"
        f.write_text("x")
        import os

        os.utime(f, (1_700_000_000 + i * 60, 1_700_000_000 + i * 60))

    main._prune_old_issues(2)

    left = sorted(p.name for p in tmp_path.glob("*.epub"))
    assert left == ["issue3.epub", "issue4.epub"]


def test_prune_zero_keeps_everything(tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(main, "OUTPUT_DIR", tmp_path)
    for i in range(3):
        (tmp_path / f"issue{i}.epub").write_text("x")

    main._prune_old_issues(0)
    assert len(list(tmp_path.glob("*.epub"))) == 3


# ── Languages ───────────────────────────────────────────────────────────────


def test_spanish_labels_are_complete():
    assert set(EPUB_LABELS["es"]) == set(EPUB_LABELS["en"])
    assert set(EPUB_LABELS["es"]) == set(EPUB_LABELS["pt-BR"])


def test_spanish_labels_render(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "es")
    _reload(monkeypatch)

    assert epub_label("summary") == "Resumen"
    assert epub_label("tema_esportes") == "deportes"


def test_english_tag_labels_are_translated(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "en")
    _reload(monkeypatch)

    assert epub_label("tema_saúde") == "health"
    assert epub_label("tema_política") == "politics"


def test_summary_rule_defaults_to_the_global_rule(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "en")
    _reload(monkeypatch)

    assert "English" in ai_summary_language_rule()


def test_summary_rule_source_keeps_the_article_language(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("ai_language", "en")
    store.set_setting("summary_language", "source")
    _reload(monkeypatch)

    rule = ai_summary_language_rule()
    assert "SAME language" in rule
    assert "do not translate" in rule


def test_summary_rule_can_pin_a_language(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("summary_language", "es")
    _reload(monkeypatch)

    assert "Spanish" in ai_summary_language_rule()


# ── Claude transport ────────────────────────────────────────────────────────


def test_strip_code_fence_unwraps_json_objects():
    from claude_backend import _strip_code_fence

    assert _strip_code_fence('```json\n{"a": [1, 2]}\n```') == '{"a": [1, 2]}'
    assert _strip_code_fence("```\n[1, 2]\n```") == "[1, 2]"


def test_strip_code_fence_leaves_bare_json_alone():
    from claude_backend import _strip_code_fence

    assert _strip_code_fence('{"a": 1}') == '{"a": 1}'
    assert _strip_code_fence('[{"id": 0}]') == '[{"id": 0}]'


def test_strip_code_fence_ignores_a_non_wrapping_fence():
    from claude_backend import _strip_code_fence

    text = 'prose ```json\n{}\n```'
    assert _strip_code_fence(text) == text


def test_fenced_object_would_otherwise_parse_as_its_inner_array():
    """Why the fence strip exists: _extract_json tries arrays before objects."""
    from claude_backend import _strip_code_fence
    from gemini import _extract_json

    fenced = '```json\n{"headline": "H", "top_stories": [{"title": "T"}]}\n```'

    # Unstripped, the regex fallback finds top_stories and returns a list,
    # which the cover code rejects with "Expected dict, got list".
    assert isinstance(_extract_json(fenced), list)

    # Stripped, the direct parse wins and the object survives.
    parsed = _extract_json(_strip_code_fence(fenced))
    assert isinstance(parsed, dict)
    assert parsed["headline"] == "H"
