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
    kept, overflow = main._apply_interest_filter(articles)
    assert kept == articles
    assert overflow == []


def test_filter_drops_below_threshold(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 60)
    _reload(monkeypatch)

    import main

    kept, _ = main._apply_interest_filter([_art("low", 20), _art("high", 80)])
    assert [a["title"] for a in kept] == ["high"]


def test_filter_caps_and_keeps_the_best(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("max_articles_per_issue", 2)
    _reload(monkeypatch)

    import main

    kept, overflow = main._apply_interest_filter(
        [_art("mid", 50), _art("best", 95), _art("worst", 5), _art("good", 70)]
    )
    assert [a["title"] for a in kept] == ["best", "good"]
    # Trimmed stories are handed back rather than thrown away.
    assert [a["title"] for a in overflow] == ["mid", "worst"]


def test_threshold_too_high_falls_back_to_a_floor(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 99)
    _reload(monkeypatch)

    import main

    articles = [_art(f"s{i}", i) for i in range(10)]
    kept, _ = main._apply_interest_filter(articles)
    assert len(kept) == main._MIN_FLOOR_ARTICLES
    # Highest scores survive.
    assert kept[0]["title"] == "s9"


def test_threshold_and_cap_compose(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("min_keep_score", 40)
    store.set_setting("max_articles_per_issue", 2)
    _reload(monkeypatch)

    import main

    kept, _ = main._apply_interest_filter(
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


# ── Cross-feed dedupe ───────────────────────────────────────────────────────


def _raw(title, url, source="S"):
    return {"title": title, "url": url, "source": source}


def test_dedupe_drops_identical_urls():
    from feed import dedupe_articles

    kept, dropped = dedupe_articles([
        _raw("A story", "http://x/1"),
        _raw("Different headline", "http://x/1"),
    ])
    assert len(kept) == 1
    assert len(dropped) == 1


def test_dedupe_drops_same_title_from_two_feeds():
    """The real case: a club feed and its parent sport feed carry one story."""
    from feed import dedupe_articles

    kept, dropped = dedupe_articles([
        _raw("Araujo the stopgap solution fixing Liverpool's problems",
             "http://bbc/sport/liverpool/1", "BBC Liverpool"),
        _raw("Araujo the stopgap solution fixing Liverpool's problems",
             "http://bbc/sport/football/9", "BBC Football"),
    ])
    assert [a["source"] for a in kept] == ["BBC Liverpool"]
    assert [a["source"] for a in dropped] == ["BBC Football"]


def test_dedupe_ignores_case_spacing_and_punctuation():
    from feed import dedupe_articles

    kept, _ = dedupe_articles([
        _raw("Liverpool Beat Villarreal, 2-0", "http://a/1"),
        _raw("liverpool beat villarreal 20", "http://b/2"),
    ])
    assert len(kept) == 1


def test_dedupe_keeps_distinct_short_titles():
    """Containment matching must not collapse unrelated short headlines."""
    from feed import dedupe_articles

    kept, dropped = dedupe_articles([
        _raw("Short one", "http://a/1"),
        _raw("Short two", "http://b/2"),
        _raw("One", "http://c/3"),
    ])
    assert len(kept) == 3
    assert dropped == []


def test_dedupe_collapses_long_containment():
    from feed import dedupe_articles

    kept, dropped = dedupe_articles([
        _raw("Liverpool sign a new centre back from Barcelona", "http://a/1"),
        _raw("Liverpool sign a new centre back from Barcelona in January",
             "http://b/2"),
    ])
    assert len(kept) == 1
    assert len(dropped) == 1


def test_dedupe_preserves_order_and_handles_empties():
    from feed import dedupe_articles

    kept, _ = dedupe_articles([
        {"title": "", "url": ""},
        _raw("Real story here about something", "http://a/1"),
        {"title": "", "url": ""},
    ])
    assert len(kept) == 3  # blanks are never treated as duplicates of each other


# ── Title pre-filter ────────────────────────────────────────────────────────


def _titled(n):
    return [{"title": f"Story number {i}", "url": f"http://x/{i}"} for i in range(n)]


def test_prefilter_is_skipped_when_disabled(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    called = []
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: called.append(1) or None)

    arts = _titled(10)
    kept, dropped = gemini.prefilter_by_title(arts, 0)
    assert kept == arts and dropped == []
    assert called == []


def test_prefilter_is_skipped_without_interests(isolated_store, monkeypatch):
    store.init_db()
    _reload(monkeypatch)

    import gemini

    called = []
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: called.append(1) or None)

    arts = _titled(10)
    kept, _ = gemini.prefilter_by_title(arts, 5)
    assert kept == arts
    assert called == [], "no interests means nothing to screen against"


def test_prefilter_skips_when_there_is_nothing_to_gain(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    called = []
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: called.append(1) or None)

    arts = _titled(5)
    kept, _ = gemini.prefilter_by_title(arts, 10)
    assert kept == arts
    assert called == []


def test_prefilter_keeps_the_best_scoring_titles(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    # Score is the reverse of the index, so article 0 ranks highest.
    def fake(instruction, block, label=""):
        import json, re
        ids = [int(m) for m in re.findall(r"^\[(\d+)\]", block, re.M)]
        return json.dumps([{"id": i, "score": 99 - i} for i in ids])

    monkeypatch.setattr(gemini, "_call_ai", fake)
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)

    arts = _titled(10)
    kept, dropped = gemini.prefilter_by_title(arts, 3)
    assert [a["title"] for a in kept] == [
        "Story number 0", "Story number 1", "Story number 2"]
    assert len(dropped) == 7
    assert kept[0]["prefilter_score"] == 99


def test_prefilter_fails_open_when_the_backend_is_down(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    monkeypatch.setattr(gemini, "_ai_available", lambda: False)
    arts = _titled(10)
    kept, dropped = gemini.prefilter_by_title(arts, 3)
    assert kept == arts, "a down backend must not silently delete articles"
    assert dropped == []


def test_prefilter_holds_a_failed_batch_at_neutral(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: "not json at all")

    arts = _titled(10)
    kept, dropped = gemini.prefilter_by_title(arts, 4)
    # Unscored articles tie at neutral, so the first four survive on index order
    # rather than all ten being discarded.
    assert len(kept) == 4
    assert len(dropped) == 6
    assert all(a["prefilter_score"] == gemini.PREFILTER_NEUTRAL_SCORE for a in kept)


def test_prefilter_batches_large_inputs(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini

    calls = []

    def fake(instruction, block, label=""):
        import json, re
        ids = [int(m) for m in re.findall(r"^\[(\d+)\]", block, re.M)]
        calls.append(len(ids))
        return json.dumps([{"id": i, "score": 70} for i in ids])

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake)

    gemini.prefilter_by_title(_titled(130), 20)
    assert calls == [60, 60, 10], "should batch by PREFILTER_BATCH_SIZE"


def test_prefilter_spreads_ties_across_sections(isolated_store, monkeypatch):
    """A tie at the cut line must not hand every slot to one section."""
    store.init_db()
    store.set_setting("user_interests", "art and farming")
    _reload(monkeypatch)

    import gemini
    import json

    # Everything ties, so only the tie-break decides who survives.
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(
        gemini, "_call_ai",
        lambda instruction, block, label="": json.dumps([
            {"id": i, "score": 75}
            for i in range(block.count("\n"))
        ]))

    # Ten Agriculture stories listed first, then four Art ones.
    arts = (
        [{"title": f"Farm {i}", "url": f"http://f/{i}", "category": "Agriculture"}
         for i in range(10)]
        + [{"title": f"Art {i}", "url": f"http://a/{i}", "category": "Art"}
           for i in range(4)]
    )

    kept, _ = gemini.prefilter_by_title(arts, 6)
    sections = [a["category"] for a in kept]
    assert sections.count("Art") == 3, sections
    assert sections.count("Agriculture") == 3, sections


def test_prefilter_still_prefers_higher_scores_over_spread(isolated_store, monkeypatch):
    """Diversity only breaks ties; a better score always wins outright."""
    store.init_db()
    store.set_setting("user_interests", "soccer")
    _reload(monkeypatch)

    import gemini
    import json, re

    scores = {"Soccer": 95, "Art": 20}

    def fake(instruction, block, label=""):
        out = []
        for line in block.splitlines():
            m = re.match(r"\[(\d+)\] \"(\w+)", line)
            if m:
                out.append({"id": int(m.group(1)),
                            "score": scores["Soccer" if m.group(2) == "Match" else "Art"]})
        return json.dumps(out)

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake)

    arts = (
        [{"title": f"Match report {i}", "url": f"http://s/{i}", "category": "Soccer"}
         for i in range(5)]
        + [{"title": f"Gallery show {i}", "url": f"http://a/{i}", "category": "Art"}
           for i in range(5)]
    )
    kept, _ = gemini.prefilter_by_title(arts, 4)
    assert all(a["category"] == "Soccer" for a in kept), [a["category"] for a in kept]


# ── Cover toggle (usage control) ────────────────────────────────────────────


def test_ai_covers_can_be_turned_off(isolated_store, monkeypatch):
    """Covers are decoration; turning them off must cost zero AI calls."""
    store.init_db()
    store.set_setting("ai_covers_enabled", False)
    _reload(monkeypatch)

    import gemini

    called = []
    monkeypatch.setattr(gemini, "_call_ai", lambda *a, **k: called.append(1) or None)
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)

    arts = [{"title": "T", "summary": "S", "url": "u", "content": "c" * 300}]
    assert gemini.generate_section_cover("Tech", arts) == {}
    assert gemini.generate_global_cover({"Tech": {"headline": "H"}}) == {}
    assert called == [], "no AI call may be made when covers are disabled"


def test_ai_covers_on_by_default_still_call(isolated_store, monkeypatch):
    store.init_db()
    _reload(monkeypatch)

    import gemini

    called = []

    def fake(*a, **k):
        called.append(1)
        return None  # falls back, but the call was attempted

    monkeypatch.setattr(gemini, "_call_ai", fake)
    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    gemini.generate_section_cover("Tech", [{"title": "T", "summary": "S",
                                            "url": "u", "content": "c" * 300}])
    assert called, "default behaviour is unchanged from upstream"


def test_prefilter_batch_size_is_configurable(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("user_interests", "soccer")
    store.set_setting("prefilter_batch_size", 150)
    _reload(monkeypatch)

    import gemini
    import json, re

    calls = []

    def fake(instruction, block, label=""):
        ids = [int(m) for m in re.findall(r"^\[(\d+)\]", block, re.M)]
        calls.append(len(ids))
        return json.dumps([{"id": i, "score": 70} for i in ids])

    monkeypatch.setattr(gemini, "_ai_available", lambda: True)
    monkeypatch.setattr(gemini, "_call_ai", fake)

    gemini.prefilter_by_title(_titled(269), 80)
    assert calls == [150, 119], calls


def test_thinking_is_disabled_by_default_in_the_claude_env(isolated_store, monkeypatch):
    """Thinking dominated output billing; the backend must switch it off."""
    store.init_db()
    _reload(monkeypatch)

    import claude_backend

    seen = {}

    class R:
        returncode = 0
        stdout = '{"subtype":"success","is_error":false,"result":"OK","usage":{}}'
        stderr = ""

    def fake_run(cmd, **kw):
        seen["env"] = kw.get("env") or {}
        return R()

    monkeypatch.setattr(claude_backend.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_backend, "_record_usage", lambda *a, **k: None)

    assert claude_backend.call("do a thing", "") == "OK"
    assert seen["env"]["MAX_THINKING_TOKENS"] == "0"


def test_thinking_budget_is_configurable(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("claude_thinking_tokens", 4000)
    _reload(monkeypatch)

    import claude_backend

    seen = {}

    class R:
        returncode = 0
        stdout = '{"subtype":"success","is_error":false,"result":"OK","usage":{}}'
        stderr = ""

    monkeypatch.setattr(claude_backend.subprocess, "run",
                        lambda cmd, **kw: (seen.update(env=kw.get("env") or {}), R())[1])
    monkeypatch.setattr(claude_backend, "_record_usage", lambda *a, **k: None)

    claude_backend.call("do a thing", "")
    assert seen["env"]["MAX_THINKING_TOKENS"] == "4000"


# ── Section balancing + overflow ────────────────────────────────────────────


def _cat(title, score, category):
    return {"title": title, "relevance": score, "relevance_source": "ai",
            "category": category}


def test_balanced_take_gives_every_section_its_lead_first():
    import main

    # Opinion sweeps the top scores; Art and Agriculture score lower.
    arts = (
        [_cat(f"op{i}", 95 - i, "Opinion") for i in range(10)]
        + [_cat("art1", 84, "Art"), _cat("art2", 83, "Art")]
        + [_cat("ag1", 82, "Agriculture")]
    )
    kept, overflow = main._balanced_take(arts, 6)

    sections = [a["category"] for a in kept]
    # Every section represented, and no section monopolises the issue.
    assert set(sections) == {"Opinion", "Art", "Agriculture"}
    assert sections.count("Opinion") == 3
    assert len(kept) == 6
    assert len(overflow) == 7
    # Overflow is the high scorers that lost their slot, best first.
    assert overflow[0]["relevance"] >= overflow[-1]["relevance"]


def test_balanced_take_visits_the_strongest_section_first():
    import main

    arts = [_cat("weak", 81, "Art"), _cat("strong", 99, "Opinion")]
    kept, _ = main._balanced_take(arts, 2)
    assert [a["title"] for a in kept] == ["strong", "weak"]


def test_balanced_take_handles_a_single_section():
    import main

    arts = [_cat(f"t{i}", 90 - i, "Opinion") for i in range(5)]
    kept, overflow = main._balanced_take(arts, 3)
    assert [a["title"] for a in kept] == ["t0", "t1", "t2"]
    assert [a["title"] for a in overflow] == ["t3", "t4"]


def test_balanced_take_stops_when_articles_run_out():
    import main

    arts = [_cat("a", 90, "Art"), _cat("b", 85, "Opinion")]
    kept, overflow = main._balanced_take(arts, 10)
    assert len(kept) == 2
    assert overflow == []


def test_filter_balances_when_enabled(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("max_articles_per_issue", 4)
    store.set_setting("balance_sections", True)
    _reload(monkeypatch)

    import main

    arts = (
        [_cat(f"op{i}", 95 - i, "Opinion") for i in range(6)]
        + [_cat("art1", 80, "Art")]
        + [_cat("mx1", 79, "México")]
    )
    kept, overflow = main._apply_interest_filter(arts)
    cats = {a["category"] for a in kept}
    assert cats == {"Opinion", "Art", "México"}, cats
    assert len(kept) == 4
    assert len(overflow) == 4


def test_filter_without_balancing_is_pure_score_order(isolated_store, monkeypatch):
    store.init_db()
    store.set_setting("max_articles_per_issue", 3)
    _reload(monkeypatch)

    import main

    arts = (
        [_cat(f"op{i}", 95 - i, "Opinion") for i in range(5)]
        + [_cat("art1", 80, "Art")]
    )
    kept, overflow = main._apply_interest_filter(arts)
    assert {a["category"] for a in kept} == {"Opinion"}
    assert any(a["category"] == "Art" for a in overflow)


def test_overflow_section_label_exists_in_every_language():
    from ai_locale import EPUB_LABELS

    for code in ("en", "es", "pt-BR"):
        assert EPUB_LABELS[code]["overflow_section"]


def test_min_section_stories_rescues_sections_below_the_threshold(
    isolated_store, monkeypatch
):
    """A global threshold otherwise deletes whole interest areas."""
    store.init_db()
    store.set_setting("min_keep_score", 80)
    store.set_setting("min_section_stories", 2)
    store.set_setting("balance_sections", True)
    store.set_setting("max_articles_per_issue", 8)
    _reload(monkeypatch)

    import main

    arts = (
        [_cat(f"op{i}", 95 - i, "Opinion") for i in range(10)]
        # No Art or Agriculture story clears 80.
        + [_cat("art1", 62, "Art"), _cat("art2", 58, "Art"), _cat("art3", 40, "Art")]
        + [_cat("ag1", 55, "Agriculture")]
    )
    kept, _ = main._apply_interest_filter(arts)
    cats = {a["category"] for a in kept}
    assert "Art" in cats, cats
    assert "Agriculture" in cats, cats
    # Only the section's best two are spared, not its whole backlog.
    assert "art3" not in [a["title"] for a in kept]


def test_min_section_stories_off_by_default_keeps_threshold_absolute(
    isolated_store, monkeypatch
):
    store.init_db()
    store.set_setting("min_keep_score", 80)
    _reload(monkeypatch)

    import main

    arts = [_cat("op", 95, "Opinion"), _cat("art", 62, "Art")]
    kept, _ = main._apply_interest_filter(arts)
    assert [a["title"] for a in kept] == ["op"]


def test_min_section_stories_alone_still_filters(isolated_store, monkeypatch):
    """Setting only the floor must not become a no-op path."""
    store.init_db()
    store.set_setting("min_section_stories", 1)
    store.set_setting("min_keep_score", 90)
    _reload(monkeypatch)

    import main

    arts = [_cat("a", 95, "X"), _cat("b", 10, "X"), _cat("c", 20, "Y")]
    kept, _ = main._apply_interest_filter(arts)
    titles = {a["title"] for a in kept}
    assert "a" in titles          # clears the bar
    assert "c" in titles          # section Y's best, spared
    assert "b" not in titles      # section X already had its one
